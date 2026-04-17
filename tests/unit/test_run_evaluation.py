"""Unit tests for evaluate.py core pipeline via Click's in-process test runner.

Running through CliRunner (instead of subprocess) keeps code execution in the
pytest process so pytest-cov tracks coverage of setup/parse_tags/check_test/cleanup.
"""
import os
import textwrap
import pytest
from click.testing import CliRunner

from assignment_codeval.evaluate import run_evaluation, setup, cleanup, parse_tags
import assignment_codeval.evaluate as ev_mod


@pytest.fixture(autouse=True)
def reset_eval_globals(tmp_path, monkeypatch):
    """Each test gets a clean working directory and reset globals."""
    monkeypatch.chdir(tmp_path)
    # Reset all relevant globals
    ev_mod.test_args = ""
    ev_mod.test_case_count = 0
    ev_mod.test_case_total = 0
    ev_mod.num_passed = 0
    ev_mod.num_failed = 0
    ev_mod.timeout_val = 10
    ev_mod.expected_exit_code = -1
    ev_mod.test_case_hint = ""
    ev_mod.is_hidden_testcase = False
    ev_mod.cmps = []
    ev_mod.temp_files = []
    ev_mod._active_temp_files = []
    ev_mod.last_compile_command = ""
    yield
    # Cleanup .testing dir if still present
    cleanup()


def _write_codeval(tmp_path, content):
    f = tmp_path / "test.codeval"
    f.write_text(textwrap.dedent(content))
    return str(f)


# ---------------------------------------------------------------------------
# setup / cleanup
# ---------------------------------------------------------------------------

class TestSetupCleanup:
    def test_setup_creates_testing_dir(self, tmp_path):
        setup()
        assert os.path.isdir(ev_mod.TESTING_DIR)

    def test_setup_creates_required_files(self, tmp_path):
        setup()
        for fname in ["compilelog", "difflog", "expectedoutput", "expectederror",
                      "fileinput", "yourerror", "youroutput"]:
            assert os.path.exists(os.path.join(ev_mod.TESTING_DIR, fname))

    def test_cleanup_removes_testing_files(self, tmp_path):
        setup()
        cleanup()
        assert not os.path.exists(os.path.join(ev_mod.TESTING_DIR, "compilelog"))

    def test_cleanup_removes_testing_dir_when_empty(self, tmp_path):
        setup()
        cleanup()
        assert not os.path.isdir(ev_mod.TESTING_DIR)

    def test_cleanup_safe_when_nothing_exists(self, tmp_path):
        cleanup()  # should not raise


# ---------------------------------------------------------------------------
# parse_tags — non-program tags
# ---------------------------------------------------------------------------

class TestParseTagsNonProgram:
    def test_empty_tags(self, tmp_path):
        parse_tags([])  # should not raise

    def test_comment_lines_ignored(self, tmp_path):
        setup()
        parse_tags(["# this is a comment\n"])

    def test_blank_lines_ignored(self, tmp_path):
        setup()
        parse_tags(["\n", "  \n", "\t\n"])

    def test_timeout_tag_sets_global(self, tmp_path):
        setup()
        parse_tags(["TO 30\n"])
        assert ev_mod.timeout_val == 30

    def test_exit_code_tag_sets_global(self, tmp_path):
        setup()
        parse_tags(["X 42\n"])
        assert ev_mod.expected_exit_code == 42

    def test_hint_tag_sets_global(self, tmp_path):
        setup()
        parse_tags(["HINT check your output\n"])
        assert ev_mod.test_case_hint == "check your output"

    def test_output_length_tag(self, tmp_path):
        setup()
        parse_tags(["OLEN 512\n"])
        assert ev_mod.output_length_limit == 512

    def test_crt_hw_block_skipped(self, tmp_path):
        setup()
        # Any T tag inside the block should NOT increment test_case_count
        tags = [
            "CRT_HW START\n",
            "T python3 should_be_ignored.py\n",
            "O ignored\n",
            "CRT_HW END\n",
        ]
        parse_tags(tags)
        assert ev_mod.test_case_count == 0

    def test_assignment_start_end_block_skipped(self, tmp_path):
        setup()
        tags = [
            "ASSIGNMENT START Homework 1\n",
            "T ignored_cmd\n",
            "ASSIGNMENT END\n",
        ]
        parse_tags(tags)
        assert ev_mod.test_case_count == 0

    def test_ignored_tags_silently_skipped(self, tmp_path):
        setup()
        # CD, CTO, Z, RUN are silently ignored
        parse_tags(["CD somedir\n", "Z support.zip\n", "RUN something\n"])

    def test_unknown_tag_exits(self, tmp_path):
        setup()
        with pytest.raises(SystemExit):
            parse_tags(["ZZUNKNOWN something\n"])

    def test_bare_shell_command_warns(self, tmp_path, capsys):
        setup()
        parse_tags(["echo hello world\n"])
        out = capsys.readouterr().out
        assert "Warning" in out or "CMD" in out


# ---------------------------------------------------------------------------
# run_evaluation — via CliRunner (in-process for coverage)
# ---------------------------------------------------------------------------

class TestRunEvaluationViaCliRunner:
    def test_basic_pass(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("hello")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nO hello\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Passed" in result.output

    def test_output_mismatch_exits_2(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("wrong")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nO correct\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert result.exit_code == 2

    def test_output_includes_test_count(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("hi")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nO hi\nT python3 {prog}\nO hi\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0
        assert "2" in result.output

    def test_hidden_test_passes(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("secret")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"HT python3 {prog}\nO secret\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_input_passed_to_program(self, tmp_path):
        prog = tmp_path / "echo.py"
        prog.write_text("print(input())\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nI hello\nO hello\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_timeout_failure(self, tmp_path):
        prog = tmp_path / "slow.py"
        prog.write_text("import time\ntime.sleep(60)\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"TO 1\nT python3 {prog}\nO something\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert result.exit_code != 0

    def test_exit_code_match_passes(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("import sys\nsys.exit(1)\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nX 1\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_exit_code_mismatch_fails(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("import sys\nsys.exit(42)\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nX 0\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert result.exit_code != 0

    def test_crt_hw_block_ignored_in_evaluation(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("real")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            CRT_HW START
            Assignment description here
            CRT_HW END
            T python3 {prog}
            O real
        """))
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_hint_shown_on_failure(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("wrong")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nHINT check format\nO correct\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert "check format" in result.output

    def test_output_contains_timing(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("hi")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nO hi\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert "took" in result.output and "seconds" in result.output

    def test_bare_input_tag(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("print(input(), end='')\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nIB hello\nOB hello\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_supply_input_file(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("print(input())\n")
        input_file = tmp_path / "input.txt"
        input_file.write_text("from file\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nIF {input_file}\nO from file\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_output_file_check(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("print('expected')\n")
        expected = tmp_path / "expected.txt"
        expected.write_text("expected\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nOF {expected}\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_print_label_tag(self, tmp_path, capsys):
        prog = tmp_path / "prog.py"
        prog.write_text('print("hi")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"PRINT Section A\nT python3 {prog}\nO hi\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert "Section A" in result.output

    def test_run_command_tag(self, tmp_path):
        codeval = tmp_path / "t.codeval"
        codeval.write_text("CMD echo setup done\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_temp_tag_registers_file(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("hi")\n')
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"TEMP out.txt\nT python3 {prog}\nO hi\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_compile_tag_runs_command(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text('print("compiled")\n')
        codeval = tmp_path / "t.codeval"
        # C tag runs the compile command; python3 -c 'pass' succeeds
        codeval.write_text(f"C python3 -c 'pass'\nT python3 {prog}\nO compiled\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert "Passed" in result.output

    def test_compile_failure_exits(self, tmp_path):
        codeval = tmp_path / "t.codeval"
        codeval.write_text("C python3 -c 'syntax error!'\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert result.exit_code != 0

    def test_tcmd_passes(self, tmp_path):
        codeval = tmp_path / "t.codeval"
        codeval.write_text("TCMD echo ok\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0
        assert "PASSED" in result.output

    def test_tcmd_failure_exits_1(self, tmp_path):
        codeval = tmp_path / "t.codeval"
        codeval.write_text("TCMD false\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)])
        assert result.exit_code == 1

    def test_cmp_tag_appends_to_cmps(self, tmp_path):
        setup()
        parse_tags(["CMP out.txt expected.txt\n"])
        assert ev_mod.cmps == [["out.txt", "expected.txt"]]

    def test_error_output_check(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("import sys\nprint('err', file=sys.stderr)\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nE err\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0

    def test_parse_tags_tag_requires_args_exits(self, tmp_path):
        setup()
        with pytest.raises(SystemExit):
            parse_tags(["T\n"])

    def test_parse_tags_empty_args_exits(self, tmp_path):
        setup()
        with pytest.raises(SystemExit):
            parse_tags(["T  \n"])

    def test_parse_tags_unknown_uppercase_tag_short_exits(self, tmp_path):
        setup()
        with pytest.raises(SystemExit):
            parse_tags(["ZZZ something\n"])

    def test_check_error_bare_tag(self, tmp_path):
        prog = tmp_path / "prog.py"
        prog.write_text("import sys\nprint('err', end='', file=sys.stderr)\n")
        codeval = tmp_path / "t.codeval"
        codeval.write_text(f"T python3 {prog}\nEB err\n")
        runner = CliRunner()
        result = runner.invoke(run_evaluation, [str(codeval)], catch_exceptions=False)
        assert result.exit_code == 0
