"""Unit tests for cli.py — command registration and top-level help."""
from click.testing import CliRunner
from assignment_codeval.cli import cli


class TestCliRegistration:
    def test_help_exits_zero(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_lists_run_evaluation(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "run-evaluation" in result.output

    def test_help_lists_download_submissions(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "download-submissions" in result.output

    def test_help_lists_export_tests(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "export-tests" in result.output

    def test_help_lists_install_assignment(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "install-assignment" in result.output

    def test_help_lists_check_grading(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "check-grading" in result.output

    def test_help_lists_recent_comments(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert "recent-comments" in result.output

    def test_unknown_command_exits_nonzero(self):
        result = CliRunner().invoke(cli, ["not-a-real-command"])
        assert result.exit_code != 0

    def test_debug_flag_accepted(self):
        result = CliRunner().invoke(cli, ["--debug", "--help"])
        assert result.exit_code == 0

    def test_run_evaluation_subcommand_help(self):
        result = CliRunner().invoke(cli, ["run-evaluation", "--help"])
        assert result.exit_code == 0
        assert "CODEVAL_FILE" in result.output

    def test_export_tests_subcommand_help(self):
        result = CliRunner().invoke(cli, ["export-tests", "--help"])
        assert result.exit_code == 0

    def test_install_assignment_subcommand_help(self):
        result = CliRunner().invoke(cli, ["install-assignment", "--help"])
        assert result.exit_code == 0
