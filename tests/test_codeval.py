"""Pytest tests for CodEval test files."""
import glob
import os
import subprocess
import pytest

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
