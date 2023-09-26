#! /usr/bin/python3

import os
import re
import subprocess
import sys
import threading
import time
import click


###########################################################
# Globals
###########################################################


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
    with open('compilelog', 'w') as outfile:
        compile_popen = subprocess.Popen(compile_command, stdout=outfile, stderr=outfile, text=True)

    compile_popen.communicate(compile_popen)
    if compile_popen.returncode:
        with open('compilelog', 'r') as infile:
            compile_log = infile.readlines

        # Print head of compile log
        for line in compile_log[:10]:
            print(line)

        print('...')

        # Print tail of compile log
        for line in compile_log[-10:]:
            print(line)

        sys.exit(1)


def check_function(function_name, *files):
    """Will be followed by a function name and a list of files to check to ensure that the function
    is used by one of those files.

    Arguments:
        function_name: the function name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    check_test()

    # Surpress output
    function_popen = subprocess.Popen([f'grep "[^[:alpha:]]{function_name}[[:space:]]*("',
                                       ' '.join(files)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    function_popen.communicate()
    if function_popen.returncode:
        print(f'not using {function_name} FAILED')
    else:
        print(f'used{function_name} PASSED')


def check_not_function(function_name, *files):
    """Will be followed by a function name and a list of files to check to ensure that the function
    is not used by any of those files.

    Arguments:
        function_name: the funcion name to check files for usage of
        *files: the files to check for the function name

    Returns:
        None
    """
    check_test()

    # Surpress output
    function_popen = subprocess.Popen([f'grep "[^[:alpha:]]{function_name}[[:space:]]*("',
                                       ' '.join(files)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    function_popen.communicate()
    if function_popen.returncode:
        print(f'used{function_name} PASSED')
    else:
        print(f'not using {function_name} FAILED')


def run_command(command):
    """Will be followed by a command to run.

    Arguments:
        command: the command to run

    Returns:
        None
    """
    check_test()

    # Execute without surpressing output
    command_popen = subprocess.Popen(command)
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
    print(f'Test case count {test_case_count} of {test_case_total}')

    # Execute without surpressing output
    command_popen = subprocess.Popen(command)
    command_popen.communicate()

    if command_popen.returncode:
        print('FAILED')
        for file in os.listdir('evaluationLogs'):
            with open(file, 'r') as infile:
                file_lines = infile.readlines()

            # Print entire file
            print('\n'.join(file_lines))

        # Exit entire program with error
        sys.exit(1)
    else:
        print('PASSED')


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
    check_test()

    # Clear hint
    global hint
    hint = ""

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
    global hint
    hint = ""

    # Set new test case command
    global test_args
    test_args = test_case_command

    # Increment test cases
    global test_case_count
    test_case_count += 1

    # Set hidden test case
    global test_case_hidden
    test_case_hidden = True


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
    'CF': check_function,
    'NCF': check_not_function,
    'CMD': run_command,
    'TCMD': run_command_noerror,
    'CMP': compare,
    'T': test_case,
    'HT': test_case_hidden,
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

    # Count test case total
    global test_case_total
    with open('testcases.txt', 'r') as infile:
        testcases = infile.readlines()
        for testcase in testcases:
            if testcase.split(" ")[0] == "T" or testcase.split(" ")[0] == "HT":
                test_case_total += 1

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


def parse_diff(diff_lines: list[str]):
    """Given output from diff command, parse lines into console

    Arguments:
        parse_diff (list[str]): list of lines as output from diff command

    Returns:
        None
    """
    # Directly write into logOfDiff rather than use redirection
    with open('evaluationLogs/logOfDiff', 'w') as outfile:
        for line in diff_lines:
            first_word = line.split(' ')[:2]
            first_character = first_word[0]

            if first_character != '@':
                # Lines present in your output but not present in expected
                if first_character == '-' and first_word[:3] == '---':
                    student_output_file = line[3:-37]
                    outfile.write(f'Your output file: {student_output_file}')

                # Lines present in expected output but not in yours
                elif first_character == '+' and first_word[:3] == '+++':
                    expected_output_file = line[3:-37]
                    outfile.write(f'Expected output file: {expected_output_file}')

                # Catch rest
                else:
                    outfile.write(line)


def check_test():
    if test_args == "":
        return

    print(f'Test case {test_case_count} of {test_case_total}')
    passed = True

    with open('fileinput', 'r') as fileinput, \
         open('youroutput', 'w') as youroutput, \
         open('yourerror', 'w') as yourerror:
        test_exec = subprocess.Popen(test_args, stdin=fileinput, stdout=youroutput, stderr=yourerror)

    # Timeout handling
    try:
        test_exec.communicate(timeout=timeout_val)
    except TimeoutError:
        print(f'Took more than {timeout_val} seconds to run. FAIL')
        passed = False

    # Difflog handling
    with open('difflog', 'w') as outfile:
        diff_popen = subprocess.Popen('diff -U1 -a ./youroutput ./expectedoutput | cat -te | head -22',
                                      stdout=outfile, stderr=outfile, text=True)
        diff_popen.communicate()

    # Append to difflog second time around
    with open('difflog', 'a') as outfile:
        diff_popen = subprocess.Popen('diff -U1 -a ./yourerror ./expectederror | cat -te | head -22',
                                      stdout=outfile, stderr=outfile, text=True)
        diff_popen.communicate()

    # Now read all the lines to accumulate both diffs
    with open('difflog', 'r') as infile:
        diff_lines = infile.readlines()

    if len(diff_lines):
        passed = False
        parse_diff(diff_lines)

    # Exit code handling
    if expected_exit_code != -1 and test_exec.returncode != expected_exit_code:
        passed = False
        print(f'    Exit Code failure: expected {expected_exit_code} got {test_exec.returncode}')

    # Compare files handling, do not surpress output
    for files in cmps:
        cmd_popen = subprocess.Popen(['cmp', files])
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
            print('    Test Case is Hidden')
            if hint:
                print(f'HINT: {hint}')
        else:
            if hint:
                print(f'HINT: {hint}')

            # Cleanup
            print(f'    Command ran: {test_args}')
            for file in os.listdir('evaluationlogs'):
                with open(file, 'r') as infile:
                    file_lines = infile.readlines()

                # Print entire file
                print('\n'.join(file_lines))

        # Exit program after failed test case
        sys.exit(2)


if __name__ == '__main__':
    evaluate()
