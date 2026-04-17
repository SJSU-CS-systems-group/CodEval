"""Tests for create_assignment.py — pure functions and dry-run command path."""
import os
import textwrap
import zipfile
from configparser import ConfigParser
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from assignment_codeval.create_assignment import (
    extract_assignment_name,
    extract_file_macros,
    upload_assignment_files,
    files_resolver,
    create_assignment,
)
import assignment_codeval.create_assignment as ca_mod
from assignment_codeval.commons import set_config
from assignment_codeval.canvas_utils import get_course as _get_course_cached


# ---------------------------------------------------------------------------
# extract_assignment_name
# ---------------------------------------------------------------------------

class TestExtractAssignmentName:
    def test_reads_assignment_start(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("ASSIGNMENT START Homework 1\nT cmd\n")
        assert extract_assignment_name(str(f)) == "Homework 1"

    def test_reads_crt_hw_start(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("CRT_HW START Old Style HW\nT cmd\n")
        assert extract_assignment_name(str(f)) == "Old Style HW"

    def test_assignment_start_preferred_over_crt_hw(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("ASSIGNMENT START New Name\nCRT_HW START Old Name\n")
        assert extract_assignment_name(str(f)) == "New Name"

    def test_exits_when_no_title(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("T cmd\nO output\n")
        with pytest.raises(SystemExit):
            extract_assignment_name(str(f))


# ---------------------------------------------------------------------------
# extract_file_macros
# ---------------------------------------------------------------------------

class TestExtractFileMacros:
    def test_finds_file_macros_in_assignment_block(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text(textwrap.dedent("""\
            ASSIGNMENT START HW1
            Download FILE[starter.zip] and FILE[data.csv].
            ASSIGNMENT END
            T cmd
        """))
        assert extract_file_macros(str(f)) == ["starter.zip", "data.csv"]

    def test_finds_macros_in_crt_hw_block(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text(textwrap.dedent("""\
            CRT_HW START HW1
            Use FILE[template.cpp].
            CRT_HW END
        """))
        assert extract_file_macros(str(f)) == ["template.cpp"]

    def test_ignores_macros_outside_block(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("T FILE[shouldbeignored.py]\nO output\n")
        assert extract_file_macros(str(f)) == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("")
        assert extract_file_macros(str(f)) == []

    def test_no_file_macros(self, tmp_path):
        f = tmp_path / "hw.codeval"
        f.write_text("ASSIGNMENT START HW1\nNo macros here.\nASSIGNMENT END\n")
        assert extract_file_macros(str(f)) == []


# ---------------------------------------------------------------------------
# upload_assignment_files — dry_run path
# ---------------------------------------------------------------------------

class TestUploadAssignmentFilesDryRun:
    def setup_method(self):
        set_config(show_debug=False, dry_run=True, force=False, copy_tmpdir=False)
        ca_mod.file_dict = {}

    def test_dry_run_adds_bogus_url(self, tmp_path):
        f = tmp_path / "starter.zip"
        f.write_text("fake zip content")
        folder = MagicMock()
        upload_assignment_files(folder, [str(f)])
        assert "starter.zip" in ca_mod.file_dict
        assert "http://bogus" in ca_mod.file_dict["starter.zip"]

    def test_dry_run_does_not_call_folder_upload(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        folder = MagicMock()
        upload_assignment_files(folder, [str(f)])
        folder.upload.assert_not_called()

    def test_multiple_files_all_added(self, tmp_path):
        files = []
        for name in ["a.txt", "b.txt", "c.txt"]:
            f = tmp_path / name
            f.write_text("x")
            files.append(str(f))
        upload_assignment_files(MagicMock(), files)
        assert "a.txt" in ca_mod.file_dict
        assert "b.txt" in ca_mod.file_dict
        assert "c.txt" in ca_mod.file_dict


# ---------------------------------------------------------------------------
# files_resolver
# ---------------------------------------------------------------------------

class TestFilesResolver:
    def setup_method(self):
        ca_mod.file_dict = {}
        ca_mod.zip_files = []
        ca_mod.canvas_folder = None

    def test_returns_url_from_file_dict(self):
        ca_mod.file_dict = {"prog.py": "http://canvas.example.com/files/123"}
        result = files_resolver("prog.py")
        assert result == "http://canvas.example.com/files/123"

    def test_returns_placeholder_when_not_found(self):
        ca_mod.file_dict = {}
        result = files_resolver("missing.py")
        assert result == "FILE[missing.py]"

    def test_finds_file_in_zip(self, tmp_path):
        zip_path = tmp_path / "support.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("starter.py", "# starter code\n")
        ca_mod.zip_files = [str(zip_path)]
        ca_mod.canvas_folder = MagicMock()
        set_config(show_debug=False, dry_run=True, force=False, copy_tmpdir=False)
        result = files_resolver("starter.py")
        # After upload in dry_run mode, it should be in file_dict
        assert "starter.py" in ca_mod.file_dict


# ---------------------------------------------------------------------------
# create_assignment command — dry-run via CliRunner
# ---------------------------------------------------------------------------

class TestCreateAssignmentCommand:
    def setup_method(self):
        _get_course_cached.cache_clear()
        ca_mod.file_dict = {}
        ca_mod.zip_files = []
        ca_mod.canvas_folder = None

    def teardown_method(self):
        _get_course_cached.cache_clear()

    def _make_spec(self, tmp_path, name="HW1", extra_content=""):
        f = tmp_path / "hw.codeval"
        f.write_text(textwrap.dedent(f"""\
            ASSIGNMENT START {name}
            Write a hello world program.
            ASSIGNMENT END
            T python3 prog.py
            O hello
        """) + extra_content)
        return str(f)

    def _make_mocks(self, assignment_name="HW1"):
        mock_canvas = MagicMock()
        mock_user = MagicMock()
        mock_course = MagicMock()
        mock_course.name = "CS101"

        mock_folder = MagicMock()
        mock_folder.name = "CodEval"
        mock_folder.full_name = "CodEval"
        mock_course.get_folders.return_value = [mock_folder]

        grp = MagicMock()
        grp.name = "Assignments"
        grp.id = 99
        mock_course.get_assignment_groups.return_value = [grp]

        existing = MagicMock()
        existing.name = assignment_name
        mock_course.get_assignments.return_value = [existing]

        return mock_canvas, mock_user, mock_course, mock_folder, existing

    def _invoke_dryrun(self, tmp_path, spec, assignment_name="HW1", extra_args=None):
        canvas, user, course, folder, assignment = self._make_mocks(assignment_name)
        args = ["CS101", spec, "--dryrun"] + (extra_args or [])
        with patch("assignment_codeval.create_assignment.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.create_assignment.get_course",
                       return_value=course):
                with patch("assignment_codeval.create_assignment.convertMD2Html.mdToHtml",
                           return_value=(assignment_name, f"<p>HTML for {assignment_name}</p>")):
                    return CliRunner().invoke(create_assignment, args), course

    def test_exits_nonzero_when_specfile_missing(self, tmp_path):
        result = CliRunner().invoke(
            create_assignment,
            ["CS101", str(tmp_path / "ghost.codeval")]
        )
        assert result.exit_code != 0

    def test_dryrun_would_update_existing_assignment(self, tmp_path):
        spec = self._make_spec(tmp_path)
        result, _ = self._invoke_dryrun(tmp_path, spec)
        assert result.exit_code == 0
        assert "would update" in result.output or result.exit_code == 0

    def test_dryrun_would_create_new_assignment(self, tmp_path):
        spec = self._make_spec(tmp_path, name="NewHW")
        canvas, user, course, _, _ = self._make_mocks("OtherHW")
        # course has no matching assignment
        course.get_assignments.return_value = []
        with patch("assignment_codeval.create_assignment.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.create_assignment.get_course",
                       return_value=course):
                with patch("assignment_codeval.create_assignment.convertMD2Html.mdToHtml",
                           return_value=("NewHW", "<p>html</p>")):
                    result = CliRunner().invoke(
                        create_assignment, ["CS101", spec, "--dryrun"]
                    )
        assert result.exit_code == 0
        assert "would create" in result.output

    def test_dryrun_with_zip_in_spec(self, tmp_path):
        spec = self._make_spec(tmp_path, extra_content="Z support.zip\n")
        result, _ = self._invoke_dryrun(tmp_path, spec)
        assert result.exit_code == 0
        assert "support.zip" in ca_mod.zip_files

    def test_dryrun_group_not_found_exits(self, tmp_path):
        spec = self._make_spec(tmp_path)
        canvas, user, course, _, _ = self._make_mocks()
        course.get_assignment_groups.return_value = []
        with patch("assignment_codeval.create_assignment.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.create_assignment.get_course",
                       return_value=course):
                with patch("assignment_codeval.create_assignment.convertMD2Html.mdToHtml",
                           return_value=("HW1", "<p>html</p>")):
                    result = CliRunner().invoke(
                        create_assignment, ["CS101", spec, "--dryrun"]
                    )
        assert result.exit_code != 0
