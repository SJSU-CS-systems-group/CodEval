from commons import *
from .classes import DistributedTests
from .homogenous import run_homogenous_tests


def run_distributed_tests(docker_command, host_ip, temp_dir, testcase_file):
    debug("Docker command before: %s" % docker_command)
    debug("Host ip: %s" % host_ip)
    debug("Temp directory: %s" % temp_dir)
    debug("Testcase file: %s" % testcase_file)

    distributed_tests = DistributedTests(
        docker_command,
        host_ip,
        temp_dir,
        testcase_file
    )

    out = b"\nRunning Distributed Tests...\n"

    with open(testcase_file, "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line_args = line.split(" ")
            if line_args[0] == "TESTCMD":
                distributed_tests.testcases_count += 1

    # Populating DistributedTests object

    # Initially, test spec file has standalone test cases. Need to ignore them
    reading_distributed_testcases = False

    current_test_group = None
    current_testcase_count = 0
    in_cleanup = False
    try:
        with open(testcase_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line_args = line.split(" ")

                if line_args[0] == "--DT--":
                    reading_distributed_testcases = True
                    continue
                if line_args[0] == "#":
                    continue
                if not reading_distributed_testcases:
                    continue

                if in_cleanup and line_args[0] not in ["ECMD", "ECMDT"]:
                    error("Cleanup commands must be at the end of spec file")

                if line_args[0] == "PORTS":
                    distributed_tests.ports_count_to_expose = int(line_args[1])
                elif line_args[0] in ["ECMD", "ECMDT"]:
                    if current_test_group is not None:
                        current_test_group.commands.append(line)
                    elif in_cleanup:
                        distributed_tests.cleanup_commands.append(line)
                    else:
                        distributed_tests.tests_setup_commands.append(line)
                elif line_args[0] == "DTC":
                    total_machines = int(line_args[1])
                    homogenous = "HOM" in line_args[2:]
                    heterogenous = "HET" in line_args[2:]
                    if current_test_group is not None:
                        distributed_tests.add_test_group(current_test_group)
                    current_test_group = DistributedTests.TestGroup(
                        total_machines, homogenous, heterogenous)
                elif current_test_group is None:
                    error("Unexpected %s before DTC in test spec file" %
                          line_args[0])
                if line_args[0] in ["ICMD", "ICMDT"]:
                    current_test_group.commands.append(line)
                elif line_args[0] == "HINT":
                    hint = " ".join(line_args[1:])
                    current_test_group.test_hints.append(hint)
                elif line_args[0] == "TESTCMD":
                    current_testcase_count += 1
                    current_test_group.commands.append(line)
                    if current_testcase_count > len(current_test_group.test_hints):
                        current_test_group.test_hints.append(None)
                elif line_args[0] == "--DTCLEAN--":
                    if current_test_group is not None:
                        distributed_tests.add_test_group(current_test_group)
                        current_test_group = None
                    in_cleanup = True

        if current_test_group is not None:
            distributed_tests.add_test_group(current_test_group)
            current_test_group = None

        # Running tests
        passed, resultlog = run_homogenous_tests(distributed_tests)
        out += resultlog
    except EnvironmentError as e:
        out += bytes(str(e) + "\n", "utf-8")
    return out
