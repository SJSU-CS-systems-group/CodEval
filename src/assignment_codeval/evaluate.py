#! /usr/bin/python3

import ast
import os
import re
import subprocess
import sys
import traceback
import threading
import time

import click

from assignment_codeval.file_utils import unzip

###########################################################
# Globals
###########################################################

TESTING_DIR = ".testing"


def get_testing_path(filename: str) -> str:
    """Return the path to a file in the testing directory."""
    return os.path.join(TESTING_DIR, filename)


test_args = ""
cmps = []
timeout_val = 10
output_length_limit = 4096
expected_exit_code = -1
test_case_count = 0
test_case_hint = ""
test_case_total = 0
num_passed = 0
num_failed = 0
is_hidden_testcase = False
is_verbose = False
compilelog = []
last_compile_command = ""
temp_files = []
_active_temp_files = []

###########################################################
# Specification Tags to Function Mapping
###########################################################

# Shell commands that likely indicate a missing CMD prefix when found untagged
_BARE_SHELL_COMMANDS = {
    'echo', 'rm', 'cp', 'mv', 'mkdir', 'rmdir', 'cat', 'ls', 'grep',
    'sed', 'awk', 'find', 'chmod', 'chown', 'touch', 'ln', 'diff',
    'sort', 'head', 'tail', 'cut', 'tr', 'wc', 'bash', 'sh', 'python',
    'python3', 'make', 'export', 'source', 'kill', 'pkill', 'sleep',
    'printf', 'read', 'unzip', 'tar', 'curl', 'wget',
}


def compile_code(compile_command):
    """Specifies the command to compile the submission code

    Arguments:
        compile_command: the command to compile the submission code with

    Returns:
        None
    """
    global last_compile_command
    last_compile_command = compile_command

    if test_case_count != 0:
        check_test()

    # Run compile command
    with open(get_testing_path("compilelog"), "w") as outfile:
        compile_popen = subprocess.Popen(
            compile_command, shell=True, stdout=outfile, stderr=outfile, text=True
        )

    compile_popen.communicate(compile_popen)

    if compile_popen.returncode:
        with open(get_testing_path("compilelog"), "r") as infile:
            compile_log = infile.readlines()

        # Print head of compile log
        for line in compile_log[:10]:
            print(line, end="")

        if len(compile_log) > 10:
            print("...", end="")

            # Print tail of compile log
            for line in compile_log[-10:]:
                print(line, end="")

        sys.exit(1)


###########################################################
# Function detection helpers
###########################################################


def _detect_language(files):
    """Return 'c_cpp', 'java', 'python', or 'unknown' based on file extensions."""
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in ('.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'):
            return 'c_cpp'
        if ext == '.java':
            return 'java'
        if ext == '.py':
            return 'python'
    return 'unknown'


def _find_compiled_artifact(source_file):
    """Return the compiled artifact for a source file, or None if not found.

    Checks (in order): same base name with .o, .exe, and no extension.
    """
    base = os.path.splitext(source_file)[0]
    for candidate in (base + '.o', base + '.exe', base):
        if os.path.exists(candidate):
            return candidate
    return None


def _extract_executable_from_compile(compile_command):
    """Extract the output executable name from a compile command (looks for -o <name>).

    Returns the executable name, or None if not found.
    """
    parts = compile_command.split()
    for i, part in enumerate(parts):
        if part == '-o' and i + 1 < len(parts):
            return parts[i + 1]
    return None


def _extract_source_files_from_compile(compile_command):
    """Extract source file arguments from a compile command.

    Recognises common source file extensions (.c, .cpp, .cc, .cxx, .java, .py)
    and skips option arguments that consume the following token as a value
    (e.g. -o, -I, -L, -l, -include, -isystem, -MF, -MT, -MQ).

    Returns a list of source file paths found in the command.
    """
    source_exts = ('.c', '.cpp', '.cc', '.cxx', '.java', '.py')
    value_flags = {'-o', '-I', '-L', '-l', '-include', '-isystem', '-MF', '-MT', '-MQ'}
    parts = compile_command.split()
    files = []
    skip_next = False
    for part in parts:
        if skip_next:
            skip_next = False
            continue
        if part in value_flags:
            skip_next = True
            continue
        if not part.startswith('-') and any(part.endswith(ext) for ext in source_exts):
            files.append(part)
    return files


def _function_used_in_c_cpp(function_name, files):
    """Use objdump on compiled artifacts to detect C/C++ function usage.

    Returns True if found, False if artifact exists but function absent,
    None if no compiled artifact was found (caller should fall back).
    """
    found_artifact = False
    for source_file in files:
        artifact = _find_compiled_artifact(source_file)
        if artifact is None:
            continue
        found_artifact = True
        # objdump -t dumps the symbol table; pipe through c++filt to demangle C++ names.
        # Mangled C++ names embed the original identifier, so grep -w finds exact matches.
        cmd = f"objdump -t '{artifact}' | c++filt | grep -w '{function_name}'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return True
    if not found_artifact:
        return None
    return False


def _function_used_in_java(function_name, files):
    """Use javap on compiled .class files to detect Java method usage.

    Returns True if found, False if class file exists but method absent,
    None if no .class file was found (caller should fall back).
    """
    found_class = False
    for source_file in files:
        base = os.path.splitext(source_file)[0]
        class_file = base + '.class'
        if not os.path.exists(class_file):
            continue
        found_class = True
        # javap -c disassembles bytecode; method invocations reference the method name.
        result = subprocess.run(
            ["javap", "-c", class_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if function_name.encode() in result.stdout:
            return True
    if not found_class:
        return None
    return False


def _function_used_in_python(function_name, files):
    """Use the ast module to detect function calls in Python source files.

    Returns True if a matching call is found, False otherwise.
    Handles both direct calls (func()) and attribute calls (obj.func()).
    """
    for source_file in files:
        try:
            with open(source_file, 'r') as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == function_name:
                        return True
                    if isinstance(func, ast.Attribute) and func.attr == function_name:
                        return True
        except (SyntaxError, OSError):
            continue
    return False


def _function_used_regex(function_name, files):
    """Legacy regex-based fallback used when no compiled artifact is available."""
    regex = rf'(^|[^[:alnum:]_]){function_name}[[:space:]]*\('
    cmd = (
        "sed -E "
        "'"
        "s://.*$::g; "
        "s:#.*$::g; "
        ":a; /\\/\\*/{N; s:/\\*.*?\\*/::g; ba}"
        "' "
        + " ".join(files)
        + f" | grep -E '{regex}'"
    )
    result = subprocess.run(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def _is_function_used(function_name, files, allow_regex_fallback=True):
    """Detect whether function_name is used in the given files.

    Dispatches to the appropriate tool based on file language:
      - C/C++:  objdump on compiled artifact (falls back to regex if none found
                and allow_regex_fallback is True)
      - Java:   javap on .class file (falls back to regex if none found
                and allow_regex_fallback is True)
      - Python: ast module on source
      - Other:  regex on source (only when allow_regex_fallback is True)

    When allow_regex_fallback is False (used when no filename was given in the
    CF tag), the function relies solely on compiled-artifact inspection and
    returns False rather than falling back to regex.
    """
    lang = _detect_language(files)
    if lang == 'python':
        return _function_used_in_python(function_name, files)
    if lang == 'java':
        result = _function_used_in_java(function_name, files)
        if result is None:
            return _function_used_regex(function_name, files) if allow_regex_fallback else False
        return result
    if lang == 'c_cpp':
        result = _function_used_in_c_cpp(function_name, files)
        if result is None:
            return _function_used_regex(function_name, files) if allow_regex_fallback else False
        return result
    if allow_regex_fallback:
        return _function_used_regex(function_name, files)
    return False


def check_function(args):
    """Will be followed by a function name and an optional list of files to check to ensure that
    the function is used by one of those files.

    When no filename is provided (preferred usage), the source files are derived from the most
    recent C (compile) tag.  The check then relies solely on compiled-artifact inspection
    (objdump for C/C++, javap for Java, ast for Python) with no regex fallback.

    When a filename is provided (legacy usage), the same compiled-artifact inspection is used
    first, but a regex scan of the source file is available as a fallback when no compiled
    artifact can be found.

    Arguments:
        function_name: the function name to check files for usage of
        *files: (optional) the files to check for the function name.  If omitted, source
                files are inferred from the most recent C tag.

    Returns:
        None
    """
    check_test()
    args_list = args.split()
    function_name = args_list[0]
    files = args_list[1:]

    if not files:
        # No filename provided — derive source files from the compile command and
        # disable the regex fallback (compiled-artifact check only).
        files = _extract_source_files_from_compile(last_compile_command)
        if _is_function_used(function_name, files, allow_regex_fallback=False):
            print(f"Used {function_name} PASSED")
        else:
            print(f"Not using {function_name} FAILED")
    else:
        if _is_function_used(function_name, files):
            print(f"Used {function_name} PASSED")
        else:
            print(f"Not using {function_name} FAILED")

def check_object(args):
    """Will be followed by an object and a list of files to ensure that the function is
    used by one of those files. 
    
    This primarily is used for C++ objects from instances of the ifstream and ofstream operators
    
    Arguments:
        object_name: the object name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    
    check_test()
    args = args.split()
    object_name = args[0]
    files = args[1:]

    # Match:
    #  [1] start of line OR non-identifier character
    #  [2] object name
    #  [3] optional whitespace
    #  [4] stream operator << or >>
    regex = rf'(^|[^[:alnum:]_]){object_name}[[:space:]]*(<<|>>)'

    # Strip comments, then search
    cmd = (
        "sed -E "
        "'s://.*$::g; "              # remove // comments
        ":a; /\\/\\*/{N; s:/\\*.*?\\*/::g; ba}' "
        + " ".join(files)
        + f" | grep -E '{regex}'"
    )

    # Surpress output
    function_popen = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    function_popen.communicate()
    if function_popen.returncode:
        print(f"Not using {object_name} FAILED")
    else:
        print(f"Used {object_name} PASSED")
        
def check_container(args):
    """Will be followed by a container and a list of files to ensure that the function is
    used by one of those files. 
    
    This primarily is used for C++ containers such as vector<double> or std::vector v;
    
    Arguments:
        object_name: the object name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    
    check_test()
    args = args.split()
    container_name = args[0]
    files = args[1:]
    
    # Match:
    #  [1] start of line OR non-identifier character
    #  [2] container name
    #  [3] optional whitespace
    #  [4] either '<' (template usage) or space (e.g. std::vector v;)
    regex = rf'(^|[^[:alnum:]_]){container_name}[[:space:]]*(<|[[:space:]])'

    # Strip comments, then search
    cmd = (
        "sed -E "
        "'s://.*$::g; "
        ":a; /\\/\\*/{N; s:/\\*.*?\\*/::g; ba}' "
        + " ".join(files)
        + f" | grep -E '{regex}'"
    )

    function_popen = subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    function_popen.communicate()
    if function_popen.returncode:
        print(f"Not using {container_name} FAILED")
    else:
        print(f"Used {container_name} PASSED")
    

def check_not_function(args):
    """Will be followed by a function name and an optional list of files to check to ensure that
    the function is not used by any of those files.

    When no filename is provided (preferred usage), the source files are derived from the most
    recent C (compile) tag.  The check relies solely on compiled-artifact inspection with no
    regex fallback.

    When a filename is provided (legacy usage), compiled-artifact inspection is used first with
    a regex fallback when no compiled artifact is found.

    Arguments:
        function_name: the function name to check files for usage of
        *files: (optional) the files to check for the function name.  If omitted, source
                files are inferred from the most recent C tag.

    Returns:
        None
    """
    check_test()
    args_list = args.split()
    function_name = args_list[0]
    files = args_list[1:]

    if not files:
        # No filename provided — derive source files from the compile command and
        # disable the regex fallback (compiled-artifact check only).
        files = _extract_source_files_from_compile(last_compile_command)
        used = _is_function_used(function_name, files, allow_regex_fallback=False)
    else:
        used = _is_function_used(function_name, files)

    if used:
        print(f"Used {function_name} FAILED")
    else:
        print(f"Not using {function_name} PASSED")


def print_label(text):
    """Print a label/message to stdout.

    Arguments:
        text: the text to print

    Returns:
        None
    """
    check_test()
    print(text)


def run_command(command):
    """Will be followed by a command to run.

    Arguments:
        command: the command to run

    Returns:
        None
    """
    check_test()

    # Execute without surpressing output
    command_popen = subprocess.Popen(command, shell=True)
    command_popen.communicate()


def run_command_noerror(command):
    """Will be followed by a command to run, evaluation fails if the command exits with an error.

    Arguments:
        command: the command to run

    Returns:
        None
    """
    check_test()
    _pre_test_temp_cleanup()

    # Run as test case
    global test_case_count
    test_case_count += 1
    print(f"Test case count {test_case_count} of {test_case_total}")

    # Execute without surpressing output
    command_popen = subprocess.Popen(command, shell=True)
    command_popen.communicate()

    if command_popen.returncode:
        print("FAILED")
        eval_logs_dir = get_testing_path("evaluationLogs")
        if os.path.exists(eval_logs_dir):
            for file in os.listdir(eval_logs_dir):
                with open(os.path.join(eval_logs_dir, file), "r") as infile:
                    file_lines = infile.readlines()
                # Print entire file
                print("\n".join(file_lines))

        # Exit entire program with error
        sys.exit(1)
    else:
        print("PASSED")


def compare(files):
    """Will be followed by files to compare.

    Arguments:
        files: A string of space-separated files to compare

    Returns:
        None
    """
    cmps.append(files.split())


def test_case(test_case_command):
    """Will be followed by the command to run to test the submission.

    Arguments:
        test_case_command: the command to run the submission

    Returns:
        None
    """
    check_test()
    _pre_test_temp_cleanup()

    # Clear hint
    global test_case_hint
    test_case_hint= ""

    # Set new test case command
    global test_args
    test_args = test_case_command

    # Increment test cases
    global test_case_count
    test_case_count += 1

    # Set test case hidden
    global test_case_hidden
    test_case_hidden = False


def test_case_hidden(test_case_command):
    """Will be followed by the command to run to test the submission. Test case is hidden.

    Arguments:
        test_case_command: the command to run the submission

    Returns:
        None
    """
    check_test()
    _pre_test_temp_cleanup()

    # Clear hint
    global test_case_hint
    test_case_hint = ""

    # Set new test case command
    global test_args
    test_args = test_case_command

    # Increment test cases
    global test_case_count
    test_case_count += 1

    # Set hidden test case
    global test_case_hidden
    test_case_hidden = True


def supply_input(inputs):
    """Specifies the input for a test case (adds newline at end).

    Arguments:
        *inputs: inputs to be used for test case

    Returns:
        None
    """
    with open(get_testing_path("fileinput"), "ab") as outfile:
        outfile.write((inputs + "\n").encode("utf-8"))


def supply_input_bare(inputs):
    """Specifies the input for a test case without adding a newline.

    Arguments:
        *inputs: inputs to be used for test case

    Returns:
        None
    """
    with open(get_testing_path("fileinput"), "ab") as outfile:
        outfile.write(inputs.encode("utf-8"))


def supply_input_file(input_file):
    """Specifies the input for a test case read from a file.

    Arguments:
        input_file: file to get input for test case from

    Returns:
        None
    """
    with open(input_file, "rb") as infile:
        input_data = infile.read()

    with open(get_testing_path("fileinput"), "ab") as outfile:
        outfile.write(input_data)


def check_output(outputs):
    """Specifies the expected output for a test case (adds newline at end).

    Arguments:
        *outputs: outputs to be used for test case

    Returns:
        None
    """

    with open(get_testing_path("expectedoutput"), "a") as outfile:
        outfile.write(outputs + "\n")


def check_output_bare(outputs):
    """Specifies the expected output for a test case without adding a newline.

    Arguments:
        *outputs: outputs to be used for test case

    Returns:
        None
    """

    with open(get_testing_path("expectedoutput"), "a") as outfile:
        outfile.write(outputs)


def check_output_file(output_file):
    """Specifies the expected output for a test case read from a file.

    Arguments:
        output_file: file to get output for test case from

    Returns:
        None
    """
    output_length(os.path.getsize(output_file)) 
    with open(output_file, "r") as infile:
        output_lines = infile.readlines()
        
    with open(get_testing_path("expectedoutput"), "a") as outfile:
        outfile.writelines(output_lines)


def check_error(error_output):
    """Specifies the expected error output for a test case (adds newline at end).

    Arguments:
        error_output: expected error output for a test case

    Returns:
        None
    """
    with open(get_testing_path("expectederror"), "a") as outfile:
        outfile.write(error_output + "\n")


def check_error_bare(error_output):
    """Specifies the expected error output for a test case without adding a newline.

    Arguments:
        error_output: expected error output for a test case

    Returns:
        None
    """
    with open(get_testing_path("expectederror"), "a") as outfile:
        outfile.write(error_output)


def hint(hints):
    """Hint

    Arguments:
        *hints: hints to be associated with test case

    Returns:
        None
    """
    global test_case_hint
    test_case_hint = hints


def register_temp_file(filename):
    """Registers a file to be deleted before and after the next T, HT, or TCMD test.

    Arguments:
        filename: the file to delete before and after the next test

    Returns:
        None
    """
    global temp_files
    temp_files.append(filename.strip())


def _cleanup_temp_files():
    """Delete all registered temp files and reset the list."""
    global temp_files
    for f in temp_files:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    temp_files = []


def _pre_test_temp_cleanup():
    """Before a test: delete registered temp files and save the list for post-test cleanup."""
    global temp_files, _active_temp_files
    _active_temp_files = list(temp_files)
    _cleanup_temp_files()


def _post_test_temp_cleanup():
    """After a test: delete the files that were registered when the test started."""
    global _active_temp_files
    for f in _active_temp_files:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    _active_temp_files = []


def timeout(timeout_sec):
    """Specifies the time limit in seconds for a test case to run. Defaults to 20 seconds.

    Arguments:
        timeout_sec: time limit in seconds for a test case to run

    Returns:
        None
    """
    global timeout_val
    timeout_val = float(timeout_sec)


def output_length(length):
    """Specifies the maximum number of bytes of diff output to render. Defaults to 4096.

    Arguments:
        length: maximum output length in bytes

    Returns:
        None
    """
    global output_length_limit
    output_length_limit = int(length)


def exit_code(test_case_exit_code):
    """Specifies the expected exit code for a test case. Defaults to zero.

    Arguments:
        test_case_exit_code: the expected exit code for a test case

    Returns:
        None
    """
    global expected_exit_code
    expected_exit_code = int(test_case_exit_code)


def start_server(timeout_sec, kill_timeout_sec, *server_cmd):
    """Command containing timeout (wait until server starts), kill timeout (wait to kill the server),
    and the command to start a server

    Arguments:
        timeout_sec: timeout in seconds to wait for server to start
        kill_timeout_sec: timeout in seconds to wait until killing the server
        server_cmd: command to run to start the server

    Returns:
        None
    """

    print(
        f'Starting server with command: {" ".join(server_cmd)} and sleeping for: {timeout_sec}. Will kill server '
        f'after {kill_timeout_sec} seconds.'
    )

    # Send output to compile log in background
    with open(get_testing_path("compilelog"), "w") as outfile:
        server_popen = subprocess.Popen(
            server_cmd, shell=True, stdout=outfile, stderr=outfile, text=True
        )

    print(f"Server pid: {server_popen.pid}. Sleeping for {timeout_sec} seconds.")
    # Block for timeout_sec so that server can start
    time.sleep(float(timeout_sec))

    # Kill the server after the timeout
    def kill_server(pid):
        print(f"Killing {pid}")
        subprocess.Popen(
            ["kill", "-9", f"{pid}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    kill_timer = threading.Timer(
        float(kill_timeout_sec), kill_server, *[server_popen.pid]
    )
    kill_timer.daemon = True
    kill_timer.start()


"""
Here is where the tags are mapped to functions.
Any tags that are added or changed must be modified here.
Assume that everything will be passed to these functions as a string, account for
this in the function itself.
"""
tag_func_map = {
    "C": compile_code,
    "CF": check_function,
    "CO" : check_object,
    "CC": check_container,
    "NCF": check_not_function,
    "PRINT": print_label,
    "CMD": run_command,
    "TCMD": run_command_noerror,
    "CMP": compare,
    "T": test_case,
    "HT": test_case_hidden,
    "I": supply_input,
    "IB": supply_input_bare,
    "IF": supply_input_file,
    "O": check_output,
    "OB": check_output_bare,
    "OF": check_output_file,
    "E": check_error,
    "EB": check_error_bare,
    "HINT": hint,
    "TO": timeout,
    "OLEN": output_length,
    "X": exit_code,
    "SS": start_server,
    "TEMP": register_temp_file,
}


def setup():
    files = [
        "compilelog",
        "difflog",
        "expectedoutput",
        "expectederror",
        "fileinput",
        "yourerror",
        "youroutput",
    ]
    cleanup()
    # Create testing directory and files
    os.makedirs(TESTING_DIR, exist_ok=True)
    for file in files:
        open(get_testing_path(file), "w").close()

    # Reset test case variables
    global expected_exit_code
    expected_exit_code = -1
    global cmps
    cmps = []


def parse_tags(tags: list[str]):
    """Given list of strings, parses and executes tags

    Arguments:
        tags (list[str]): list of tags and arguments to be parsed and executed

    Returns:
        None
    """
    # Pattern matches: TAG arguments (arguments required)
    # Use single space separator to preserve leading whitespace in values
    tag_pattern = r"([A-Z_]+) (.*)"
    # Pattern for tag with optional arguments
    tag_only_pattern = r"([A-Z_]+)\s*$"

    valid_tags = set(tag_func_map.keys())
    # Tags to silently ignore (used by other tools but not by run-evaluation)
    ignored_tags = {"CD", "CTO", "Z", "RUN"}

    # Track if we're inside a CRT_HW block (content to ignore)
    in_crt_hw_block = False

    for line_num, tag_line in enumerate(tags, start=1):
        # Skip empty lines and comments
        stripped = tag_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Check for CRT_HW block delimiter
        if stripped.startswith("CRT_HW"):
            in_crt_hw_block = not in_crt_hw_block
            continue

        # Skip lines inside CRT_HW block
        if in_crt_hw_block:
            continue

        tag_match = re.match(tag_pattern, tag_line)
        tag_only_match = re.match(tag_only_pattern, tag_line)

        # Check for tag without arguments
        if tag_only_match and not tag_match:
            tag = tag_only_match.group(1)
            # Skip ignored tags
            if tag in ignored_tags:
                continue
            if tag in valid_tags:
                print(f"Error on line {line_num}: Tag '{tag}' requires arguments")
                print(f"  {line_num}: {tag_line.rstrip()}")
                sys.exit(1)
            elif tag.isupper():
                print(f"Error on line {line_num}: Unknown tag '{tag}'")
                print(f"  {line_num}: {tag_line.rstrip()}")
                print(f"  Valid tags are: {', '.join(sorted(valid_tags))}")
                sys.exit(1)
            continue

        # If line does not match tag format, skip non-tag lines
        if not tag_match:
            # Check if it looks like an invalid tag (starts with uppercase letters)
            potential_tag = re.match(r"([A-Z]+)", tag_line)
            if potential_tag:
                tag = potential_tag.group(1)
                # Skip ignored tags
                if tag in ignored_tags:
                    continue
                if tag not in valid_tags and len(tag) <= 4:
                    print(f"Error on line {line_num}: Unknown tag '{tag}'")
                    print(f"  {line_num}: {tag_line.rstrip()}")
                    print(f"  Valid tags are: {', '.join(sorted(valid_tags))}")
                    sys.exit(1)
            else:
                # Check if this looks like a bare shell command missing a CMD prefix
                first_word = tag_line.split()[0] if tag_line.split() else ""
                if first_word.lower() in _BARE_SHELL_COMMANDS:
                    print(f"Warning on line {line_num}: bare shell command without CMD prefix, shell commands will be ignored")
                    print(f"  {line_num}: {tag_line.rstrip()}")
                    print(f"  Did you mean: CMD {tag_line.rstrip()}")
            continue

        tag = tag_match.group(1)
        args = tag_match.group(2)

        # Skip ignored tags
        if tag in ignored_tags:
            continue

        # Check for unknown tag
        if tag not in valid_tags:
            print(f"Error on line {line_num}: Unknown tag '{tag}'")
            print(f"  {line_num}: {tag_line.rstrip()}")
            print(f"  Valid tags are: {', '.join(sorted(valid_tags))}")
            sys.exit(1)

        # Check for empty arguments
        if not args.strip():
            print(f"Error on line {line_num}: Tag '{tag}' requires arguments")
            print(f"  {line_num}: {tag_line.rstrip()}")
            sys.exit(1)

        # Execute function based on tag-function mapping
        try:
            tag_func_map[tag](args)
        except TypeError as e:
            print(f"Error on line {line_num}: Invalid arguments for tag '{tag}'")
            print(f"  {line_num}: {tag_line.rstrip()}")
            print(f"  Details: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Error on line {line_num}: Invalid value for tag '{tag}'")
            print(f"  {line_num}: {tag_line.rstrip()}")
            print(f"  Details: {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"Error on line {line_num}: File not found for tag '{tag}'")
            print(f"  {line_num}: {tag_line.rstrip()}")
            print(f"  Details: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error on line {line_num}: Unexpected error for tag '{tag}'")
            print(f"  {line_num}: {tag_line.rstrip()}")
            print(f"  Details: {e}")
            traceback.print_exc()
            sys.exit(1)


def parse_diff(diff_lines: list[str], testing_dir: str):
    """Given output from diff command, parse lines into console

    Arguments:
        diff_lines (list[str]): list of lines as output from diff command
        testing_dir (str): directory to create evaluationLogs in

    Returns:
        None
    """
    eval_logs_dir = os.path.join(testing_dir, "evaluationLogs")
    os.makedirs(eval_logs_dir, exist_ok=True)
    # Directly write into logOfDiff rather than use redirection
    with open(os.path.join(eval_logs_dir, "logOfDiff"), "w") as outfile:
        for line in diff_lines:
            first_word = line.split(" ")[:2]
            first_character = first_word[0]

            if first_character != "@":
                # Lines present in your output but not present in expected
                if first_character == "-" and first_word[:3] == "---":
                    student_output_file = line[3:-37]
                    outfile.write(f"Your output file: {student_output_file}")

                # Lines present in expected output but not in yours
                elif first_character == "+" and first_word[:3] == "+++":
                    expected_output_file = line[3:-37]
                    outfile.write(f"Expected output file: {expected_output_file}")

                # Catch rest
                else:
                    outfile.write(line)


def _render_diff_output(raw_bytes: bytes) -> str:
    """Render raw bytes for diff output, making unprintable characters visible.

    Replaces the shell pipeline `cat -te | head -22` with pure Python.
    """
    result = []
    i = 0
    n = len(raw_bytes)

    while i < n:
        b = raw_bytes[i]

        if b == 0x0A:  # newline
            result.append("$\n")
            i += 1
        elif b == 0x20 or (0x21 <= b <= 0x7E):  # space or printable ASCII
            result.append(chr(b))
            i += 1
        elif b <= 0x1F:  # control chars (except newline handled above)
            result.append("^" + chr(b + 0x40))
            i += 1
        elif b == 0x7F:  # DEL
            result.append("^?")
            i += 1
        elif b >= 0x80:
            # Try to decode as UTF-8 multi-byte sequence
            seq_len = 0
            if (b & 0xE0) == 0xC0:
                seq_len = 2
            elif (b & 0xF0) == 0xE0:
                seq_len = 3
            elif (b & 0xF8) == 0xF0:
                seq_len = 4

            decoded_char = None
            if seq_len >= 2 and i + seq_len <= n:
                try:
                    decoded_char = raw_bytes[i:i + seq_len].decode("utf-8")
                except UnicodeDecodeError:
                    pass

            if decoded_char and len(decoded_char) == 1 and decoded_char.isprintable():
                result.append(decoded_char)
                i += seq_len
            elif decoded_char and len(decoded_char) == 1:
                # Valid UTF-8 but non-printable: render each byte as \xCC
                for j in range(seq_len):
                    result.append(f"\\x{raw_bytes[i + j]:02X}")
                i += seq_len
            else:
                # Invalid UTF-8 byte
                result.append(f"\\x{b:02X}")
                i += 1
        else:
            result.append(chr(b))
            i += 1

    output = "".join(result)

    # If output doesn't end with \n, append $ at the very end
    if output and not output.endswith("\n"):
        output += "$"

    return output


def _find_touched_files(pre_run_timestamp):
    """Find files touched (modified or accessed) since pre_run_timestamp.

    Recursively scans the current working directory, ignoring TESTING_DIR.
    """
    touched = []
    for dirpath, dirnames, filenames in os.walk("."):
        # Prune TESTING_DIR from traversal
        if TESTING_DIR in dirnames:
            dirnames.remove(TESTING_DIR)
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                st = os.stat(filepath)
                if st.st_mtime > pre_run_timestamp or st.st_atime > pre_run_timestamp:
                    touched.append(filepath)
            except OSError:
                continue
    return touched


def check_test():
    global test_args
    if test_args == "":
        return

    print(f"Test case {test_case_count} of {test_case_total}")
    passed = True

    # Record timestamp before running student code for file tracking
    pre_run_timestamp = time.time()

    with open(get_testing_path("fileinput"), "rb") as fileinput, open(
        get_testing_path("youroutput"), "w"
    ) as youroutput, open(get_testing_path("yourerror"), "w") as yourerror:
        test_exec = subprocess.Popen(
            test_args, shell=True, stdin=fileinput, stdout=youroutput, stderr=yourerror
        )

    # Timeout handling
    try:
        test_exec.communicate(timeout=timeout_val)

    except subprocess.TimeoutExpired:
        print(f"Took more than {timeout_val} seconds to run. FAIL")
        passed = False

    # Find files touched by student's program
    touched_files = _find_touched_files(pre_run_timestamp)

    # Difflog handling
    with open(get_testing_path("difflog"), "w") as outfile:
        diff_popen = subprocess.Popen(
            ["diff", "-U1", "-a",
             f"./{TESTING_DIR}/youroutput", f"./{TESTING_DIR}/expectedoutput"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        raw_output, _ = diff_popen.communicate()
        outfile.write(_render_diff_output(raw_output[:output_length_limit]))

    # Append to difflog second time around
    with open(get_testing_path("difflog"), "a") as outfile:
        diff_popen = subprocess.Popen(
            ["diff", "-U1", "-a",
             f"./{TESTING_DIR}/yourerror", f"./{TESTING_DIR}/expectederror"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        raw_output, _ = diff_popen.communicate()
        outfile.write(_render_diff_output(raw_output[:output_length_limit]))

    # Now read all the lines to accumulate both diffs
    with open(get_testing_path("difflog"), "r") as infile:
        diff_lines = infile.readlines()

    if len(diff_lines):
        passed = False
        parse_diff(diff_lines, TESTING_DIR)

    # Exit code handling
    if expected_exit_code != -1 and test_exec.returncode != expected_exit_code:
        passed = False
        print(
            f"    Exit Code failure: expected {expected_exit_code} got {test_exec.returncode}"
        )

    # Compare files handling, do not surpress output
    for files in cmps:
        cmd_popen = subprocess.Popen(["cmp"] + files)
        cmd_popen.communicate()
        if cmd_popen.returncode:
            passed = False
            break

    # Pass fail handling
    if passed:
        global num_passed
        num_passed += 1
        print("Passed")
    else:
        global num_failed
        num_failed += 1
        print("FAILED")

        # Hidden test case handling
        if test_case_hidden:
            print("    Test Case is Hidden")
            if test_case_hint:
                print(f"HINT: {test_case_hint}")
        else:
            if test_case_hint:
                print(f"HINT: {test_case_hint}")

            # Cleanup
            print(f"    Command ran: {test_args}")
            eval_logs_dir = get_testing_path("evaluationLogs")
            if os.path.exists(eval_logs_dir):
                for file in os.listdir(eval_logs_dir):
                    with open(os.path.join(eval_logs_dir, file), "r") as infile:
                        file_lines = infile.readlines()

                    # Print entire file
                    print("".join(file_lines))

            # Show diffs for files touched by student's program
            if touched_files and cmps:
                expected_map = {}
                for file_pair in cmps:
                    if len(file_pair) >= 2:
                        expected_map[os.path.normpath(file_pair[0])] = file_pair[1]

                for filepath in touched_files:
                    normalized = os.path.normpath(filepath)
                    if normalized in expected_map:
                        expected_file = expected_map[normalized]
                        if os.path.exists(expected_file):
                            diff_proc = subprocess.Popen(
                                ["diff", "-U1", "-a", filepath, expected_file],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                            )
                            diff_output, _ = diff_proc.communicate()
                            if diff_output:
                                print(f"    File output diff ({os.path.basename(filepath)}):")
                                lines = diff_output.splitlines()
                                for line in lines[:22]:
                                    print(f"    {line}")
                                if len(lines) > 22:
                                    print(f"    ... ({len(lines) - 22} more lines)")

        _post_test_temp_cleanup()
        cleanup()

        # Exit program after failed test case
        sys.exit(2)

    # reinitialize test variables and files here
    _post_test_temp_cleanup()
    setup()


def cleanup():
    global test_args
    test_args = ""
    files = [
        "compilelog",
        "difflog",
        "expectedoutput",
        "expectederror",
        "fileinput",
        "yourerror",
        "youroutput",
    ]

    eval_logs_dir = get_testing_path("evaluationLogs")
    if os.path.exists(eval_logs_dir):
        log_of_diff = os.path.join(eval_logs_dir, "logOfDiff")
        if os.path.exists(log_of_diff):
            os.remove(log_of_diff)
            os.rmdir(eval_logs_dir)

    for name in files:
        file_path = get_testing_path(name)
        if os.path.exists(file_path):
            os.remove(file_path)

    # Remove the testing directory if it exists and is empty
    if os.path.exists(TESTING_DIR) and not os.listdir(TESTING_DIR):
        os.rmdir(TESTING_DIR)


@click.command()
@click.argument("codeval_file", type=click.Path(exists=True))
def run_evaluation(codeval_file):
    """
    This command should be run in the docker container, so it is not usually run directly.
    """
    start_time_seconds = time.time()

    # turn off line buffering so that outputs don't get intermixed
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    setup()

    # Count test case total
    global test_case_total
    with open(codeval_file, "r") as infile:
        testcases = infile.readlines()
        in_crt_hw_block = False
        for testcase in testcases:
            stripped = testcase.strip()
            if stripped.startswith("CRT_HW"):
                in_crt_hw_block = not in_crt_hw_block
                continue
            if in_crt_hw_block:
                continue
            parts = testcase.split(" ", 1)
            tag = parts[0]
            if tag == "T" or tag == "HT" or tag == "TCMD":
                test_case_total += 1

    # Read testcases
    with open(codeval_file, "r") as infile:
        testcases = infile.readlines()
        parse_tags(testcases)

    check_test()

    end_time_seconds = time.time()
    print(f"took {end_time_seconds - start_time_seconds} seconds")
