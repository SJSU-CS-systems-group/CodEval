"""Pytest tests for CodEval test files."""
import glob
import os
import subprocess
import pytest

from assignment_codeval.evaluate import _render_diff_output

# Get all .codeval test files
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
CODEVAL_FILES = sorted(glob.glob(os.path.join(TEST_DIR, "*.codeval")))


def get_test_ids():
    """Generate test IDs from filenames."""
    return [os.path.basename(f).replace(".codeval", "") for f in CODEVAL_FILES]


@pytest.mark.parametrize("codeval_file", CODEVAL_FILES, ids=get_test_ids())
def test_codeval(codeval_file):
    """Run a .codeval test file and verify it passes."""
    test_name = os.path.basename(codeval_file)

    result = subprocess.run(
        ["assignment-codeval", "run-evaluation", test_name],
        cwd=TEST_DIR,
        capture_output=True,
        text=True,
    )

    # Print output for debugging
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    assert result.returncode == 0, f"Test {test_name} failed with exit code {result.returncode}"


class TestRenderDiffOutput:
    def test_plain_ascii(self):
        assert _render_diff_output(b"hello\n") == "hello$\n"

    def test_multiple_lines(self):
        assert _render_diff_output(b"a\nb\n") == "a$\nb$\n"

    def test_no_trailing_newline(self):
        assert _render_diff_output(b"hello") == "hello$"

    def test_tab_rendered_as_caret_i(self):
        assert _render_diff_output(b"a\tb\n") == "a^Ib$\n"

    def test_control_chars(self):
        assert _render_diff_output(b"\x01\x02\x03\n") == "^A^B^C$\n"

    def test_null_byte(self):
        assert _render_diff_output(b"\x00\n") == "^@$\n"

    def test_del_byte(self):
        assert _render_diff_output(b"\x7f\n") == "^?$\n"

    def test_invalid_utf8_bytes(self):
        assert _render_diff_output(b"\x80\xff\n") == "\\x80\\xFF$\n"

    def test_valid_utf8_printable(self):
        # é is U+00E9, encoded as 0xC3 0xA9
        assert _render_diff_output("é\n".encode("utf-8")) == "é$\n"

    def test_mixed_content(self):
        raw = b"ok\t\x01\x80end\n"
        assert _render_diff_output(raw) == "ok^I^A\\x80end$\n"

    def test_empty_input(self):
        assert _render_diff_output(b"") == ""

    def test_spaces_preserved(self):
        assert _render_diff_output(b"a b\n") == "a b$\n"
