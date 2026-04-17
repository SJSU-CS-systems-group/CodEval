"""Unit tests for pure helper functions in submissions.py."""
import os
import zipfile
import pytest

from assignment_codeval.submissions import (
    _parse_codeval_test_info,
    _read_of_file_content,
    _extract_codeval_title,
    find_codeval_file,
)


# ---------------------------------------------------------------------------
# _parse_codeval_test_info
# ---------------------------------------------------------------------------

class TestParseCodevalTestInfo:
    def _write(self, tmp_path, content):
        f = tmp_path / "hw.codeval"
        f.write_text(content)
        return str(f)

    def test_single_visible_test(self, tmp_path):
        path = self._write(tmp_path, "T python3 prog.py\nO hello\n")
        info = _parse_codeval_test_info(path)
        assert 1 in info
        assert info[1]["hidden"] is False

    def test_hidden_test(self, tmp_path):
        path = self._write(tmp_path, "HT python3 prog.py\nO hello\n")
        info = _parse_codeval_test_info(path)
        assert info[1]["hidden"] is True

    def test_multiple_tests(self, tmp_path):
        path = self._write(tmp_path, "T cmd1\nO out1\nT cmd2\nO out2\nHT cmd3\nO out3\n")
        info = _parse_codeval_test_info(path)
        assert len(info) == 3
        assert info[1]["hidden"] is False
        assert info[2]["hidden"] is False
        assert info[3]["hidden"] is True

    def test_crt_hw_block_skipped(self, tmp_path):
        content = (
            "CRT_HW START\n"
            "T ignored_cmd\n"
            "O ignored\n"
            "CRT_HW END\n"
            "T python3 real.py\n"
            "O real output\n"
        )
        path = self._write(tmp_path, content)
        info = _parse_codeval_test_info(path)
        assert len(info) == 1

    def test_of_file_recorded(self, tmp_path):
        path = self._write(tmp_path, "T python3 prog.py\nOF expected.txt\n")
        info = _parse_codeval_test_info(path)
        assert info[1]["of_file"] == "expected.txt"

    def test_no_test_cases(self, tmp_path):
        path = self._write(tmp_path, "# just a comment\nC g++ prog.cpp\n")
        info = _parse_codeval_test_info(path)
        assert info == {}

    def test_tcmd_counts_as_test(self, tmp_path):
        path = self._write(tmp_path, "TCMD make run\nO output\n")
        info = _parse_codeval_test_info(path)
        assert 1 in info

    def test_of_only_recorded_for_first_per_test(self, tmp_path):
        path = self._write(tmp_path, "T cmd\nOF first.txt\nOF second.txt\n")
        info = _parse_codeval_test_info(path)
        assert info[1]["of_file"] == "first.txt"


# ---------------------------------------------------------------------------
# _read_of_file_content
# ---------------------------------------------------------------------------

class TestReadOfFileContent:
    def test_reads_file_in_codeval_dir(self, tmp_path):
        codeval = tmp_path / "hw.codeval"
        codeval.write_text("T cmd\nOF expected.txt\n")
        expected = tmp_path / "expected.txt"
        expected.write_text("expected output\n")
        result = _read_of_file_content("expected.txt", str(codeval))
        assert result == "expected output\n"

    def test_returns_none_when_file_missing(self, tmp_path):
        codeval = tmp_path / "hw.codeval"
        codeval.write_text("T cmd\n")
        result = _read_of_file_content("missing.txt", str(codeval))
        assert result is None

    def test_reads_from_zip_file(self, tmp_path):
        zip_path = tmp_path / "support.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("expected.txt", "from zip\n")
        codeval = tmp_path / "hw.codeval"
        codeval.write_text(f"Z support.zip\nT cmd\nOF expected.txt\n")
        result = _read_of_file_content("expected.txt", str(codeval))
        assert result == "from zip\n"

    def test_direct_file_preferred_over_zip(self, tmp_path):
        zip_path = tmp_path / "support.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("expected.txt", "from zip\n")
        expected = tmp_path / "expected.txt"
        expected.write_text("from file\n")
        codeval = tmp_path / "hw.codeval"
        codeval.write_text(f"Z support.zip\nT cmd\nOF expected.txt\n")
        result = _read_of_file_content("expected.txt", str(codeval))
        assert result == "from file\n"


# ---------------------------------------------------------------------------
# _extract_codeval_title
# ---------------------------------------------------------------------------

class TestExtractCodevalTitle:
    def test_extracts_assignment_start_title(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("ASSIGNMENT START My Assignment\nT cmd\n")
        assert _extract_codeval_title(str(f)) == "My Assignment"

    def test_extracts_crt_hw_start_title(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("CRT_HW START Old Assignment\nT cmd\n")
        assert _extract_codeval_title(str(f)) == "Old Assignment"

    def test_returns_none_when_no_title_line(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("T cmd\nO output\n")
        assert _extract_codeval_title(str(f)) is None

    def test_returns_none_for_missing_file(self, tmp_path):
        assert _extract_codeval_title(str(tmp_path / "ghost.codeval")) is None

    def test_returns_none_for_empty_title(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("ASSIGNMENT START\nT cmd\n")
        assert _extract_codeval_title(str(f)) is None


# ---------------------------------------------------------------------------
# find_codeval_file
# ---------------------------------------------------------------------------

class TestFindCodevalFile:
    def test_finds_by_exact_filename(self, tmp_path):
        f = tmp_path / "hw1.codeval"
        f.write_text("T cmd\n")
        result = find_codeval_file(str(tmp_path), "hw1")
        assert result == str(f)

    def test_case_insensitive_filename_match(self, tmp_path):
        f = tmp_path / "HW1.codeval"
        f.write_text("T cmd\n")
        result = find_codeval_file(str(tmp_path), "hw1")
        assert result is not None

    def test_finds_by_title_fallback(self, tmp_path):
        f = tmp_path / "assignment.codeval"
        f.write_text("ASSIGNMENT START My Cool HW\nT cmd\n")
        result = find_codeval_file(str(tmp_path), "My Cool HW")
        assert result == str(f)

    def test_returns_none_when_not_found(self, tmp_path):
        result = find_codeval_file(str(tmp_path), "nonexistent")
        assert result is None

    def test_despace_applied_to_assignment_name(self, tmp_path):
        f = tmp_path / "my_hw.codeval"
        f.write_text("T cmd\n")
        result = find_codeval_file(str(tmp_path), "my hw")
        assert result == str(f)
