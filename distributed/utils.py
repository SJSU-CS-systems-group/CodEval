import subprocess
from typing import Tuple
from .containers import *
from commons import *


def kill_stale_and_run_docker_container(
        container_name: str,
        docker_command: str,
        temp_dir: str,
        ports_count: int,
) -> bytes:
    ports_subcommand = ""
    container = ContainerData(container_name)
    for i in range(ports_count):
        port = get_free_port()
        container.ports.append(port)
        ports_subcommand += "-p %d:%d " % (port, port)
    docker_command = docker_command.replace("NAME", container_name)
    docker_command = docker_command.replace("SUBMISSIONS", temp_dir)
    docker_command = docker_command.replace("PORTS", ports_subcommand)

    debug("Docker run command: %s" % docker_command)
    _kill_docker_container(container_name, True)
    result = _run_command(docker_command, True)
    debug("Docker run result: %s" % result.stdout.decode("utf-8"))
    if result.returncode != 0:
        error("Docker run failed: %s" % result.stdout.decode("utf-8"), True)
    container.id = result.stdout.decode("utf-8").strip()
    add_container(container)


def kill_running_docker_container(
    container_name: str,
    wait_to_kill: bool
) -> None:
    container = get_container_by_name(container_name)
    if container is not None:
        _kill_docker_container(container.id, wait_to_kill)
        remove_container_by_name(container_name)


def _kill_docker_container(
    container_identifier: str,
    wait_to_kill: bool
) -> None:
    ''' Asynchronously kill a docker container and remove it '''
    # Run docker rm irrespective of whether docker kill succeeds or not.
    _run_command("docker kill %s || true && docker rm %s " % (
        container_identifier,
        container_identifier
    ), wait_to_kill)


def run_command_in_containers(
    container_names: list,
    command: str,
    is_sync: bool,
    fail_on_error: bool,
    placeholder_replacements: dict,
) -> (Tuple[bool, bytes]):
    '''
    Run a command in a list of docker containers.
    If is_sync is True, then the command is run in all containers in parallel.
    If is_sync is False, then the command is run in each container sequentially.
    '''
    out = b''
    command = command.replace("HOST_IP", placeholder_replacements['host_ip'])
    no_error = True
    debug("Running command %s in containers %s" % (command, container_names))
    for container_name in container_names:
        ports_used = get_container_by_name(container_name).ports
        replica_command = command
        port_index = 0
        while "PORT_" in replica_command:
            if port_index >= len(ports_used):
                error("Not enough ports to expose. Increase PORTS \
                        in spec file to at least %d" % (port_index+1),
                      True)
            replica_command = replica_command.replace(
                "PORT_%d" % port_index,
                str(ports_used[port_index])
            )
            port_index += 1
        success, logs = _run_command_in_container(
            container_name, replica_command, is_sync, fail_on_error
        )
        out += logs
        if not is_sync:
            continue
        if not success and fail_on_error:
            return False, out
        no_error = no_error and success
    return no_error, out


def _run_command_in_container(
    container_name: str,
    command: str,
    is_sync: bool,
    fail_on_error: bool,
) -> (Tuple[bool, bytes]):
    '''
    Run a command in a docker container.
    If is_sync is True, wait for the command to finish and return the result.
    If is_sync is False, return None.
    '''
    out = b''
    container_data = get_container_by_name(container_name)
    if container_data is None:
        error("Container %s not found" % container_name, fail_on_error)
        return False, out

    debug("Running %s %s command in container %s: %s" % (
        'halting' if fail_on_error else 'non-halting',
        'sync' if is_sync else 'async',
        container_name,
        command
    ))

    command = "docker exec %s %s" % (container_data.id, command)
    result = _run_command(command, is_sync)
    if not is_sync:
        return True, out
    if result.returncode != 0:
        if fail_on_error:
            error("Docker command failed for container %s: %s\n%s" % (
                container_name,
                command,
                result.stdout.decode("utf-8")
            ), raise_exception=False)
            out += bytes(
                "Docker command failed for container %s: %s\n%s" % (
                    container_name,
                    command,
                    "\n".join(result.stdout.decode("utf-8").split("\n")[-5:])
                ), "utf-8"
            )
        else:
            warn("Docker command failed for container %s: %s\n%s" % (
                container_name,
                command,
                result.stdout.decode("utf-8")
            ))
    return result.returncode == 0, out


def run_external_command(
    bash_command: str,
    is_sync: bool,
    fail_on_error: bool,
    placeholder_replacements: dict,
) -> (Tuple[bool, bytes]):
    '''
    Run command on the host machine.
    Returns a tuple (success, out), where success is a boolean indicating
    whether the test passed or not, and out is a string containing the
    output of the test.
    '''
    out = b''
    bash_command = bash_command.replace("HOST_IP",
                                        placeholder_replacements['host_ip'])
    debug("Running %s %s command on host: %s" % (
        'halting' if fail_on_error else 'non-halting',
        'sync' if is_sync else 'async',
        bash_command
    ))
    result = _run_command(bash_command, is_sync)
    if not is_sync:
        return True, out
    if result.returncode != 0:
        if fail_on_error:
            error("Command failed: %s\n%s" % (
                bash_command,
                result.stdout.decode("utf-8")
            ), raise_exception=False)
            out += bytes(
                "Command failed: %s\n%s" % (
                    bash_command,
                    "\n".join(result.stdout.decode("utf-8").split("\n")[-5:])
                ), "utf-8"
            )
        else:
            warn("Command failed: %s\n%s" %
                 (bash_command, result.stdout.decode("utf-8")))
    return result.returncode == 0, out


def run_test_command(
    command: str,
    hint: str,
    placeholder_replacements: dict,
    test_number: int,
    testcases_count: int,
) -> (Tuple[bool, bytes]):
    '''
    Run test command synchronously on the host machine.
    Returns a tuple (success, out), where success is a boolean indicating
    whether the test passed or not, and out is a string containing the
    output of the test.
    '''
    out = b''
    command = command.replace("HOST_IP", placeholder_replacements['host_ip'])
    command = command.replace("TEMP_DIR", placeholder_replacements['temp_dir'])
    command = _replace_peer_hostport_placeholders(command,
                                                  placeholder_replacements)

    debug("Running test command: %s" % command)
    result = _run_command(command, True)
    if result.returncode != 0:
        error(result.stdout.decode("utf-8"), raise_exception=False)
        message = "Distributed Test %s of %s: FAILED" % (
            str(test_number), str(testcases_count))
        out += bytes(message + "\n", "utf-8")
        if hint is not None:
            out += bytes("Hint: " + hint + "\n", "utf-8")
        out += bytes("\n".join(result.stdout.decode("utf-8")
                               .split("\n")[-10:]) + "\n", "utf-8")
    else:
        message = "Distributed Test %s of %s: PASSED" % (
            str(test_number), str(testcases_count))
        out += bytes(message + "\n", "utf-8")
        info(message)
    return result.returncode == 0, out


def _replace_peer_hostport_placeholders(
    command: str,
    placeholder_replacements: dict
) -> str:
    while 'PEER_HP' in command:
        start_index = command.index('PEER_HP')
        end_index = start_index + 8
        while end_index < len(command) and command[end_index].isdigit():
            end_index += 1
        max_hostport_peers_count = int(
            command[start_index + len('PEER_HP['): end_index])
        hostport_peers = []
        for i in range(min(max_hostport_peers_count,
                           get_running_containers_count() - 1)):
            hostport_peers.append(placeholder_replacements['host_ip'] + ':' +
                                  str(get_container_by_name("replica%d" % i).ports[0]))
        command = command[:start_index] + \
            ",".join(hostport_peers) + command[end_index+1:]
    return command


def _run_command(command: str, is_sync: bool) -> (
    subprocess.CompletedProcess or None
):
    '''
    Run a command in the host machine.
    If is_sync is True, wait for the command to finish and return the result.
    If is_sync is False, return None.
    '''
    result = None
    if is_sync:
        result = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE,  stderr=subprocess.STDOUT)
    else:
        subprocess.Popen(command, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result
