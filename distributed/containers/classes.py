import dataclasses


@dataclasses.dataclass(repr=True)
class ContainerData:
    """ Class to store running container data """
    id: str
    name: str
    ports: list

    def __init__(self, name) -> None:
        self.id = None
        self.name = name
        self.ports = []
