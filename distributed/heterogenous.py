from canvasapi.assignment import Assignment
from typing import Tuple, List
import itertools
import tempfile
from multiprocessing import Process
from datetime import datetime
from commons import debug, error, errorWithException, info, get_config
from file_utils import download_attachment, unzip, set_acls, \
    copy_files_to_submission_dir
from .classes import DistributedTests
from .dist_utils import kill_stale_and_run_docker_container, \
    run_external_command, run_command_in_containers, run_test_command, \
    kill_running_docker_container, kill_stale_and_run_controller_container, \
    kill_running_controller_container
from .db import add_user_submission_if_not_present, \
    get_other_user_submissions, add_score_to_submissions, \
    deactivate_user_submission
from .containers import clear_running_containers, clear_ports_in_use


def run_heterogenous_tests(
        distributed_tests: DistributedTests,
        assignment_id: str,
        student_id: str,
        student_name: str,
        submitted_at: datetime,
        attachments: List[dict],
        canvas_assignment: Assignment
) -> Tuple[bool, str]:
    """Runs heterogenous tests"""
    passed = True
    out = b""

    # Clear the list of running containers
    clear_running_containers()
    clear_ports_in_use()

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
        'temp_dir': distributed_tests.temp_dir,
        'username': student_name.replace(" ", "_").lower()[:10]
    }

    # start a controller container to emulate host machine
    kill_stale_and_run_controller_container(
        docker_command=distributed_tests.docker_command,
        temp_dir=distributed_tests.temp_dir,
        ports_count=distributed_tests.ports_count_to_expose
    )

    # Run commands to setup tests
    for command in distributed_tests.tests_setup_commands:
        label, execution_style, command = command.split(" ", 2)
        if label not in ["ECMD", "ECMDT"]:
            errorWithException("Invalid command: %s" % command)
        success, resultlog = run_external_command(
            command=command,
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
        attachments=[{
            'display_name': a['display_name'],
            'url': a['url']
        } for a in attachments],
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

    combination_outputs = []

    for current_combination in combinations:
        current_combination_output = bytes("Test with submissions by: %s\n" % (
            ', '.join([student_name] +
                      list(x['student_name'] for x in current_combination))
        ), 'utf-8')
        debug("Running tests with submissions of users: %s" % (
            ', '.join(x['student_name'] for x in current_combination)
        ))
        for submission in current_combination:
            other_student_id = submission['student_id']
            if other_student_id not in student_id_to_temp_dir:
                temp_dir = tempfile.TemporaryDirectory(
                    prefix="codeval",
                    suffix="%s_submission" % other_student_id
                )
                temp_dir_name = temp_dir.name
                debug("Created temp dir for %s: %s" % (
                    submission['student_name'],
                    temp_dir_name
                ))
                debug("Setting ACLs for %s" % temp_dir_name)
                set_acls(temp_dir_name)
                _download_attachments(submission['attachments'], temp_dir_name)
                debug("Downloaded %s attachment(s) for %s" % (
                    str(len(submission['attachments'])), other_student_id
                ))
                copy_files_to_submission_dir(
                    distributed_tests.temp_fixed_dir, temp_dir_name)
                student_id_to_temp_dir[other_student_id] = temp_dir

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
                    temp_dir=student_id_to_temp_dir[submission['student_id']].name,
                    ports_count=distributed_tests.ports_count_to_expose
                )

            for command in test_group.commands:
                label, rest = command.split(" ", 1)
                if label in ["ECMD", "ECMDT"]:
                    execution_style, command = rest.split(" ", 1)
                    success, resultlog = run_external_command(
                        command=command,
                        is_sync=execution_style == "SYNC",
                        fail_on_error=label == "ECMDT",
                        placeholder_replacements=placeholder_replacements,
                    )
                    current_combination_output += resultlog
                    if not success and label == "ECMDT":
                        passed = False
                        break
                elif label in ["ICMD", "ICMDT"]:
                    execution_style, containers, command = rest.split(" ", 2)

                    container_names = []
                    current_username = placeholder_replacements['username']
                    containers_pr = {
                        **placeholder_replacements,
                        'username': []
                    }
                    if containers == '*':
                        for i in range(test_group.total_machines):
                            container_names.append("replica%d" % i)
                            if i == 0:
                                containers_pr['username'].append(
                                    current_username
                                )
                            else:
                                containers_pr['username'].append(
                                    current_combination[i-1]['student_name']
                                    .replace(" ", "_").lower()[:10]
                                )
                    else:
                        container_indexes = containers.split(',')
                        for index in container_indexes:
                            if int(index) >= test_group.total_machines:
                                errorWithException(
                                    "Invalid container index: %s" % index
                                )
                            container_names.append("replica%s" % index)
                            if index == '0':
                                containers_pr['username'].append(
                                    current_username
                                )
                            else:
                                containers_pr['username'].append(
                                    current_combination[int(index)-1]['student_name']
                                    .replace(" ", "_").lower()[:10]
                                )
                    success, resultlog = run_command_in_containers(
                        container_names=container_names,
                        command=command,
                        is_sync=execution_style == "SYNC",
                        fail_on_error=label == "ICMDT",
                        placeholder_replacements=containers_pr,
                    )
                    current_combination_output += resultlog
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
                    current_combination_output += resultlog
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
        _add_comment_to_user_submissions_in_parallel(
            student_ids=[x['student_id'] for x in current_combination],
            student_names=[x['student_name'] for x in current_combination],
            comment=current_combination_output.decode(),
            canvas_assignment=canvas_assignment
        )
        combination_outputs.append(current_combination_output)
        if passed:
            student_ids_passed = [student_id] + \
                [s['student_id'] for s in current_combination]
            if not get_config().dry_run:
                debug("Adding score to submissions in parallel: %s" %
                      str(student_ids_passed))
                Process(
                    target=add_score_to_submissions,
                    args=(assignment_id, student_ids_passed)
                ).start()
            else:
                debug("Would have incremented score to submissions in parallel: %s" %
                      str(student_ids_passed))
            # No need to go to next combination if current passed
            break

    out += b'\n'.join(combination_outputs)
    # Cleanup after all tests
    for command in distributed_tests.cleanup_commands:
        label, execution_style, command = command.split(" ", 2)
        if label not in ["ECMD", "ECMDT"]:
            error("Invalid command: %s" % command)
        success, resultlog = run_external_command(
            command=command,
            is_sync=execution_style == "SYNC",
            fail_on_error=label == "ECMDT",
            placeholder_replacements=placeholder_replacements,
        )
        out += resultlog
        if not success and label == "ECMDT":
            passed = False
            break
    kill_running_controller_container(wait_to_kill=True)
    debug("Finished tests with other submissions. Passed: %s" % passed)
    return passed, out


def mark_user_submission_as_not_active_if_present_in_parallel(
    assignment_id: int,
    student_id: str,
) -> None:
    """Marks user's submission as not active"""
    if get_config().dry_run:
        debug("would have marked submission by %s as not active if present" % student_id)
        return
    Process(
        target=deactivate_user_submission,
        args=(assignment_id, student_id)
    ).start()


def _download_attachments(attachments: List[dict], temp_dir: str) -> None:
    """Downloads attachments"""
    for attachment in attachments:
        attachment_path = download_attachment(temp_dir, attachment)
        unzip(attachment_path, temp_dir, delete=True)


def _add_comment_to_user_submissions_in_parallel(
    student_ids: List[str],
    student_names: List[str],
    comment: str,
    canvas_assignment: Assignment
) -> None:
    """Adds comments to users' submissions in a parallel process"""
    if get_config().dry_run:
        info("would have added comment to submissions by %s:\n%s" % (
            ', '.join(student_names), comment))
        return
    debug("Adding comment to submissions by %s:\n%s" % (
        ', '.join(student_names), comment))
    Process(
        target=_add_comment_to_user_submissions,
        args=(
            student_ids,
            comment,
            canvas_assignment
        )
    ).start()


def _add_comment_to_user_submissions(
    student_ids: List[str],
    comment: str,
    canvas_assignment: Assignment
) -> None:
    """Adds a comment to users' submissions"""
    for student_id in student_ids:
        # canvas doesn't like nulls in messages
        comment = comment.replace("\0", "\\0")
        canvas_assignment.get_submission(student_id).edit(comment={
            'text_comment': '[AG]\n\n' + comment
        })
