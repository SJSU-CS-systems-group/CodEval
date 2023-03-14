from typing import List, Tuple
from commons import *
from .classes import DistributedTests
from .dist_utils import *


def run_homogenous_tests(
    distributed_tests: DistributedTests,
    student_name: str,
) -> Tuple[bool, bytes]:
    """Run homogenous tests"""
    passed = True
    out = b""

    # Clear the list of running containers
    clear_running_containers()

    debug("Running tests with user's own submission")
    current_testcase_number = 0
    has_homogenous_tests = False

    student_container_name = student_name.replace(" ", "_").lower()[:10]

    placeholder_replacements = {
        'host_ip': distributed_tests.host_ip,
        'temp_dir': distributed_tests.temp_dir,
        'username': student_container_name
    }

    # Run commands to setup tests
    for command in distributed_tests.tests_setup_commands:
        label, execution_style, bash_command = command.split(" ", 2)
        if label not in ["ECMD", "ECMDT"]:
            error("Invalid command: %s" % command, True)
        success, resultlog = run_external_command(
            bash_command=bash_command,
            is_sync=execution_style == "SYNC",
            fail_on_error=label == "ECMDT",
            placeholder_replacements=placeholder_replacements,
        )
        out += resultlog
        if not success and label == "ECMDT":
            passed = False
            break

    if passed:
        # Run tests in each test group
        test_group: DistributedTests.TestGroup
        for test_group in distributed_tests.test_groups:
            if not test_group.homogenous:
                continue
            if not has_homogenous_tests:
                has_homogenous_tests = True
                out += b"Tests with your own submission:\n"
            current_group_testcase_number = 0

            for i in range(test_group.total_machines):
                kill_stale_and_run_docker_container(
                    container_name="replica%d" % i,
                    docker_command=distributed_tests.docker_command,
                    temp_dir=distributed_tests.temp_dir,
                    ports_count=distributed_tests.ports_count_to_expose
                )

            for command in test_group.commands:
                label, rest = command.split(" ", 1)
                if label in ["ECMD", "ECMDT"]:
                    execution_style, bash_command = rest.split(" ", 1)
                    success, resultlog = run_external_command(
                        bash_command=bash_command,
                        is_sync=execution_style == "SYNC",
                        fail_on_error=label == "ECMDT",
                        placeholder_replacements=placeholder_replacements,
                    )
                    out += resultlog
                    if not success and label == "ECMDT":
                        passed = False
                        break
                elif label in ["ICMD", "ICMDT"]:
                    execution_style, bash_command = rest.split(" ", 1)

                    container_names = []
                    for i in range(test_group.total_machines):
                        container_names.append("replica%d" % i)
                    containers_pr = {
                        **placeholder_replacements,
                        'username': [placeholder_replacements['username']] * \
                            test_group.total_machines
                    }
                    success, resultlog = run_command_in_containers(
                        container_names=container_names,
                        command=bash_command,
                        is_sync=execution_style == "SYNC",
                        fail_on_error=label == "ICMDT",
                        placeholder_replacements=containers_pr,
                    )
                    out += resultlog
                    if not success and label == "ICMDT":
                        passed = False
                        break
                elif label == "TESTCMD":
                    current_testcase_number += 1
                    current_group_testcase_number += 1
                    command = rest
                    command = command.replace("HOST_IP", distributed_tests.host_ip)
                    passed, resultlog = run_test_command(
                        command=command,
                        hint=test_group.test_hints[current_group_testcase_number-1],
                        placeholder_replacements=placeholder_replacements,
                        test_number=current_testcase_number,
                        testcases_count=distributed_tests.testcases_count,
                    )
                    out += resultlog
                    if not passed:
                        break

            # Cleanup before next test group
            for i in range(test_group.total_machines):
                kill_running_docker_container("replica%d" % i, wait_to_kill=True)
            debug("Killed all running containers")

            # No need to go to next test group if current failed
            if not passed:
                break

    # Cleanup after all tests
    for command in distributed_tests.cleanup_commands:
        label, execution_style, bash_command = command.split(" ", 2)
        if label not in ["ECMD", "ECMDT"]:
            error("Invalid command: %s" % command, raise_exception=False)
        success, resultlog = run_external_command(
            bash_command=bash_command,
            is_sync=execution_style == "SYNC",
            fail_on_error=label == "ECMDT",
            placeholder_replacements=placeholder_replacements,
        )
        out += resultlog
        if not success and label == "ECMDT":
            passed = False
            break

    debug("Finished tests with user's own submission. Passed: %s" % passed)
    return passed, out
