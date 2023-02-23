import dataclasses


@dataclasses.dataclass(repr=True)
class DistributedTests:
    """Class to store distributed tests"""
    docker_command: str
    host_ip: str
    temp_dir: str
    testcase_file: str
    ports_count_to_expose: int
    testcases_count: int
    tests_setup_commands: list
    cleanup_commands: list
    test_groups: list
    timeout: int

    def __init__(self, docker_command, host_ip, temp_dir, testcase_file):
        self.docker_command = docker_command
        self.host_ip = host_ip
        self.temp_dir = temp_dir
        self.testcase_file = testcase_file
        self.testcases_count = 0
        self.ports_count_to_expose = 0
        self.tests_setup_commands = []
        self.cleanup_commands = []
        self.test_groups = []
        self.timeout = 60

    def add_test_group(self, test_group: "TestGroup"):
        self.test_groups.append(test_group)

    @dataclasses.dataclass(repr=True)
    class TestGroup:
        """
        Defines a test group with commands and test hints.
        Can be a combination of homogenous and heterogenous tests.
        """
        total_machines: int
        homogenous: bool
        heterogenous: bool
        commands: list
        test_hints: list

        def __init__(self, total_machines, homogenous, heterogenous) -> None:
            self.total_machines = total_machines
            self.homogenous = homogenous
            self.heterogenous = heterogenous
            self.commands = []
            self.test_hints = []
