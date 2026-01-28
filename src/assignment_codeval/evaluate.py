#! /usr/bin/python3

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
expected_exit_code = -1
test_case_count = 0
test_case_hint = ""
test_case_total = 0
num_passed = 0
num_failed = 0
is_hidden_testcase = False
is_verbose = False
compilelog = []

###########################################################
# Specification Tags to Function Mapping
###########################################################


def compile_code(compile_command):
    """Specifies the command to compile the submission code

    Arguments:
        compile_command: the command to compile the submission code with

    Returns:
        None
    """
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


def check_function(args):
    """Will be followed by a function name and a list of files to check to ensure that the function
    is used by one of those files.

    Arguments:
        function_name: the function name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    check_test()
    args = args.split()
    function_name = args[0]
    files = args[1:]

    # Match:
    #  [1] start of line OR non-identifier character
    #  [2] function name
    #  [3] optional whitespace
    #  [4] opening parenthesis (function call)
    regex = rf'(^|[^[:alnum:]_]){function_name}[[:space:]]*\('

    # Strip comments, then search
    cmd = (
        "sed -E "
        "'"
        "s://.*$::g; " # C/C++ single-line comments
        "s:#.*$::g; " # Python single-line comments
        ":a; /\\/\\*/{N; s:/\\*.*?\\*/::g; ba}"
        "' "
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
        print(f"Not using {function_name} FAILED")
    else:
        print(f"Used {function_name} PASSED")

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
    """Will be followed by a function name and a list of files to check to ensure that the function
    is not used by any of those files.

    Arguments:
        function_name: the funcion name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    check_test()
    args = args.split()
    function_name = args[0]
    files = args[1:]

    # Surpress output
    function_popen = subprocess.Popen(
        ["grep", f"[^[:alpha:]]{function_name}[[:space:]]*("] + files,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    function_popen.communicate()
    if function_popen.returncode:
        print(f"used{function_name} PASSED")
    else:
        print(f"not using {function_name} FAILED")


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


def timeout(timeout_sec):
    """Specifies the time limit in seconds for a test case to run. Defaults to 20 seconds.

    Arguments:
        timeout_sec: time limit in seconds for a test case to run

    Returns:
        None
    """
    global timeout_val
    timeout_val = float(timeout_sec)


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
    "X": exit_code,
    "SS": start_server,
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
    tag_pattern = r"([A-Z_]+)\s+(.*)"
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


def check_test():
    global test_args
    if test_args == "":
        return

    print(f"Test case {test_case_count} of {test_case_total}")
    passed = True

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

    # Difflog handling
    with open(get_testing_path("difflog"), "w") as outfile:
        diff_popen = subprocess.Popen(
            f"diff -U1 -a ./{TESTING_DIR}/youroutput ./{TESTING_DIR}/expectedoutput | cat -te | head -22",
            shell=True,
            stdout=outfile,
            stderr=outfile,
            text=True,
        )
        diff_popen.communicate()

    # Append to difflog second time around
    with open(get_testing_path("difflog"), "a") as outfile:
        diff_popen = subprocess.Popen(
            f"diff -U1 -a ./{TESTING_DIR}/yourerror ./{TESTING_DIR}/expectederror | cat -te | head -22",
            shell=True,
            stdout=outfile,
            stderr=outfile,
            text=True,
        )
        diff_popen.communicate()

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

        cleanup()

        # Exit program after failed test case
        sys.exit(2)

    # reinitialize test variables and files here
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

    # cleanup
    cleanup()

    end_time_seconds = time.time()
    print(f"took {end_time_seconds - start_time_seconds} seconds")
