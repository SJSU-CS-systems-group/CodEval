import subprocess
import shutil

###########################################################
#  Specification Tags to Function Mapping
###########################################################


def compile_code():
    """Specifies the command to compile the submission code

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def compile_timeout():
    """Timeout in seconds for the compile command to run

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def run_script():
    """Specifies the script to use to evaluate the specification file. Defaults to evaluate.sh.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def download_zip():
    """Will be followed by zip files to download from Canvas to use when running the test cases.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def check_function():
    """Will be followed by a function name and a list of files to check to ensure that the function
    is used by one of those files.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def check_not_function():
    """Will be followed by a function name and a list of files to check to ensure that the function
    is not used by any of those files.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def run_command():
    """Will be followed by a command to run.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def run_command_noerror():
    """Will be followed by a command to run, evaluation fails if the command exits with an error.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def compare():
    """Will be followed by two files to compare.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def test_case():
    """Will be followed by the command to run to test the submission.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def supply_input():
    """Specifies the input for a test case.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def supply_input_file():
    """Specifies the input for a test case read from a file.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def check_output():
    """Specifies the expected output for a test case.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def check_output_file():
    """Specifies the expected output for a test case read from a file.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def check_error():
    """Specifies the expected error output for a test case.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def hint():
    """Hint

    Arguments:
        argument: description

    Returns:
        return_description
    """


def timeout():
    """Specifies the time limit in seconds for a test case to run. Defaults to 20 seconds.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def exit_code():
    """Specifies the expected exit code for a test case. Defaults to zero.

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


def start_server():
    """Command containing timeout (wait until server starts), kill timeout (wait to kill the server),
    and the command to start a server

    Arguments:
        argument: description

    Returns:
        return_description
    """
    pass


"""
Here is where the tags are mapped to functions.
Any tags that are added or changed must be modified here.
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


# This is a seperate command, use click interface
# Keep as one file
def evaluate():
    pass


# def check_test():

#     print(f'Test Case {} of {}:')
