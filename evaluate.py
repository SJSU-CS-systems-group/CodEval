import click
import re
import subprocess
import threading
import time

###########################################################
# Globals
###########################################################


cmps = []
timeout_val = 20
expected_exit_code = 0
test_case_hint = ""

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
    pass


def compile_timeout(timeout_sec):
    """Timeout in seconds for the compile command to run

    Arguments:
        timeout: the timeout for the compile command

    Returns:
        None
    """
    raise NotImplementedError()


def run_script(script_file):
    """Specifies the script to use to evaluate the specification file. Defaults to evaluate.sh.

    Arguments:
        script_file: the script file to run to evaluate the specification file

    Returns:
        None
    """
    raise NotImplementedError()


def download_zip(*zip_files):
    """Will be followed by zip files to download from Canvas to use when running the test cases.

    Arguments:
        *zip_files: zip files to be downloaded from Canvas

    Returns:
        None
    """
    raise NotImplementedError()


def check_function(function_name, *files):
    """Will be followed by a function name and a list of files to check to ensure that the function
    is used by one of those files.

    Arguments:
        function_name: the function name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    pass


def check_not_function(function_name, *files):
    """Will be followed by a function name and a list of files to check to ensure that the function
    is not used by any of those files.

    Arguments:
        function_name: the funcion name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    pass


def run_command(command):
    """Will be followed by a command to run.

    Arguments:
        command: the command to run

    Returns:
        None
    """
    pass


def run_command_noerror(command):
    """Will be followed by a command to run, evaluation fails if the command exits with an error.

    Arguments:
        command: the command to run

    Returns:
        None
    """
    pass


def compare(file1, file2):
    """Will be followed by two files to compare.

    Arguments:
        file1: The first file to compare
        file2: The second file to compare

    Returns:
        None
    """
    cmps.append(file1)
    cmps.append(file2)


def test_case(test_case_command):
    """Will be followed by the command to run to test the submission.

    Arguments:
        test_case_command: the command to run the submission

    Returns:
        None
    """
    pass


def supply_input(*inputs):
    """Specifies the input for a test case.

    Arguments:
        *inputs: inputs to be used for test case

    Returns:
        None
    """
    with open('fileinput', 'a') as outfile:
        outfile.write(' '.join(inputs))


def supply_input_file(input_file):
    """Specifies the input for a test case read from a file.

    Arguments:
        input_file: file to get input for test case from

    Returns:
        None
    """
    with open(input_file, 'r') as infile:
        input_lines = infile.readlines()

    with open('fileinput', 'a') as outfile:
        outfile.writelines(input_lines)


def check_output(*outputs):
    """Specifies the expected output for a test case.

    Arguments:
        *outputs: outputs to be used for test case

    Returns:
        None
    """
    with open('expectedoutput', 'a') as outfile:
        outfile.write(' '.join(outputs))


def check_output_file(output_file):
    """Specifies the expected output for a test case read from a file.

    Arguments:
        output_file: file to get output for test case from

    Returns:
        None
    """
    with open(output_file, 'r') as infile:
        output_lines = infile.readlines()

    with open('expectedoutput', 'a') as outfile:
        outfile.writelines(output_lines)


def check_error(*error_output):
    """Specifies the expected error output for a test case.

    Arguments:
        error_output: expected error output for a test case

    Returns:
        None
    """
    with open('expectederror', 'a') as outfile:
        outfile.write(' '.join(error_output))


def hint(*hints):
    """Hint

    Arguments:
        *hints: hints to be associated with test case

    Returns:
        None
    """
    global test_case_hint
    test_case_hint = ' '.join(hints)


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
    expected_exit_code = float(test_case_exit_code)


def start_server(timeout_sec, kill_timeout_sec, server_cmd):
    """Command containing timeout (wait until server starts), kill timeout (wait to kill the server),
    and the command to start a server

    Arguments:
        timeout_sec: timeout in seconds to wait for server to start
        kill_timeout_sec: timeout in seconds to wait until killing the server
        server_cmd: command to run to start the server

    Returns:
        None
    """
    print(f'Starting server with command: {server_cmd} and sleeping for: {timeout_sec}. Will kill server '
          f'after {kill_timeout_sec} seconds.')

    # Send output to compile log in background
    with open('compilelog', 'w') as outfile:
        server_popen = subprocess.Popen(server_cmd, stdout=outfile, stderr=outfile, text=True)

    print(f'Server pid: {server_popen.pid}. Sleeping for {timeout_sec} seconds.')
    # Block for timeout_sec so that server can start
    time.sleep(float(timeout_sec))

    # Kill the server after the timeout
    def kill_server(pid):
        print(f'Killing {pid}')
        subprocess.Popen(f'kill -9 {pid}', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    kill_timer = threading.Timer(float(kill_timeout_sec), kill_server, *[server_popen.pid])
    kill_timer.daemon = True
    kill_timer.start()


"""
Here is where the tags are mapped to functions.
Any tags that are added or changed must be modified here.
Assume that everything will be passed to these functions as a string, account for
this in the function itself.
"""
tag_func_map = {
    'C': compile_code,
    'CTO': compile_timeout,
    'RUN': run_script,
    'Z': download_zip,
    'CF': check_function,
    'NCF': check_not_function,
    'CMD': run_command,
    'TCMD': run_command_noerror,
    'CMP': compare,
    'T': test_case,
    'I': supply_input,
    'IF': supply_input_file,
    'O': check_output,
    'OF': check_output_file,
    'E': check_error,
    'HINT': hint,
    'TO': timeout,
    'X': exit_code,
    'SS': start_server
}


@click.command()
def evaluate():
    start_time_seconds = time.time()

    # Read testcases
    with open('testcases.txt', 'r') as infile:
        testcases = infile.readlines()
        parse_tags(testcases)

    end_time_seconds = time.time()
    print(f'took {end_time_seconds - start_time_seconds} seconds')


def parse_tags(tags: list[str]):
    """Given file open in read mode, parses and executes tags

    Arguments:
        tags (list[str]): list of tags and arguments to be parsed and executed

    Returns:
        None
    """
    tag_pattern = r'([A-Z]+) (.*)'
    for tag_line in tags:
        tag_match = re.match(tag_pattern, tag_line)
        tag = tag_match.group(1)
        args = tag_match.group(2).split(' ')

        # Execute function based on tag-function mapping
        try:
            tag_func_map[tag](*args)
        except KeyError:
            print(f'Invalid tag {tag} for parsing.')
        except (TypeError, ValueError):
            print(f'Invalid arguments for tag {tag}')
