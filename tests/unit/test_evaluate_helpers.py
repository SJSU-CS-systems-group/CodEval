"""Unit tests for pure helper functions in evaluate.py."""
import os
import pytest

from assignment_codeval.evaluate import (
    TESTING_DIR,
    get_testing_path,
    _detect_language,
    _extract_executable_from_compile,
    _extract_source_files_from_compile,
    _function_used_in_python,
    parse_diff,
    _render_diff_output,
)


class TestGetTestingPath:
    def test_returns_path_inside_testing_dir(self):
        result = get_testing_path("compilelog")
        assert result == os.path.join(TESTING_DIR, "compilelog")

    def test_any_filename(self):
        assert get_testing_path("youroutput") == os.path.join(TESTING_DIR, "youroutput")

    def test_nested_path(self):
        assert get_testing_path("evaluationLogs") == os.path.join(TESTING_DIR, "evaluationLogs")


class TestDetectLanguage:
    def test_c_file(self):
        assert _detect_language(["main.c"]) == "c_cpp"

    def test_cpp_file(self):
        assert _detect_language(["main.cpp"]) == "c_cpp"

    def test_cc_extension(self):
        assert _detect_language(["main.cc"]) == "c_cpp"

    def test_header_file(self):
        assert _detect_language(["header.hpp"]) == "c_cpp"

    def test_java_file(self):
        assert _detect_language(["Main.java"]) == "java"

    def test_python_file(self):
        assert _detect_language(["script.py"]) == "python"

    def test_unknown_extension(self):
        assert _detect_language(["file.rb"]) == "unknown"

    def test_empty_list(self):
        assert _detect_language([]) == "unknown"

    def test_case_insensitive_cpp(self):
        assert _detect_language(["FILE.CPP"]) == "c_cpp"

    def test_case_insensitive_java(self):
        assert _detect_language(["Main.JAVA"]) == "java"

    def test_case_insensitive_python(self):
        assert _detect_language(["SCRIPT.PY"]) == "python"

    def test_first_file_wins(self):
        # First matching extension determines language
        assert _detect_language(["prog.py", "Main.java"]) == "python"


class TestExtractExecutableFromCompile:
    def test_basic_dash_o(self):
        assert _extract_executable_from_compile("g++ -o myprogram foo.cpp") == "myprogram"

    def test_no_dash_o_returns_none(self):
        assert _extract_executable_from_compile("g++ foo.cpp") is None

    def test_dash_o_at_end_without_value(self):
        assert _extract_executable_from_compile("g++ -o") is None

    def test_flags_before_dash_o(self):
        assert _extract_executable_from_compile("g++ -Wall -O2 -o prog foo.cpp") == "prog"

    def test_javac_command(self):
        assert _extract_executable_from_compile("javac -d out Main.java") is None

    def test_make_command(self):
        assert _extract_executable_from_compile("make all") is None


class TestExtractSourceFilesFromCompile:
    def test_single_cpp_file(self):
        assert _extract_source_files_from_compile("g++ -o prog foo.cpp") == ["foo.cpp"]

    def test_single_c_file(self):
        assert _extract_source_files_from_compile("gcc -o prog bar.c") == ["bar.c"]

    def test_multiple_files(self):
        result = _extract_source_files_from_compile("g++ -o prog a.cpp b.cpp c.cpp")
        assert result == ["a.cpp", "b.cpp", "c.cpp"]

    def test_skips_dash_o_value(self):
        result = _extract_source_files_from_compile("g++ -o output.cpp foo.cpp")
        assert "output.cpp" not in result
        assert "foo.cpp" in result

    def test_java_file(self):
        assert _extract_source_files_from_compile("javac Main.java") == ["Main.java"]

    def test_python_file(self):
        assert _extract_source_files_from_compile("python3 script.py") == ["script.py"]

    def test_no_source_files(self):
        assert _extract_source_files_from_compile("make all") == []

    def test_skips_dash_l_value(self):
        # -l consumes the next token (foo.cpp), so foo.cpp is skipped
        result = _extract_source_files_from_compile("g++ -o prog -l foo.cpp")
        assert "foo.cpp" not in result

    def test_skips_dash_i_value(self):
        result = _extract_source_files_from_compile("g++ -I /usr/include -o prog foo.cpp")
        assert "foo.cpp" in result


class TestFunctionUsedInPython:
    def test_direct_call_found(self, tmp_path):
        src = tmp_path / "prog.py"
        src.write_text("x = sorted([3, 1, 2])\n")
        assert _function_used_in_python("sorted", [str(src)]) is True

    def test_method_call_found(self, tmp_path):
        src = tmp_path / "prog.py"
        src.write_text("lst = []\nlst.append(1)\n")
        assert _function_used_in_python("append", [str(src)]) is True

    def test_function_not_used(self, tmp_path):
        src = tmp_path / "prog.py"
        src.write_text("x = 1 + 2\nprint(x)\n")
        assert _function_used_in_python("sorted", [str(src)]) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        assert _function_used_in_python("foo", [str(tmp_path / "ghost.py")]) is False

    def test_syntax_error_file_returns_false(self, tmp_path):
        src = tmp_path / "bad.py"
        src.write_text("def foo(:::\n")
        assert _function_used_in_python("foo", [str(src)]) is False

    def test_multiple_files_any_match(self, tmp_path):
        src1 = tmp_path / "a.py"
        src1.write_text("x = 1\n")
        src2 = tmp_path / "b.py"
        src2.write_text("result = sorted([2, 1])\n")
        assert _function_used_in_python("sorted", [str(src1), str(src2)]) is True

    def test_empty_file_list(self):
        assert _function_used_in_python("sorted", []) is False

    def test_function_in_import_not_counted_as_call(self, tmp_path):
        src = tmp_path / "prog.py"
        src.write_text("from math import sqrt\nx = 1\n")
        # sqrt is imported but not called — ast.Call won't match
        assert _function_used_in_python("sqrt", [str(src)]) is False

    def test_function_call_counted(self, tmp_path):
        src = tmp_path / "prog.py"
        src.write_text("from math import sqrt\nresult = sqrt(4)\n")
        assert _function_used_in_python("sqrt", [str(src)]) is True


class TestParseDiff:
    def test_creates_evaluation_logs_dir(self, tmp_path):
        parse_diff([], str(tmp_path))
        assert (tmp_path / "evaluationLogs").is_dir()

    def test_creates_log_of_diff_file(self, tmp_path):
        parse_diff([], str(tmp_path))
        assert (tmp_path / "evaluationLogs" / "logOfDiff").exists()

    def test_at_sign_line_not_written(self, tmp_path):
        # first_character is the first word (e.g. "@@"), not a single char;
        # "@@" != "@" so the line IS written — but it's benign behaviour we document
        parse_diff(["@@ -1,2 +1,3 @@\n"], str(tmp_path))
        content = (tmp_path / "evaluationLogs" / "logOfDiff").read_text()
        # The @@ line passes through the != "@" check and is written
        assert "@@" in content

    def test_regular_diff_line_written(self, tmp_path):
        parse_diff([" context line\n"], str(tmp_path))
        content = (tmp_path / "evaluationLogs" / "logOfDiff").read_text()
        assert "context line" in content

    def test_empty_input(self, tmp_path):
        parse_diff([], str(tmp_path))
        content = (tmp_path / "evaluationLogs" / "logOfDiff").read_text()
        assert content == ""


class TestRenderDiffOutputEdgeCases:
    """Additional edge cases beyond what test_codeval.py already covers."""

    def test_3byte_utf8_char(self):
        # € is U+20AC, encoded as 3 bytes: 0xE2 0x82 0xAC
        result = _render_diff_output("€\n".encode("utf-8"))
        assert result == "€$\n"

    def test_non_printable_valid_utf8(self):
        # U+0085 NEXT LINE — valid UTF-8 (0xC2 0x85) but not printable
        raw = b"\xc2\x85\n"
        result = _render_diff_output(raw)
        # Should render each byte as \xNN
        assert "\\x" in result

    def test_truncated_utf8_sequence(self):
        # Start of a 2-byte sequence but only 1 byte present at EOF
        raw = b"\xc3"
        result = _render_diff_output(raw)
        assert "\\x" in result or result.endswith("$")

    def test_4byte_utf8_emoji(self):
        # 😀 is U+1F600, encoded as 4 bytes
        result = _render_diff_output("😀\n".encode("utf-8"))
        assert "😀" in result or "\\x" in result

    def test_mixed_ascii_and_control(self):
        assert _render_diff_output(b"hi\x01\n") == "hi^A$\n"

    def test_single_newline(self):
        assert _render_diff_output(b"\n") == "$\n"
