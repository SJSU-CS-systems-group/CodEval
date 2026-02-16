"""Tests for create_assignment module, specifically FILE macro extraction and upload logic."""
import os
import zipfile
import pytest

from assignment_codeval.create_assignment import extract_file_macros
from assignment_codeval.convertMD2Html import sampleTestCases, mdToHtml, ansi_to_html


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


class TestAnsiToHtml:
    """Tests for ANSI escape code to HTML conversion."""

    def test_no_ansi_codes(self):
        """Plain text is returned unchanged."""
        assert ansi_to_html("hello world") == "hello world"

    def test_foreground_color(self):
        """ANSI foreground color becomes a span with color style."""
        text = "\x1b[31mred text\x1b[0m"
        html = ansi_to_html(text)
        assert '<span style="color:red">' in html
        assert "red text" in html
        assert "</span>" in html

    def test_background_color(self):
        """ANSI background color becomes a span with background-color style."""
        text = "\x1b[44m  blue bg  \x1b[0m"
        html = ansi_to_html(text)
        assert '<span style="background-color:blue">' in html

    def test_bold(self):
        """ANSI bold becomes font-weight:bold."""
        text = "\x1b[1mbold\x1b[0m"
        html = ansi_to_html(text)
        assert '<span style="font-weight:bold">' in html

    def test_combined_codes(self):
        """Multiple ANSI codes produce nested spans."""
        text = "\x1b[1m\x1b[33mA \x1b[0m"
        html = ansi_to_html(text)
        assert "font-weight:bold" in html
        assert "color:#a50" in html
        assert "A " in html

    def test_reset_closes_all_spans(self):
        """Reset code closes all open spans."""
        text = "\x1b[1m\x1b[33mbold yellow\x1b[0m plain"
        html = ansi_to_html(text)
        assert html.endswith("plain")
        assert html.count("<span") == html.count("</span>")

    def test_compound_codes(self):
        """Semicolon-separated codes in a single escape sequence."""
        text = "\x1b[1;31mbold red\x1b[0m"
        html = ansi_to_html(text)
        assert "font-weight:bold" in html
        assert "color:red" in html

    def test_unclosed_spans_closed_at_end(self):
        """Spans without a reset are closed at the end."""
        text = "\x1b[31mred text"
        html = ansi_to_html(text)
        assert html.count("<span") == html.count("</span>")


class TestSampleTestCases:
    """Tests for the sampleTestCases function in convertMD2Html."""

    def test_of_tag_reads_file_content(self, tmp_path):
        """Test that OF tags read and inline the file content."""
        (tmp_path / "expected.txt").write_text("hello world\n")
        examples = [
            "T ./program\n",
            "I yes\n",
            "OF expected.txt\n",
            "O some output\n",
            "X 0\n",
        ]
        html = sampleTestCases(examples, 1, str(tmp_path))
        assert "hello world" in html
        assert "expected.txt" not in html

    def test_of_tag_converts_ansi_to_html(self, tmp_path):
        """Test that ANSI codes in OF file content are converted to HTML."""
        (tmp_path / "expected.txt").write_text("\x1b[1m\x1b[33mA \x1b[0m\x1b[44m  \x1b[0m\n")
        examples = [
            "T ./program\n",
            "OF expected.txt\n",
        ]
        html = sampleTestCases(examples, 1, str(tmp_path))
        assert "font-weight:bold" in html
        assert "\x1b[" not in html

    def test_of_tag_falls_back_when_file_missing(self):
        """Test that OF tags fall back to showing filename when file is not found."""
        examples = [
            "T ./program\n",
            "OF nonexistent.txt\n",
        ]
        html = sampleTestCases(examples, 1, "/no/such/dir")
        assert "nonexistent.txt" in html

    def test_o_tag_preserves_leading_and_trailing_spaces(self):
        """Test that O tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "O  there is a space \n",
        ]
        html = sampleTestCases(examples, 1)
        assert " there is a space " in html

    def test_i_tag_preserves_leading_and_trailing_spaces(self):
        """Test that I tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "I  leading space\n",
            "O expected\n",
        ]
        html = sampleTestCases(examples, 1)
        assert " leading space" in html

    def test_ob_tag_preserves_leading_and_trailing_spaces(self):
        """Test that OB tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "OB  spaced output \n",
        ]
        html = sampleTestCases(examples, 1)
        assert " spaced output " in html

    def test_ib_tag_preserves_leading_and_trailing_spaces(self):
        """Test that IB tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "IB  spaced input \n",
            "O expected\n",
        ]
        html = sampleTestCases(examples, 1)
        assert " spaced input " in html

    def test_e_tag_preserves_leading_and_trailing_spaces(self):
        """Test that E tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "E  error with spaces \n",
        ]
        html = sampleTestCases(examples, 1)
        assert " error with spaces " in html

    def test_eb_tag_preserves_leading_and_trailing_spaces(self):
        """Test that EB tag values preserve leading and trailing whitespace."""
        examples = [
            "T ./program\n",
            "EB  bare error \n",
        ]
        html = sampleTestCases(examples, 1)
        assert " bare error " in html

    def test_ob_tag_included_in_html(self):
        """Test that OB tags are included in sample test case HTML output."""
        examples = [
            "T ./program\n",
            "OB output without newline\n",
        ]
        html = sampleTestCases(examples, 1)
        assert "output without newline" in html

    def test_if_tag_reads_file_content(self, tmp_path):
        """Test that IF tags read and inline the file content."""
        (tmp_path / "input.txt").write_text("file input data\n")
        examples = [
            "T ./program\n",
            "IF input.txt\n",
            "O expected\n",
        ]
        html = sampleTestCases(examples, 1, str(tmp_path))
        assert "file input data" in html
        assert "input.txt" not in html

    def test_ib_tag_included_in_html(self):
        """Test that IB tags are included in sample test case HTML output."""
        examples = [
            "T ./program\n",
            "IB bare input\n",
            "O expected\n",
        ]
        html = sampleTestCases(examples, 1)
        assert "bare input" in html

    def test_eb_tag_included_in_html(self):
        """Test that EB tags are included in sample test case HTML output."""
        examples = [
            "T ./program\n",
            "EB error output\n",
        ]
        html = sampleTestCases(examples, 1)
        assert "error output" in html


class TestMdToHtmlTagCollection:
    """Tests that mdToHtml collects multi-char tags (OF, OB, IF, IB, EB) for sample test cases."""

    def test_of_tag_reads_file_content(self, tmp_path):
        """Test that OF tag file content appears in the generated HTML."""
        spec_content = """CRT_HW START Test Assignment
# Description

EXMPLS 1

CRT_HW END
T ./program
I yes
OF expected.txt
O some output
X 0
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)
        (tmp_path / "expected.txt").write_text("file output content\n")

        from unittest.mock import patch
        with patch('assignment_codeval.convertMD2Html.get_config') as mock_config:
            mock_config.return_value.dry_run = False
            (name, html) = mdToHtml(str(spec_file))

        assert "file output content" in html

    def test_compile_macro_replaced_with_c_tag(self, tmp_path):
        """Test that COMPILE macro is replaced with the C tag value."""
        spec_content = """CRT_HW START Test Assignment
# Compiling

    COMPILE

CRT_HW END
C g++ main.cpp -o main -std=c++23
T ./main
O hello
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        from unittest.mock import patch
        with patch('assignment_codeval.convertMD2Html.get_config') as mock_config:
            mock_config.return_value.dry_run = False
            (name, html) = mdToHtml(str(spec_file))

        assert "g++ main.cpp -o main -std=c++23" in html
        assert "COMPILE" not in html

    def test_compile_macro_unchanged_without_c_tag(self, tmp_path):
        """Test that COMPILE macro is left as-is when there is no C tag."""
        spec_content = """CRT_HW START Test Assignment
# Compiling

    COMPILE

CRT_HW END
T ./main
O hello
"""
        spec_file = tmp_path / "test.codeval"
        spec_file.write_text(spec_content)

        from unittest.mock import patch
        with patch('assignment_codeval.convertMD2Html.get_config') as mock_config:
            mock_config.return_value.dry_run = False
            (name, html) = mdToHtml(str(spec_file))

        assert "COMPILE" in html
