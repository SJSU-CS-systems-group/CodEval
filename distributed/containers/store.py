from typing import List, Set
import random
from .classes import ContainerData

_port_range = (10000, 20000)

_running_controller_container: ContainerData = None
_running_containers: List[ContainerData] = []

_ports_in_use: Set[int] = set()


def add_new_controller_container() -> ContainerData:
    global _running_controller_container
    if _running_controller_container is not None:
        raise Exception("Controller container already running")
    _running_controller_container = ContainerData(name='controller')
    return _running_controller_container

def get_controller_container() -> ContainerData:
    global _running_controller_container
    if _running_controller_container is None:
        raise Exception("Controller container not found")
    return _running_controller_container

def remove_controller_container() -> None:
    global _running_controller_container
    if _running_controller_container is not None:
        for port in _running_controller_container.ports:
            if port in _ports_in_use:
                _ports_in_use.remove(port)
    _running_controller_container = None

def add_container(container_data: ContainerData) -> None:
    _running_containers.append(container_data)


def get_container_by_name(name: str) -> ContainerData or None:
    for container in _running_containers:
        if container.name == name:
            return container
    return None


def get_running_containers_count() -> int:
    return len(_running_containers)


def clear_running_containers() -> None:
    _running_containers.clear()

def clear_ports_in_use() -> None:
    _ports_in_use.clear()


def remove_container_by_name(name: str) -> None:
    '''
    Remove a container from the global list of running containers.
    Returns True if the container was found and removed, False otherwise.
    '''
    for container in _running_containers:
        if container.name == name:
            for port in container.ports:
                _ports_in_use.remove(port)
            _running_containers.remove(container)
            return True
    return False


def get_free_port():
    ''' Get a free port from the global port range '''
    port = random.randint(_port_range[0], _port_range[1])
    while port in _ports_in_use:
        port = random.randint(_port_range[0], _port_range[1])
    _ports_in_use.add(port)
    return port
