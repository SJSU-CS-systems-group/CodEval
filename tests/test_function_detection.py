"""Unit tests for CF/NCF function detection helpers.

Tests the three detection paths introduced in evaluate.py:
  - C/C++:  objdump -t on compiled artifact
  - Java:   javap -c on .class file
  - Python: ast module on source

C++ and Java tests are skipped automatically when the required tools
are not available (e.g. on macOS without a full JDK install).
"""

import os
import shutil
import subprocess
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Tool availability guards
# ---------------------------------------------------------------------------

def _tool_works(*cmd):
    """Return True if cmd exits with code 0."""
    try:
        result = subprocess.run(list(cmd), capture_output=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


HAS_GPP_OBJDUMP = (
    shutil.which("g++") is not None
    and shutil.which("objdump") is not None
    and _tool_works("g++", "--version")
)

HAS_JAVA = _tool_works("javac", "--version") and _tool_works("javap", "-version")


# ---------------------------------------------------------------------------
# C++ — objdump path
# ---------------------------------------------------------------------------

CPP_SOURCE = """\
#include <iostream>
void greet() { std::cout << "Hello World" << std::endl; }
int main() { greet(); return 0; }
"""


@pytest.mark.skipif(not HAS_GPP_OBJDUMP, reason="g++ or objdump not available")
class TestCppFunctionDetection:
    """_function_used_in_c_cpp uses objdump -t on the compiled artifact."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.src = os.path.join(self.tmpdir, "sample.cpp")
        self.exe = os.path.join(self.tmpdir, "sample")
        with open(self.src, "w") as f:
            f.write(CPP_SOURCE)
        subprocess.run(
            ["g++", "-o", self.exe, self.src],
            check=True,
            capture_output=True,
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detects_used_function(self):
        from assignment_codeval.evaluate import _function_used_in_c_cpp
        assert _function_used_in_c_cpp("greet", [self.src]) is True

    def test_returns_false_for_unused_function(self):
        from assignment_codeval.evaluate import _function_used_in_c_cpp
        assert _function_used_in_c_cpp("forbidden_func", [self.src]) is False

    def test_returns_none_when_no_artifact(self):
        """No compiled artifact → caller should fall back to regex."""
        from assignment_codeval.evaluate import _function_used_in_c_cpp
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "uncompiled.cpp")
            with open(src, "w") as f:
                f.write("int main() { return 0; }\n")
            assert _function_used_in_c_cpp("greet", [src]) is None


# ---------------------------------------------------------------------------
# Java — javap path
# ---------------------------------------------------------------------------

JAVA_SOURCE = """\
public class SampleCfDetect {
    public static void greet() { System.out.println("Hello World"); }
    public static void main(String[] args) { greet(); }
}
"""


@pytest.mark.skipif(not HAS_JAVA, reason="javac or javap not available")
class TestJavaFunctionDetection:
    """_function_used_in_java uses javap -c on the compiled .class file."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.src = os.path.join(self.tmpdir, "SampleCfDetect.java")
        with open(self.src, "w") as f:
            f.write(JAVA_SOURCE)
        subprocess.run(
            ["javac", self.src],
            check=True,
            capture_output=True,
            cwd=self.tmpdir,
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detects_used_method(self):
        from assignment_codeval.evaluate import _function_used_in_java
        assert _function_used_in_java("greet", [self.src]) is True

    def test_returns_false_for_unused_method(self):
        from assignment_codeval.evaluate import _function_used_in_java
        assert _function_used_in_java("forbidden_func", [self.src]) is False

    def test_returns_none_when_no_class_file(self):
        """No .class file → caller should fall back to regex."""
        from assignment_codeval.evaluate import _function_used_in_java
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "Uncompiled.java")
            with open(src, "w") as f:
                f.write(
                    "public class Uncompiled { public static void main(String[] a) {} }\n"
                )
            assert _function_used_in_java("greet", [src]) is None

    def test_cf_no_filename_detects_used_method(self, capsys):
        import assignment_codeval.evaluate as ev
        old_cmd = ev.last_compile_command
        old_cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            ev.last_compile_command = f"javac SampleCfDetect.java"
            ev.test_case_count = 0
            ev.check_function("greet")
        finally:
            ev.last_compile_command = old_cmd
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out

    def test_cf_no_filename_fails_for_unused_method(self, capsys):
        import assignment_codeval.evaluate as ev
        old_cmd = ev.last_compile_command
        old_cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            ev.last_compile_command = f"javac SampleCfDetect.java"
            ev.test_case_count = 0
            ev.check_function("forbidden_func")
        finally:
            ev.last_compile_command = old_cmd
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out

    def test_ncf_no_filename_passes_for_absent_method(self, capsys):
        import assignment_codeval.evaluate as ev
        old_cmd = ev.last_compile_command
        old_cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            ev.last_compile_command = f"javac SampleCfDetect.java"
            ev.test_case_count = 0
            ev.check_not_function("forbidden_func")
        finally:
            ev.last_compile_command = old_cmd
            os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out


# ---------------------------------------------------------------------------
# Python — ast path
# ---------------------------------------------------------------------------

class TestPythonFunctionDetection:
    """_function_used_in_python uses the ast module; no external tools needed."""

    def _write_source(self, code):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write(code)
        f.close()
        return f.name

    def test_detects_direct_call(self):
        from assignment_codeval.evaluate import _function_used_in_python
        fname = self._write_source("print('hello')\nlen([1, 2])\n")
        try:
            assert _function_used_in_python("print", [fname]) is True
            assert _function_used_in_python("len", [fname]) is True
        finally:
            os.unlink(fname)

    def test_detects_attribute_call(self):
        from assignment_codeval.evaluate import _function_used_in_python
        fname = self._write_source("items = []\nitems.append(1)\n")
        try:
            assert _function_used_in_python("append", [fname]) is True
        finally:
            os.unlink(fname)

    def test_returns_false_for_unused_function(self):
        from assignment_codeval.evaluate import _function_used_in_python
        fname = self._write_source("print('hello')\n")
        try:
            assert _function_used_in_python("eval", [fname]) is False
        finally:
            os.unlink(fname)

    def test_ignores_function_name_in_string(self):
        """A function name that only appears inside a string is not a call."""
        from assignment_codeval.evaluate import _function_used_in_python
        fname = self._write_source('x = "eval is dangerous"\n')
        try:
            assert _function_used_in_python("eval", [fname]) is False
        finally:
            os.unlink(fname)

    def test_ignores_function_name_in_comment(self):
        """A function name that only appears in a comment is not a call."""
        from assignment_codeval.evaluate import _function_used_in_python
        fname = self._write_source("# eval would be bad here\nx = 1\n")
        try:
            assert _function_used_in_python("eval", [fname]) is False
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# Compile-command helpers
# ---------------------------------------------------------------------------

class TestExtractExecutableFromCompile:
    """_extract_executable_from_compile returns the -o argument."""

    def test_simple_c_compile(self):
        from assignment_codeval.evaluate import _extract_executable_from_compile
        assert _extract_executable_from_compile("cc -o mycalc --std=gnu11 mycalc.c") == "mycalc"

    def test_cpp_compile(self):
        from assignment_codeval.evaluate import _extract_executable_from_compile
        assert _extract_executable_from_compile("g++ -o sample_cf_functions sample_cf_functions.cpp") == "sample_cf_functions"

    def test_no_output_flag(self):
        from assignment_codeval.evaluate import _extract_executable_from_compile
        assert _extract_executable_from_compile("cc mycalc.c") is None

    def test_empty_command(self):
        from assignment_codeval.evaluate import _extract_executable_from_compile
        assert _extract_executable_from_compile("") is None


class TestExtractSourceFilesFromCompile:
    """_extract_source_files_from_compile returns source file arguments."""

    def test_single_c_file(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        assert _extract_source_files_from_compile("cc -o mycalc --std=gnu11 mycalc.c") == ["mycalc.c"]

    def test_cpp_file(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        assert _extract_source_files_from_compile("g++ -o out sample.cpp") == ["sample.cpp"]

    def test_multiple_source_files(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        result = _extract_source_files_from_compile("cc -o prog main.c util.c helper.c")
        assert result == ["main.c", "util.c", "helper.c"]

    def test_python_file(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        assert _extract_source_files_from_compile("python3 myscript.py") == ["myscript.py"]

    def test_java_file(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        assert _extract_source_files_from_compile("javac MyClass.java") == ["MyClass.java"]

    def test_skips_output_flag_value(self):
        """The value after -o should not be treated as a source file."""
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        result = _extract_source_files_from_compile("cc -o mycalc.exe mycalc.c")
        assert "mycalc.exe" not in result
        assert "mycalc.c" in result

    def test_empty_command(self):
        from assignment_codeval.evaluate import _extract_source_files_from_compile
        assert _extract_source_files_from_compile("") == []


# ---------------------------------------------------------------------------
# CF / NCF no-filename path (check_function / check_not_function)
# ---------------------------------------------------------------------------

class TestCheckFunctionNoFilename:
    """check_function and check_not_function infer source files from last_compile_command."""

    @pytest.mark.skipif(not HAS_GPP_OBJDUMP, reason="g++ or objdump not available")
    def test_cf_no_filename_detects_used_function(self, capsys):
        import assignment_codeval.evaluate as ev
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "sample.cpp")
            exe = os.path.join(tmpdir, "sample")
            with open(src, "w") as f:
                f.write(CPP_SOURCE)
            subprocess.run(["g++", "-o", exe, src], check=True, capture_output=True)
            old_cmd = ev.last_compile_command
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ev.last_compile_command = f"g++ -o sample sample.cpp"
                ev.test_case_count = 0
                ev.check_function("greet")
            finally:
                ev.last_compile_command = old_cmd
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out

    @pytest.mark.skipif(not HAS_GPP_OBJDUMP, reason="g++ or objdump not available")
    def test_cf_no_filename_fails_for_unused_function(self, capsys):
        import assignment_codeval.evaluate as ev
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "sample.cpp")
            exe = os.path.join(tmpdir, "sample")
            with open(src, "w") as f:
                f.write(CPP_SOURCE)
            subprocess.run(["g++", "-o", exe, src], check=True, capture_output=True)
            old_cmd = ev.last_compile_command
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ev.last_compile_command = f"g++ -o sample sample.cpp"
                ev.test_case_count = 0
                ev.check_function("forbidden_func")
            finally:
                ev.last_compile_command = old_cmd
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out

    def test_cf_no_filename_python_detects_used_function(self, capsys):
        """Python uses ast — no compiled artifact needed; no-filename path works."""
        import assignment_codeval.evaluate as ev
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "myscript.py")
            with open(src, "w") as f:
                f.write("print('hello')\nlen([1, 2])\n")
            old_cmd = ev.last_compile_command
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ev.last_compile_command = "python3 -m py_compile myscript.py"
                ev.test_case_count = 0
                ev.check_function("print")
            finally:
                ev.last_compile_command = old_cmd
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out

    def test_cf_no_filename_python_fails_for_unused_function(self, capsys):
        import assignment_codeval.evaluate as ev
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "myscript.py")
            with open(src, "w") as f:
                f.write("print('hello')\n")
            old_cmd = ev.last_compile_command
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ev.last_compile_command = "python3 -m py_compile myscript.py"
                ev.test_case_count = 0
                ev.check_function("eval")
            finally:
                ev.last_compile_command = old_cmd
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out

    def test_ncf_no_filename_python(self, capsys):
        """NCF without filename works for Python via the ast path."""
        import assignment_codeval.evaluate as ev
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "myscript.py")
            with open(src, "w") as f:
                f.write("print('hello')\n")
            old_cmd = ev.last_compile_command
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ev.last_compile_command = "python3 -m py_compile myscript.py"
                ev.test_case_count = 0
                ev.check_not_function("eval")
            finally:
                ev.last_compile_command = old_cmd
                os.chdir(old_cwd)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out
