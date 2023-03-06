from typing import Tuple, List
import itertools
import tempfile
from datetime import datetime
from commons import *
from utils import *
from .classes import DistributedTests
from .utils import *
from .db import *


def run_heterogenous_tests(
        distributed_tests: DistributedTests,
        assignment_id: str,
        student_id: str,
        student_name: str,
        submitted_at: datetime,
        attachments: List[dict],
) -> Tuple[bool, str]:
    """Runs heterogenous tests"""
    passed = True
    out = b""

    # Clear the list of running containers
    clear_running_containers()

    debug("Running tests with other users' submissions")
    has_heterogenous_tests = False

    test_group: DistributedTests.TestGroup
    for test_group in distributed_tests.test_groups:
        if not test_group.heterogenous:
            continue
        has_heterogenous_tests = True
        out += b"Tests with other users' submissions:\n"
        break

    if not has_heterogenous_tests:
        return passed, out

    placeholder_replacements = {
        'host_ip': distributed_tests.host_ip,
    }

    # Run commands to setup tests
    for command in distributed_tests.tests_setup_commands:
        label, execution_style, bash_command = command.split(" ", 2)
        if label not in ["ECMD", "ECMDT"]:
            error("Invalid command: %s" % command)
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

    # add user's own submission to the pool if not present
    add_user_submission_if_not_present(
        assignment_id=assignment_id,
        student_id=student_id,
        student_name=student_name,
        submitted_at=submitted_at,
        attachments=attachments,
    )

    other_submissions = get_other_user_submissions(
        assignment_id=assignment_id,
        current_user_id=student_id
    )
    debug("Found submissions of users: %s" % (
        ', '.join(x['student_name'] for x in other_submissions)
    ))
    if other_submissions is None or \
            len(other_submissions) < test_group.total_machines - 1:
        out += b"Could not find enough submissions to run tests." + \
            b" Added to the pool and waiting for others.\n"
        return passed, out

    combinations = itertools.combinations(other_submissions,
                                          test_group.total_machines-1)

    # Sort combinations by total score (in descending order) and submission
    # time (in ascending order)
    combinations = sorted(
        combinations,
        key=lambda x: (
            sum(s['score'] for s in x),
            sum(-1 * int(s['submitted_at'].strftime("%s")) for s in x)
        ),
        reverse=True
    )

    student_id_to_temp_dir = {}

    for current_combination in combinations:
        debug("Running tests with submissions of users: %s" % (
            ', '.join(x['student_name'] for x in current_combination)
        ))
        for submission in current_combination:
            student_id = submission['student_id']
            if student_id not in student_id_to_temp_dir:
                temp_dir = tempfile.TemporaryDirectory(
                    prefix="codeval",
                    suffix="%s_submission" % student_id
                )
                temp_dir_name = temp_dir.name
                debug("Created temp dir for %s: %s" % (
                    submission['student_name'],
                    temp_dir_name
                ))
                debug("Setting ACLs for %s" % temp_dir_name)
                set_acls(temp_dir_name)
                download_attachments(submission['attachments'], temp_dir_name)
                debug("Downloaded %s attachment(s) for %s" % (
                    str(len(submission['attachments'])), student_id
                ))
                copy_files_to_submission_dir(
                    distributed_tests.temp_fixed_dir, temp_dir_name)
                student_id_to_temp_dir[student_id] = temp_dir

        placeholder_replacements = {
            'host_ip': distributed_tests.host_ip,
            'temp_dir': distributed_tests.temp_dir
        }

        current_testcase_number = 0

        # Run tests in each test group
        test_group: DistributedTests.TestGroup
        for test_group in distributed_tests.test_groups:
            if not test_group.heterogenous:
                continue
            current_group_testcase_number = 0

            # restarting user's own submission for each combination
            kill_stale_and_run_docker_container(
                container_name="replica0",
                docker_command=distributed_tests.docker_command,
                temp_dir=distributed_tests.temp_dir,
                ports_count=distributed_tests.ports_count_to_expose
            )
            debug("[Re]started user's own submission")

            for submission_idx, submission in enumerate(current_combination):
                debug("[Re]starting %s's submission" %
                      submission['student_name'])
                kill_stale_and_run_docker_container(
                    container_name="replica%d" % (submission_idx + 1),
                    docker_command=distributed_tests.docker_command,
                    temp_dir=student_id_to_temp_dir[student_id].name,
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
                    success, resultlog = run_command_in_containers(
                        container_names=container_names,
                        command=bash_command,
                        is_sync=execution_style == "SYNC",
                        fail_on_error=label == "ICMDT",
                        placeholder_replacements=placeholder_replacements,
                    )
                    out += resultlog
                    if not success and label == "ICMDT":
                        passed = False
                        break
                elif label == "TESTCMD":
                    current_testcase_number += 1
                    current_group_testcase_number += 1
                    command = rest
                    command = command.replace(
                        "HOST_IP", distributed_tests.host_ip)
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
                kill_running_docker_container(
                    "replica%d" % i, wait_to_kill=True)
            debug("Killed all running containers")

            # No need to go to next test group if current failed
            if not passed:
                break
        if passed:
            out += bytes("Tests passed with submissions by users: %s" % (
                ', '.join(x['student_name'] for x in current_combination)
            ), 'utf-8')
            add_score_to_submissions(
                assignment_id=test_group.assignment_id,
                student_ids=[s['student_id'] for s in current_combination]
            )
            # No need to go to next combination if current passed
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

    debug("Finished tests with other submissions. Passed: %s" % passed)
    return passed, out


# def create_temp_dir_for_student_id(student_id: str) -> str:
#     """Creates a temporary directory for a user"""
#     return


def download_attachments(attachments: List[dict], temp_dir: str) -> None:
    """Downloads attachments"""
    for attachment in attachments:
        attachment_path = download_attachment(temp_dir, attachment)
        unzip(attachment_path, temp_dir, delete=True)
