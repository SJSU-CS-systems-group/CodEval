import os
import zipfile

import pytest
from click.testing import CliRunner

from assignment_codeval.export_tests import export_tests, parse_codeval_tests

CODEVAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_comprehensive.codeval")


class TestParseCodevalTests:
    def test_parses_all_tests(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert len(tests) == 4

    def test_numbering_sequential(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert [t["num"] for t in tests] == [1, 2, 3, 4]

    def test_hidden_flag(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[0]["hidden"] is False
        assert tests[1]["hidden"] is False
        assert tests[2]["hidden"] is False
        assert tests[3]["hidden"] is True

    def test_command_parsed(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[0]["command"] == "python3 sample_program.py"
        assert tests[1]["command"] == "python3 sample_echo.py"

    def test_input_collected(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[1]["input"] == "hello world\n"
        assert tests[0]["input"] == ""

    def test_output_collected(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[0]["output"] == "hello\n"
        assert tests[1]["output"] == "hello world\n"

    def test_error_collected(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[0]["error"] == "bye\n"
        assert tests[1]["error"] == ""

    def test_exit_code(self):
        tests = parse_codeval_tests(CODEVAL_FILE)
        assert tests[2]["exit_code"] == 42
        assert tests[0]["exit_code"] == -1


class TestFileFromZip:
    def test_if_reads_from_zip(self, tmp_path):
        support_zip = tmp_path / "support.zip"
        with zipfile.ZipFile(str(support_zip), "w") as zf:
            zf.writestr("test_input.txt", "from zip input\n")
        codeval = tmp_path / "test.codeval"
        codeval.write_text("Z support.zip\nT echo hello\nIF test_input.txt\nO hello\n")
        tests = parse_codeval_tests(str(codeval))
        assert tests[0]["input"] == "from zip input\n"

    def test_of_reads_from_zip(self, tmp_path):
        support_zip = tmp_path / "support.zip"
        with zipfile.ZipFile(str(support_zip), "w") as zf:
            zf.writestr("expected.txt", "from zip output\n")
        codeval = tmp_path / "test.codeval"
        codeval.write_text("Z support.zip\nT echo hello\nOF expected.txt\n")
        tests = parse_codeval_tests(str(codeval))
        assert tests[0]["output"] == "from zip output\n"

    def test_multiple_zip_archives(self, tmp_path):
        zip1 = tmp_path / "first.zip"
        with zipfile.ZipFile(str(zip1), "w") as zf:
            zf.writestr("in1.txt", "input one\n")
        zip2 = tmp_path / "second.zip"
        with zipfile.ZipFile(str(zip2), "w") as zf:
            zf.writestr("out1.txt", "output one\n")
        codeval = tmp_path / "test.codeval"
        codeval.write_text(
            "Z first.zip\nZ second.zip\nT echo hello\nIF in1.txt\nOF out1.txt\n"
        )
        tests = parse_codeval_tests(str(codeval))
        assert tests[0]["input"] == "input one\n"
        assert tests[0]["output"] == "output one\n"

    def test_missing_file_raises_error(self, tmp_path):
        codeval = tmp_path / "test.codeval"
        codeval.write_text("T echo hello\nIF nonexistent.txt\nO hello\n")
        with pytest.raises(FileNotFoundError):
            parse_codeval_tests(str(codeval))

    def test_no_z_tag_raises_error_for_if(self, tmp_path):
        # IF without any Z tag means no zip archives to search
        codeval = tmp_path / "test.codeval"
        codeval.write_text("T echo hello\nIF some_file.txt\nO hello\n")
        with pytest.raises(FileNotFoundError):
            parse_codeval_tests(str(codeval))


class TestExportTestsCommand:
    def test_default_excludes_hidden(self, tmp_path):
        runner = CliRunner()
        output_zip = str(tmp_path / "out.zip")
        result = runner.invoke(export_tests, [CODEVAL_FILE, "-o", output_zip])
        assert result.exit_code == 0
        assert "3 test(s)" in result.output

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert "in.1" in names
            assert "out.1" in names
            assert "err.1" in names
            assert "in.2" in names
            assert "in.3" in names
            # test 4 is hidden, should be excluded
            assert "in.4" not in names
            assert "TESTS.md" in names

    def test_include_hidden(self, tmp_path):
        runner = CliRunner()
        output_zip = str(tmp_path / "out.zip")
        result = runner.invoke(export_tests, [CODEVAL_FILE, "--include-hidden", "-o", output_zip])
        assert result.exit_code == 0
        assert "4 test(s)" in result.output

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert "in.4" in names
            assert "out.4" in names

    def test_default_output_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(export_tests, [CODEVAL_FILE])
        assert result.exit_code == 0
        expected_name = "test_comprehensive_tests.zip"
        assert os.path.exists(tmp_path / expected_name)

    def test_tests_md_content(self, tmp_path):
        runner = CliRunner()
        output_zip = str(tmp_path / "out.zip")
        result = runner.invoke(export_tests, [CODEVAL_FILE, "--include-hidden", "-o", output_zip])
        assert result.exit_code == 0

        with zipfile.ZipFile(output_zip, "r") as zf:
            tests_md = zf.read("TESTS.md").decode()
            assert "# Test 1" in tests_md
            assert "command: `python3 sample_program.py`" in tests_md
            assert "# Test 3" in tests_md
            assert "expected exit code: 42" in tests_md
            # test 1 has no exit code tag
            lines = tests_md.split("\n")
            # find test 1 section and verify no exit code line before test 2
            test1_idx = next(i for i, l in enumerate(lines) if "# Test 1" in l)
            test2_idx = next(i for i, l in enumerate(lines) if "# Test 2" in l)
            test1_section = "\n".join(lines[test1_idx:test2_idx])
            assert "expected exit code" not in test1_section

    def test_zip_file_contents(self, tmp_path):
        runner = CliRunner()
        output_zip = str(tmp_path / "out.zip")
        runner.invoke(export_tests, [CODEVAL_FILE, "-o", output_zip])

        with zipfile.ZipFile(output_zip, "r") as zf:
            assert zf.read("in.1").decode() == ""
            assert zf.read("out.1").decode() == "hello\n"
            assert zf.read("err.1").decode() == "bye\n"
            assert zf.read("in.2").decode() == "hello world\n"
            assert zf.read("out.2").decode() == "hello world\n"
            assert zf.read("err.2").decode() == ""
