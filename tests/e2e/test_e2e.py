"""End-to-end tests for the assignment-codeval CLI.

These tests invoke the CLI binary via subprocess to verify full command
workflows, exit codes, and output from the user's perspective.
"""
import os
import subprocess
import textwrap
import zipfile
from pathlib import Path

import pytest

# The tests/ directory (one level up from e2e/)
TESTS_DIR = Path(__file__).parent.parent
UNIT_DIR = TESTS_DIR / "unit"

CLI = "assignment-codeval"


def run_cli(*args, cwd=None, input_text=None):
    """Run the CLI and return the CompletedProcess."""
    return subprocess.run(
        [CLI, *args],
        cwd=cwd or TESTS_DIR,
        capture_output=True,
        text=True,
        input=input_text,
    )


# ---------------------------------------------------------------------------
# CLI meta
# ---------------------------------------------------------------------------


class TestCliHelp:
    def test_help_exits_zero(self):
        result = run_cli("--help")
        assert result.returncode == 0

    def test_help_lists_subcommands(self):
        result = run_cli("--help")
        assert "run-evaluation" in result.stdout
        assert "export-tests" in result.stdout
        assert "install-assignment" in result.stdout

    def test_subcommand_help(self):
        result = run_cli("run-evaluation", "--help")
        assert result.returncode == 0
        assert "CODEVAL_FILE" in result.stdout

    def test_unknown_command_exits_nonzero(self):
        result = run_cli("no-such-command")
        assert result.returncode != 0

    def test_export_tests_help(self):
        result = run_cli("export-tests", "--help")
        assert result.returncode == 0
        assert "--include-hidden" in result.stdout


# ---------------------------------------------------------------------------
# run-evaluation — happy path
# ---------------------------------------------------------------------------


class TestRunEvaluationPassing:
    def test_basic_stdout_check(self):
        result = run_cli("run-evaluation", "test_basic.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_input_echo(self):
        result = run_cli("run-evaluation", "test_input.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_timeout_tag_respected(self):
        result = run_cli("run-evaluation", "test_timeout.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_exit_code_tag(self):
        result = run_cli("run-evaluation", "test_exit_code.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_hidden_test_case_passes(self):
        result = run_cli("run-evaluation", "test_hidden.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_bare_output_tags(self):
        result = run_cli("run-evaluation", "test_bare_tags.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_multiple_inputs(self):
        result = run_cli("run-evaluation", "test_multiple_inputs.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_comprehensive_multi_test(self):
        result = run_cli("run-evaluation", "test_comprehensive.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_file_io(self):
        result = run_cli("run-evaluation", "test_file_io.codeval", cwd=UNIT_DIR)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_output_includes_pass(self):
        result = run_cli("run-evaluation", "test_basic.codeval", cwd=UNIT_DIR)
        assert "Passed" in result.stdout or "passed" in result.stdout.lower()

    def test_output_includes_timing(self):
        result = run_cli("run-evaluation", "test_basic.codeval", cwd=UNIT_DIR)
        assert "took" in result.stdout and "seconds" in result.stdout


# ---------------------------------------------------------------------------
# run-evaluation — failure cases
# ---------------------------------------------------------------------------


class TestRunEvaluationFailing:
    def test_wrong_output_exits_nonzero(self, tmp_path):
        """A program whose output doesn't match expected output exits 2."""
        prog = tmp_path / "wrong.py"
        prog.write_text('print("wrong answer")\n')
        codeval = tmp_path / "wrong.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            T python3 {prog}
            O correct answer
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode == 2

    def test_wrong_output_shows_failed(self, tmp_path):
        prog = tmp_path / "wrong.py"
        prog.write_text('print("nope")\n')
        codeval = tmp_path / "fail.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            T python3 {prog}
            O expected output
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert "FAILED" in result.stdout

    def test_timeout_triggers_failure(self, tmp_path):
        prog = tmp_path / "slow.py"
        prog.write_text("import time\ntime.sleep(60)\n")
        codeval = tmp_path / "slow.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            TO 1
            T python3 {prog}
            O something
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode != 0

    def test_wrong_exit_code_fails(self, tmp_path):
        prog = tmp_path / "exit42.py"
        prog.write_text("import sys\nsys.exit(42)\n")
        codeval = tmp_path / "exit.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            T python3 {prog}
            X 0
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode != 0

    def test_nonexistent_codeval_file_exits_nonzero(self):
        result = run_cli("run-evaluation", "does_not_exist.codeval")
        assert result.returncode != 0

    def test_compile_failure_exits_nonzero(self, tmp_path):
        src = tmp_path / "bad.cpp"
        src.write_text("this is not valid C++\n")
        codeval = tmp_path / "compile_fail.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            C g++ -o bad {src}
            T ./bad
            O hello
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# run-evaluation — output format
# ---------------------------------------------------------------------------


class TestRunEvaluationOutput:
    def test_test_case_count_in_output(self, tmp_path):
        prog = tmp_path / "echo.py"
        prog.write_text("print('hi')\n")
        codeval = tmp_path / "count.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            T python3 {prog}
            O hi
            T python3 {prog}
            O hi
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode == 0
        assert "1" in result.stdout
        assert "2" in result.stdout

    def test_hidden_test_shows_hidden_label_on_failure(self, tmp_path):
        prog = tmp_path / "bad.py"
        prog.write_text('print("wrong")\n')
        codeval = tmp_path / "hidden_fail.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            HT python3 {prog}
            O correct
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode != 0
        assert "Hidden" in result.stdout or "hidden" in result.stdout.lower()

    def test_hint_shown_on_failure(self, tmp_path):
        prog = tmp_path / "bad.py"
        prog.write_text('print("wrong")\n')
        codeval = tmp_path / "hint_fail.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            T python3 {prog}
            HINT Check your output format
            O correct
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert "Check your output format" in result.stdout


# ---------------------------------------------------------------------------
# export-tests
# ---------------------------------------------------------------------------


class TestExportTests:
    def test_creates_zip(self, tmp_path):
        codeval = tmp_path / "simple.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 echo.py
            I hello
            O hello
        """))
        result = run_cli(
            "export-tests", str(codeval), "-o", str(tmp_path / "out.zip"),
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert (tmp_path / "out.zip").exists()

    def test_zip_contains_expected_files(self, tmp_path):
        codeval = tmp_path / "simple.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 echo.py
            I hello
            O hello
        """))
        out = tmp_path / "out.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert "in.1" in names
        assert "out.1" in names
        assert "err.1" in names
        assert "TESTS.md" in names

    def test_input_content_in_zip(self, tmp_path):
        codeval = tmp_path / "simple.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 echo.py
            I hello world
            O hello world
        """))
        out = tmp_path / "out.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            assert zf.read("in.1") == b"hello world\n"

    def test_output_content_in_zip(self, tmp_path):
        codeval = tmp_path / "simple.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 echo.py
            O expected output
        """))
        out = tmp_path / "out.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            assert zf.read("out.1") == b"expected output\n"

    def test_hidden_excluded_by_default(self, tmp_path):
        codeval = tmp_path / "mixed.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 a.py
            O visible
            HT python3 b.py
            O hidden
        """))
        out = tmp_path / "out.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert "in.1" in names
        assert "in.2" not in names

    def test_include_hidden_flag(self, tmp_path):
        codeval = tmp_path / "mixed.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 a.py
            O visible
            HT python3 b.py
            O hidden
        """))
        out = tmp_path / "out.zip"
        run_cli(
            "export-tests", str(codeval), "--include-hidden", "-o", str(out),
            cwd=tmp_path,
        )
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert "in.1" in names
        assert "in.2" in names

    def test_multiple_test_cases(self, tmp_path):
        codeval = tmp_path / "multi.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 a.py
            O one
            T python3 b.py
            O two
            T python3 c.py
            O three
        """))
        out = tmp_path / "out.zip"
        result = run_cli(
            "export-tests", str(codeval), "-o", str(out), cwd=tmp_path
        )
        assert result.returncode == 0
        assert "3" in result.stdout
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        for i in (1, 2, 3):
            assert f"in.{i}" in names
            assert f"out.{i}" in names

    def test_default_output_filename(self, tmp_path):
        codeval = tmp_path / "myassign.codeval"
        codeval.write_text("T python3 a.py\nO hi\n")
        result = run_cli("export-tests", str(codeval), cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / "myassign_tests.zip").exists()

    def test_tests_md_content(self, tmp_path):
        codeval = tmp_path / "doc.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 prog.py
            O output
        """))
        out = tmp_path / "doc.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            md = zf.read("TESTS.md").decode()
        assert "Test 1" in md
        assert "python3 prog.py" in md

    def test_exit_code_in_tests_md(self, tmp_path):
        codeval = tmp_path / "exit.codeval"
        codeval.write_text(textwrap.dedent("""\
            T python3 prog.py
            X 42
            O done
        """))
        out = tmp_path / "exit.zip"
        run_cli("export-tests", str(codeval), "-o", str(out), cwd=tmp_path)
        with zipfile.ZipFile(out) as zf:
            md = zf.read("TESTS.md").decode()
        assert "42" in md

    def test_nonexistent_file_exits_nonzero(self, tmp_path):
        result = run_cli(
            "export-tests", str(tmp_path / "ghost.codeval"), cwd=tmp_path
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# install-assignment (local copy)
# ---------------------------------------------------------------------------


class TestInstallAssignment:
    def test_install_to_local_dir(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        codeval = src_dir / "hw1.codeval"
        codeval.write_text("T python3 prog.py\nO hi\n")
        result = run_cli(
            "install-assignment", str(codeval), str(dest_dir), cwd=src_dir
        )
        assert result.returncode == 0
        assert (dest_dir / "hw1.codeval").exists()

    def test_install_help(self):
        result = run_cli("install-assignment", "--help")
        assert result.returncode == 0
        assert "CODEVAL" in result.stdout or "codeval" in result.stdout.lower()


# ---------------------------------------------------------------------------
# download-submissions (CLI surface only — Canvas API not available in CI)
# ---------------------------------------------------------------------------


class TestDownloadSubmissions:
    def test_help_exits_zero(self):
        result = run_cli("download-submissions", "--help")
        assert result.returncode == 0

    def test_help_shows_course_and_assignment_args(self):
        result = run_cli("download-submissions", "--help")
        assert "COURSE" in result.stdout
        assert "ASSIGNMENT" in result.stdout

    def test_help_shows_options(self):
        result = run_cli("download-submissions", "--help")
        for flag in ("--active", "--target-dir", "--include-commented", "--for-name"):
            assert flag in result.stdout

    def test_missing_args_exits_nonzero(self):
        # COURSE and ASSIGNMENT are required when --active is not passed
        result = run_cli("download-submissions")
        assert result.returncode != 0

    def test_missing_args_shows_usage(self):
        result = run_cli("download-submissions")
        output = result.stdout + result.stderr
        assert "Usage" in output or "Error" in output or "Missing" in output

    def test_no_canvas_config_exits_nonzero(self, tmp_path, monkeypatch):
        # Point the app config dir to an empty tmp dir so no codeval.ini exists
        monkeypatch.setenv("HOME", str(tmp_path))
        result = subprocess.run(
            [CLI, "download-submissions", "TestCourse", "TestAssignment"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        assert result.returncode != 0

    def test_no_canvas_config_reports_error(self, tmp_path):
        result = subprocess.run(
            [CLI, "download-submissions", "TestCourse", "TestAssignment"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        output = result.stdout + result.stderr
        # Should mention config, SERVER, or canvas rather than a raw traceback
        assert any(word in output.lower() for word in ("config", "server", "canvas", "token", "error"))

    def test_active_flag_no_canvas_config_exits_nonzero(self, tmp_path):
        result = subprocess.run(
            [CLI, "download-submissions", "--active"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# CRT_HW block handling
# ---------------------------------------------------------------------------


class TestCrtHwBlock:
    def test_crt_hw_content_ignored(self, tmp_path):
        """Content inside CRT_HW blocks must not affect evaluation."""
        prog = tmp_path / "prog.py"
        prog.write_text('print("hello")\n')
        codeval = tmp_path / "crt.codeval"
        codeval.write_text(textwrap.dedent(f"""\
            CRT_HW START
            This is assignment description that should be ignored
            T python3 should_be_ignored.py
            O ignored output
            CRT_HW END
            T python3 {prog}
            O hello
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode == 0

    def test_crt_hw_block_only_file_passes(self, tmp_path):
        """A codeval file with only a CRT_HW block has no test cases — should exit 0."""
        codeval = tmp_path / "desc_only.codeval"
        codeval.write_text(textwrap.dedent("""\
            CRT_HW START
            # Assignment description
            Only markdown here.
            CRT_HW END
        """))
        result = run_cli("run-evaluation", str(codeval), cwd=tmp_path)
        assert result.returncode == 0
