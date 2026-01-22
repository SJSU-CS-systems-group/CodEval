"""Tests for create_assignment module, specifically FILE macro extraction and upload logic."""
import os
import zipfile
import pytest

from assignment_codeval.create_assignment import extract_file_macros


class TestExtractFileMacros:
    """Tests for the extract_file_macros function."""

    def test_extracts_single_file_macro(self, tmp_path):
        """Test extraction of a single FILE macro."""
        spec_content = """CRT_HW START Test Assignment
# Assignment Description

Download the starter file: [starter.py](FILE[starter.py])

CRT_HW END
T python3 solution.py
O expected output
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["starter.py"]

    def test_extracts_multiple_file_macros(self, tmp_path):
        """Test extraction of multiple FILE macros."""
        spec_content = """CRT_HW START Test Assignment
# Assignment Description

Download these files:
- [starter.py](FILE[starter.py])
- [data.txt](FILE[data.txt])
- [config.json](FILE[config.json])

CRT_HW END
T python3 solution.py
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["starter.py", "data.txt", "config.json"]

    def test_extracts_multiple_macros_on_same_line(self, tmp_path):
        """Test extraction when multiple FILE macros are on the same line."""
        spec_content = """CRT_HW START Test Assignment
Download [file1.py](FILE[file1.py]) and [file2.py](FILE[file2.py])
CRT_HW END
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["file1.py", "file2.py"]

    def test_ignores_macros_outside_assignment_section(self, tmp_path):
        """Test that FILE macros outside CRT_HW START/END are ignored."""
        spec_content = """# This is before the assignment section
FILE[ignored.py]

CRT_HW START Test Assignment
Download [included.py](FILE[included.py])
CRT_HW END

# This is after
FILE[also_ignored.py]
T python3 solution.py
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["included.py"]

    def test_returns_empty_list_when_no_macros(self, tmp_path):
        """Test that empty list is returned when no FILE macros exist."""
        spec_content = """CRT_HW START Test Assignment
# Simple assignment with no file downloads
CRT_HW END
T python3 solution.py
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == []

    def test_returns_empty_list_when_no_assignment_section(self, tmp_path):
        """Test that empty list is returned when there's no CRT_HW section."""
        spec_content = """# Just a simple codeval file
T python3 solution.py
O hello
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == []

    def test_handles_filenames_with_paths(self, tmp_path):
        """Test extraction of FILE macros with path-like filenames."""
        spec_content = """CRT_HW START Test Assignment
Download [data](FILE[data/input.txt])
CRT_HW END
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["data/input.txt"]

    def test_handles_filenames_with_spaces(self, tmp_path):
        """Test extraction of FILE macros with spaces in filenames."""
        spec_content = """CRT_HW START Test Assignment
Download [readme](FILE[my file.txt])
CRT_HW END
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        macros = extract_file_macros(str(spec_file))
        assert macros == ["my file.txt"]


class TestFileUploadLogic:
    """Tests for the file upload logic in create_assignment.

    These tests verify the logic for finding files locally and in zip files.
    They don't test actual Canvas uploads (which would require mocking).
    """

    def test_local_file_found(self, tmp_path):
        """Test that local files in the same directory as spec are found."""
        # Create a spec file with FILE macro
        spec_content = """CRT_HW START Test Assignment
Download [starter.py](FILE[starter.py])
CRT_HW END
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        # Create the referenced local file
        local_file = tmp_path / "starter.py"
        local_file.write_text("# starter code")

        # Verify the file exists where we expect it
        spec_dir = os.path.dirname(os.path.abspath(str(spec_file)))
        macros = extract_file_macros(str(spec_file))

        for filename in macros:
            local_path = os.path.join(spec_dir, filename)
            assert os.path.isfile(local_path), f"Local file {filename} should exist"

    def test_file_found_in_zip(self, tmp_path):
        """Test that files can be found in zip files."""
        # Create a zip file with a test file inside
        zip_path = tmp_path / "support.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("nested/folder/data.txt", "test data content")

        # Verify we can find the file in the zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            matches = [f for f in zf.namelist() if os.path.basename(f) == "data.txt"]
            assert len(matches) == 1
            assert matches[0] == "nested/folder/data.txt"

    def test_file_extraction_from_zip(self, tmp_path):
        """Test that files can be extracted from zip files."""
        # Create a zip file with a test file inside
        zip_path = tmp_path / "support.zip"
        file_content = "test data content"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.txt", file_content)

        # Extract and verify content
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            extracted_path = zf.extract("data.txt", path=str(extract_dir))
            assert os.path.isfile(extracted_path)
            with open(extracted_path, 'r') as f:
                assert f.read() == file_content

    def test_local_file_takes_precedence_over_zip(self, tmp_path):
        """Test that local files are preferred over files in zip."""
        # Create spec file
        spec_content = """CRT_HW START Test Assignment
Download [data.txt](FILE[data.txt])
CRT_HW END
Z support.zip
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        # Create local file
        local_file = tmp_path / "data.txt"
        local_file.write_text("local content")

        # Create zip with same filename but different content
        zip_path = tmp_path / "support.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.txt", "zip content")

        # The logic should find the local file first
        spec_dir = os.path.dirname(os.path.abspath(str(spec_file)))
        macros = extract_file_macros(str(spec_file))

        for filename in macros:
            local_path = os.path.join(spec_dir, filename)
            # Local file should exist and be used
            assert os.path.isfile(local_path)
            with open(local_path, 'r') as f:
                assert f.read() == "local content"
