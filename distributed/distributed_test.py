from commons import *
import subprocess
import random

class DistributedTest:

    def __init__(self, total_machines, homogenous, heterogenous) -> None:
        self.total_machines = total_machines
        self.homogenous = homogenous
        self.heterogenous = heterogenous
        self.pre_commands = []
        self.test_commands = []
        self.test_hints = []
        self.post_commands = []

    def _append_pre_command(self, command):
        self.pre_commands.append(command)

    def _append_test_command(self, command, hint=None):
        self.test_commands.append(command)
        self.test_hints.append(hint)

    def _append_post_command(self, command):
        self.post_commands.append(command)

port_range = (10000, 20000)

ports_in_use = set()
containers_data = {}

distributed_tests = []


def run_distributed_tests(docker_command, host_ip, temp_dir, testcase_file):
    debug("Docker command before: %s" % docker_command)
    debug("Host ip: %s" % host_ip)
    debug("Temp directory: %s" % temp_dir)
    debug("Testcase file: %s" % testcase_file)

    out = b"\n Running Distributed Tests... \n"

    testcases_count = 0
    with open(testcase_file, "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line_args = line.split(" ")
            if line_args[0] == "TESTCMD":
                testcases_count += 1

    ports_count = []
    reading_distributed_testcases = False
    current_distributed_testcase = None
    current_testcase_count = 0
    in_cleanup = False
    try:
        with open(testcase_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                debug("Line: %s" % line)
                if not line:
                    continue
                line_args = line.split(" ")

                if line_args[0] == "--DT--":
                    reading_distributed_testcases = True
                    continue
                if not reading_distributed_testcases:
                    continue

                if in_cleanup and line_args[0] not in ["DTCLEAN", "ECMD", "ECMDT"]:
                    error("Cleanup commands must be at the end of the testcase file")

                if line_args[0] == "PORTS":
                    ports_count = int(line_args[1])
                elif line_args[0] in ["ECMD", "ECMDT"]:
                    command = " ".join(line_args[2:])
                    command = command.replace("HOST_IP", host_ip)
                    command = command.replace("TEMP_DIR", temp_dir)
                    debug("Running %s external command: %s" % (line_args[1], command))
                    run_command(command, line_args[1] == "SYNC", line_args[0] == "ECMDT")
                elif line_args[0] == "DTC":
                    total_machines = int(line_args[1])
                    homogenous = "HOM" in line_args[2:]
                    heterogenous = "HET" in line_args[2:]
                    current_distributed_testcase = DistributedTest(total_machines, homogenous, heterogenous)
                    debug("Starting docker containers")
                    for i in range(total_machines):
                        kill_if_running_and_start_docker_container(i, docker_command, temp_dir, ports_count)
                    debug("Started docker containers")
                else:
                    if current_distributed_testcase is None:
                        error("Unexpected %s before DTC in testcase file" % line_args[0])

                if line_args[0] in ["ICMD", "ICMDT"]:
                    command = " ".join(line_args[2:])
                    command = command.replace("HOST_IP", host_ip)
                    if len(current_distributed_testcase.test_commands) == 0:
                        current_distributed_testcase.pre_commands.append(command)
                    else:
                        current_distributed_testcase.post_commands.append(command)
                    for i in range(total_machines):
                        replica_command = command
                        for j in range(ports_count):
                            replica_command = replica_command.replace("PORT_%d" % j, str(containers_data["replica%d" % i]["ports"][j]))
                        debug("Replica command: %s for replica%s" % (replica_command, str(i)))
                        run_command_in_container("replica%d" % i, replica_command, line_args[1] == "SYNC", line_args[0] == "ICMDT")
                elif line_args[0] == "HINT":
                    hint = " ".join(line_args[1:])
                    current_distributed_testcase.test_hints.append(hint)
                elif line_args[0] == "TESTCMD":
                    current_testcase_count += 1
                    command = " ".join(line_args[1:])
                    command = command.replace("HOST_IP", host_ip)
                    command = command.replace("TEMP_DIR", temp_dir)
                    while 'PEER_HP' in command:
                        start_index = command.index('PEER_HP')
                        end_index = start_index + 8
                        while end_index < len(command) and command[end_index].isdigit():
                            end_index += 1
                        max_hostport_peers_count = int(command[start_index + 8:end_index])
                        hostport_peers = []
                        for i in range(min(max_hostport_peers_count, len(containers_data))):
                            hostport_peers.append(host_ip + ':' + str(containers_data["replica%d" % i]["ports"][0]))
                        command = command[:start_index] + ",".join(hostport_peers) + command[end_index+1:]
                            
                    current_distributed_testcase.test_commands.append(command)
                    if len(current_distributed_testcase.test_commands) > len(current_distributed_testcase.test_hints):
                        current_distributed_testcase.test_hints.append(None)
                    debug("Running test command: %s" % command)
                    result = run_command(command, True, False)
                    if result.returncode != 0:
                        message = "Distributed Test %s of %s: FAILED" % (str(current_testcase_count), str(testcases_count))
                        out += bytes(message + "\n", "utf-8")
                        if current_distributed_testcase.test_hints[-1] is not None:
                            out += bytes("Hint: " + current_distributed_testcase.test_hints[-1] + "\n", "utf-8")
                        out += bytes("\n".join(result.stdout.decode("utf-8").split("\n")[-10:]) + "\n", "utf-8")
                        return out
                    else:
                        message = "Distributed Test %s of %s: PASSED" % (str(current_testcase_count), str(testcases_count))
                        out += bytes(message + "\n", "utf-8")
                        info(message)
                elif line_args[0] == "CLEANUP":
                    in_cleanup = True
        if current_distributed_testcase is not None:
            distributed_tests.append(current_distributed_testcase)
            kill_running_docker_containers()
            debug("Killed docker containers")
    except EnvironmentError as e:
        out += bytes(str(e) + "\n", "utf-8")
    finally:
        return out

def kill_if_running_and_start_docker_container(machine_number, docker_command, temp_dir, ports_count):
    container_name = "replica%d" % machine_number
    ports_subcommand = ""
    containers_data[container_name] = {"ports": []}
    for i in range(ports_count):
        port = get_free_port()
        containers_data[container_name]["ports"].append(port)
        ports_subcommand += "-p %d:%d " % (port, port)
    docker_command = docker_command.replace("NAME", container_name)
    docker_command = docker_command.replace("SUBMISSIONS", temp_dir)
    docker_command = docker_command.replace("PORTS", ports_subcommand)

    debug("Docker command after: %s" % docker_command)
    _kill_docker_container(container_name)
    result = run_command(docker_command, True, False)
    debug("Docker command result: %s" % result.stdout.decode("utf-8"))
    if result.returncode != 0:
        error("Docker command failed: %s" % result.stdout.decode("utf-8"))
    containers_data[container_name]["id"] = result.stdout.decode("utf-8").strip()

def kill_running_docker_containers():
    for container_name in containers_data:
        container_id = containers_data[container_name]["id"]
        _kill_docker_container(container_id)
    ports_in_use.clear()

def cleanup_stale_docker_containers_if_any(total_machines):
    debug("Cleaning up stale docker containers if any")
    container_names = []
    for i in range(total_machines):
        container_names.append("replica%d" % i)
    _kill_docker_container(" ".join(container_names))
    debug("Cleaned up stale docker containers")

def _kill_docker_container(container_identifier):
    run_command("docker kill %s" % container_identifier, True, False)
    run_command("docker rm %s" % container_identifier, True, False)



def run_command_in_container(container_name, command, synchronous, exit_if_fail):
    container_id = containers_data[container_name]["id"]
    command = "docker exec %s %s" % (container_id, command)
    run_command(command, synchronous, exit_if_fail)


def get_free_port():
    port = random.randint(port_range[0], port_range[1])
    while port in ports_in_use:
        port = random.randint(port_range[0], port_range[1])
    ports_in_use.add(port)
    return port


def run_command(command, synchronous, exit_if_fail):
    result = None
    if synchronous:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE,  stderr=subprocess.STDOUT)
        if result.returncode != 0:
            if exit_if_fail:
                warn("Command failed: %s" % command)
                error(result.stdout.decode("utf-8"))
            else:
                warn("Command failed %s: %s" % (command, result.stdout.decode("utf-8")))
    else:
        subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result