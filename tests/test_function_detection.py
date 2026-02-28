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
