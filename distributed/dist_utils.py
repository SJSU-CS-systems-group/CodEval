import subprocess
from typing import Tuple, List
from .containers import ContainerData, add_container, get_container_by_name, \
    remove_container_by_name, get_free_port, get_running_containers_count, \
    add_new_controller_container, get_controller_container, \
    remove_controller_container
from commons import debug, error, errorWithException, warn


def _kill_stale_and_run_docker_container(
        container: ContainerData,
        docker_command: str,
        temp_dir: str,
        ports_count: int,
) -> ContainerData:
    ports_subcommand = ""
    for _ in range(ports_count):
        port = get_free_port()
        container.ports.append(port)
        ports_subcommand += "-p %d:%d " % (port, port)
    docker_command = docker_command.replace("NAME", container.name)
    docker_command = docker_command.replace("SUBMISSIONS", temp_dir)
    docker_command = docker_command.replace("PORTS", ports_subcommand)

    debug("Docker run command: %s" % docker_command)
    _kill_docker_container(container.name, True)
    result = _run_command(docker_command, True)
    if result.returncode != 0:
        errorWithException("Docker run failed: %s" %
                           result.stdout.decode("utf-8"))
    container.id = result.stdout.decode("utf-8").strip()


def kill_stale_and_run_controller_container(
        docker_command: str,
        temp_dir: str,
        ports_count: int,
) -> None:
    container = add_new_controller_container()
    _kill_stale_and_run_docker_container(
        container, docker_command, temp_dir, ports_count
    )


def kill_stale_and_run_docker_container(
        container_name: str,
        docker_command: str,
        temp_dir: str,
        ports_count: int,
) -> None:
    container = ContainerData(container_name)
    _kill_stale_and_run_docker_container(
        container, docker_command, temp_dir, ports_count
    )
    add_container(container)


def kill_running_docker_container(
    container_name: str,
    wait_to_kill: bool
) -> None:
    container = get_container_by_name(container_name)
    if container is not None:
        _kill_docker_container(container.id, wait_to_kill)
        remove_container_by_name(container_name)


def kill_running_controller_container(wait_to_kill: bool) -> None:
    container = get_controller_container()
    if container is not None:
        _kill_docker_container(container.id, wait_to_kill)
        remove_controller_container()


def _kill_docker_container(
    container_identifier: str,
    wait_to_kill: bool
) -> None:
    ''' Kill a docker container and remove it '''
    # Run docker rm irrespective of whether docker kill succeeds or not.
    _run_command("docker stop %s || true && docker rm %s " % (
        container_identifier,
        container_identifier
    ), wait_to_kill)


def _replace_ports_in_command(
    command: str,
    port_placeholder: str,
    ports_used: List[str],
) -> str:
    '''
    Replace the port placeholder with the actual ports used by the container.
    '''
    port_start_index = command.find(port_placeholder)
    while port_start_index != -1:
        port_end_index = port_start_index + len(port_placeholder)
        while port_end_index < len(command) and \
                command[port_end_index].isdigit():
            port_end_index += 1
        port_index = int(
            command[port_start_index+len(port_placeholder):port_end_index])
        if port_index >= len(ports_used):
            errorWithException("Not enough ports to expose. Increase PORTS " +
                               "in spec file to at least %d" % (port_index+1))
        command = command.replace(
            "%s%d" % (port_placeholder, port_index),
            str(ports_used[port_index])
        )
        port_start_index = command.find(port_placeholder)
    return command


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
    for idx, container_name in enumerate(container_names):
        replica_command = command
        replica_command = replica_command.replace(
            "USERNAME",
            placeholder_replacements['username'][idx] + '_' + str(idx)
        )
        replica_command = _replace_ports_in_command(
            replica_command,
            "H_PORT_",
            get_controller_container().ports
        )
        replica_command = _replace_ports_in_command(
            replica_command,
            "PORT_",
            get_container_by_name(container_name).ports
        )
        success, logs = _run_command_in_container(
            container_name, replica_command, is_sync, fail_on_error
        )
        out += logs
        if not is_sync and not fail_on_error:
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
        if fail_on_error:
            errorWithException("Container %s not found" % container_name)
        else:
            error("Container %s not found" % container_name)
        return False, out

    debug("Running %s %s command in container %s: %s" % (
        'halting' if fail_on_error else 'non-halting',
        'sync' if is_sync else 'async',
        container_name,
        command
    ))

    docker_command = command

    if not is_sync and fail_on_error:
        docker_command = docker_command + \
            ' 2> outlog || echo $? > failed_status'

    docker_command = "docker exec %s bash -c '%s'" % \
        (container_data.id, docker_command)
    result = _run_command(docker_command, is_sync)
    if not is_sync:
        if not fail_on_error:
            return True, out
        else:
            result = _run_command(
                "sleep 3 && docker exec %s bash -c '( ! test -f failed_status ) || ( cat outlog && false )'" % (
                    container_data.id
                ),
                True
            )
    if result.returncode != 0:
        if fail_on_error:
            error("Docker command failed for container %s: %s\n%s" % (
                container_name,
                command,
                result.stdout.decode("utf-8")
            ))
            stdout_split = result.stdout.decode("utf-8").split("\n")
            out += bytes(
                "Docker command failed for container %s: %s\n%s" % (
                    container_name,
                    command,
                    "\n".join(
                        stdout_split[:5] +
                        ["..."] +
                        stdout_split[-6:]
                            if len(stdout_split) > 10 else stdout_split
                    )
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
    command: str,
    is_sync: bool,
    fail_on_error: bool,
    placeholder_replacements: dict,
) -> (Tuple[bool, bytes]):
    '''
    Run command on the controller container emulating a host machine.
    Returns a tuple (success, out), where success is a boolean indicating
    whether the test passed or not, and out is a string containing the
    output of the test.
    '''
    out = b''
    container_data = get_controller_container()
    command = command.replace("HOST_IP", placeholder_replacements['host_ip'])
    command = _replace_ports_in_command(
        command,
        "H_PORT_",
        container_data.ports
    )
    debug("Running %s %s command in controller container: %s" % (
        'halting' if fail_on_error else 'non-halting',
        'sync' if is_sync else 'async',
        command
    ))


    if not is_sync and fail_on_error:
        command = command + ' 2> outlog || echo $? > failed_status'

    docker_command = "docker exec %s bash -c '%s'" % (
        container_data.id, command
    )
    result = _run_command(docker_command, is_sync)
    if not is_sync:
        if not fail_on_error:
            return True, out
        else:
            result = _run_command(
                "sleep 3 && docker exec %s bash -c '( ! test -f failed_status ) || ( cat outlog && false )'" % (
                    container_data.id
                ),
                True
            )
    if result.returncode != 0:
        if fail_on_error:
            error("Docker command failed for controller container: %s\n%s" % (
                command,
                result.stdout.decode("utf-8")
            ))
            stdout_split = result.stdout.decode("utf-8").split("\n")
            out += bytes(
                "Docker command failed for controller container: %s\n%s" % (
                    command,
                    "\n".join(
                        stdout_split[:5] +
                        ["..."] +
                        stdout_split[-6:]
                            if len(stdout_split) > 10 else stdout_split
                    )
                ), "utf-8"
            )
        else:
            warn("Docker command failed for controller container: %s\n%s" % (
                command,
                result.stdout.decode("utf-8")
            ))
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
    container_data = get_controller_container()
    command = command.replace("HOST_IP", placeholder_replacements['host_ip'])
    command = _replace_ports_in_command(
        command,
        "H_PORT_",
        container_data.ports
    )
    # command = command.replace("TEMP_DIR", placeholder_replacements['temp_dir'])
    command = _replace_peer_hostport_placeholders(command,
                                                  placeholder_replacements)
    docker_command = "docker exec %s bash -c '%s'" % (
        container_data.id, command
    )
    debug("Running test command: %s" % docker_command)
    result = _run_command(docker_command, True)
    if result.returncode != 0:
        error(result.stdout.decode("utf-8"))
        message = "Distributed Test %s of %s: FAILED" % (
            str(test_number), str(testcases_count))
        out += bytes(message + "\n", "utf-8")
        if hint is not None:
            out += bytes("Hint: " + hint + "\n", "utf-8")
        else:
            out += bytes("Command ran: " + command + "\n", "utf-8")
            stdout_split = result.stdout.decode("utf-8").split("\n")
            out += bytes(
                (
                    "\n".join(
                        stdout_split[:5] +
                        ["..."] +
                        stdout_split[-6:]
                            if len(stdout_split) > 10 else stdout_split
                    ) + "\n"
                ), "utf-8"
            )
    else:
        message = "Distributed Test %s of %s: PASSED" % (
            str(test_number), str(testcases_count))
        out += bytes(message + "\n", "utf-8")
        debug(message)
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
            hostport_peers.append(
                placeholder_replacements['host_ip'] + ':' +
                str(get_container_by_name("replica%d" % i).ports[0])
            )
        command = command[:start_index] + \
            ",".join(hostport_peers) + command[end_index+1:]
    return command


def _run_command(command: str, is_sync: bool) -> (
    subprocess.CompletedProcess or subprocess.Popen
):
    '''
    Run a command in the host machine.
    If is_sync is True, wait for the command to finish and return a 
        CompletedProcess instance.
    If is_sync is False, return Popen instance.
    '''
    result = None
    if is_sync:
        result = subprocess.run(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    else:
        result = subprocess.Popen(command, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result
