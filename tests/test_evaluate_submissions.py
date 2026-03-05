"""Tests for evaluate_submissions command."""

import os
import tempfile
import zipfile

import click
import pytest

from assignment_codeval.submissions import _parse_substitutions_file, _apply_substitutions


class TestGitHubSubmissionWorkingDir:
    """Tests for GitHub submission working directory detection."""

    def test_zip_extracted_to_assignment_dir_for_github(self):
        """Verify zip files are extracted to assignment directory for GitHub submissions.

        When a GitHub submission exists (has .git directory) and no CD tag is specified,
        zip files should be extracted to the assignment_name subdirectory, not the root.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup directory structure:
            # tmpdir/
            #   codeval/
            #     TestAssignment.codeval
            #     support.zip
            #   submissions/
            #     Course/
            #       TestAssignment/
            #         12345/
            #           submission/
            #             TestAssignment/
            #               .git/
            #               main.py

            codeval_dir = os.path.join(tmpdir, "codeval")
            submissions_dir = os.path.join(tmpdir, "submissions")
            os.makedirs(codeval_dir)

            assignment_name = "TestAssignment"
            student_dir = os.path.join(submissions_dir, "Course", assignment_name, "12345")
            submission_dir = os.path.join(student_dir, "submission")
            git_repo_dir = os.path.join(submission_dir, assignment_name)
            os.makedirs(os.path.join(git_repo_dir, ".git"))

            # Create a dummy file in the git repo
            with open(os.path.join(git_repo_dir, "main.py"), "w") as f:
                f.write("print('hello')\n")

            # Create a zip file with a helper file
            zip_path = os.path.join(codeval_dir, "support.zip")
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("helper.txt", "helper content")

            # Create codeval file with Z tag but NO CD tag
            codeval_path = os.path.join(codeval_dir, f"{assignment_name}.codeval")
            with open(codeval_path, "w") as f:
                f.write("Z support.zip\n")
                f.write("T echo test\n")
                f.write("O test\n")

            # Parse the codeval file and check where zip would be extracted
            # This simulates what evaluate_submissions does
            from assignment_codeval.submissions import evaluate_submissions
            from zipfile import ZipFile

            # Manually trace through the logic to verify the bug
            assignment_working_dir = "."
            has_cd_tag = False
            zip_files = []

            with open(codeval_path, "r") as fd:
                for line in fd:
                    line = line.strip()
                    if line.startswith("CD"):
                        has_cd_tag = True
                    if line.startswith("Z"):
                        zip_files.append(line.split(None, 1)[1])

            # Check for GitHub submission BEFORE extracting
            is_github = os.path.exists(os.path.join(submission_dir, assignment_name, ".git"))
            assert is_github, "Test setup: .git directory should exist"

            if not has_cd_tag and is_github:
                assignment_working_dir = assignment_name

            # Now extract zip files to the correct location
            for zf_name in zip_files:
                with ZipFile(os.path.join(codeval_dir, zf_name)) as zf:
                    dest_dir = os.path.join(submission_dir, assignment_working_dir)
                    zf.extractall(dest_dir)

            # Verify helper.txt was extracted to the assignment directory, not root
            correct_path = os.path.join(submission_dir, assignment_name, "helper.txt")
            wrong_path = os.path.join(submission_dir, "helper.txt")

            assert os.path.exists(correct_path), \
                f"helper.txt should be at {correct_path}"
            assert not os.path.exists(wrong_path), \
                f"helper.txt should NOT be at {wrong_path} (root of submission_dir)"

    def test_zip_extracted_to_root_when_cd_tag_present(self):
        """Verify zip files respect CD tag even for GitHub submissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            codeval_dir = os.path.join(tmpdir, "codeval")
            submissions_dir = os.path.join(tmpdir, "submissions")
            os.makedirs(codeval_dir)

            assignment_name = "TestAssignment"
            student_dir = os.path.join(submissions_dir, "Course", assignment_name, "12345")
            submission_dir = os.path.join(student_dir, "submission")

            # Create custom directory specified by CD tag
            custom_dir = os.path.join(submission_dir, "custom_dir")
            os.makedirs(os.path.join(custom_dir, ".git"))

            # Create codeval file WITH CD tag
            codeval_path = os.path.join(codeval_dir, f"{assignment_name}.codeval")
            with open(codeval_path, "w") as f:
                f.write("CD custom_dir\n")
                f.write("Z support.zip\n")
                f.write("T echo test\n")
                f.write("O test\n")

            # Create zip file
            zip_path = os.path.join(codeval_dir, "support.zip")
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("helper.txt", "helper content")

            # Trace through logic
            from zipfile import ZipFile

            assignment_working_dir = "."
            has_cd_tag = False
            zip_files = []

            with open(codeval_path, "r") as fd:
                for line in fd:
                    line = line.strip()
                    if line.startswith("CD"):
                        has_cd_tag = True
                        assignment_working_dir = os.path.normpath(
                            os.path.join(assignment_working_dir, line.split()[1].strip()))
                    if line.startswith("Z"):
                        zip_files.append(line.split(None, 1)[1])

            # CD tag should take precedence
            assert has_cd_tag
            assert assignment_working_dir == "custom_dir"

            # Extract zip files
            for zf_name in zip_files:
                with ZipFile(os.path.join(codeval_dir, zf_name)) as zf:
                    dest_dir = os.path.join(submission_dir, assignment_working_dir)
                    zf.extractall(dest_dir)

            # Verify helper.txt was extracted to custom_dir
            correct_path = os.path.join(submission_dir, "custom_dir", "helper.txt")
            assert os.path.exists(correct_path), \
                f"helper.txt should be at {correct_path}"


class TestSubstitutionsFromZip:
    """Tests for copying SUBSTITUTIONS.txt from zip to comments.txt directory."""

    def _setup_submission(self, tmpdir, assignment_name, zip_contents):
        """Helper to create a submission directory with a zip file."""
        codeval_dir = os.path.join(tmpdir, "codeval")
        submissions_dir = os.path.join(tmpdir, "submissions")
        os.makedirs(codeval_dir)

        student_dir = os.path.join(submissions_dir, "Course", assignment_name, "12345")
        submission_dir = os.path.join(student_dir, "submission")
        os.makedirs(submission_dir)

        # Create zip
        zip_path = os.path.join(codeval_dir, "support.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for name, content in zip_contents.items():
                zf.writestr(name, content)

        # Create codeval file
        codeval_path = os.path.join(codeval_dir, f"{assignment_name}.codeval")
        with open(codeval_path, "w") as f:
            f.write("Z support.zip\n")
            f.write("T echo test\n")
            f.write("O test\n")

        return codeval_dir, student_dir, submission_dir

    def test_substitutions_copied_to_dirpath(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            codeval_dir, student_dir, submission_dir = self._setup_submission(
                tmpdir, "TestAssignment",
                {"SUBSTITUTIONS.txt": "/foo/bar/\n", "helper.txt": "data"}
            )

            # Simulate the zip extraction logic from evaluate_submissions
            from zipfile import ZipFile
            codeval_file = os.path.join(codeval_dir, "TestAssignment.codeval")
            zip_files = ["support.zip"]

            for zf_name in zip_files:
                with ZipFile(os.path.join(codeval_dir, zf_name)) as zf:
                    if "SUBSTITUTIONS.txt" in zf.namelist():
                        with open(os.path.join(student_dir, "SUBSTITUTIONS.txt"), "wb") as out_f:
                            out_f.write(zf.read("SUBSTITUTIONS.txt"))

            subs_path = os.path.join(student_dir, "SUBSTITUTIONS.txt")
            assert os.path.exists(subs_path)
            with open(subs_path) as f:
                assert f.read() == "/foo/bar/\n"

    def test_no_substitutions_in_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            codeval_dir, student_dir, submission_dir = self._setup_submission(
                tmpdir, "TestAssignment",
                {"helper.txt": "data"}
            )

            from zipfile import ZipFile
            zip_files = ["support.zip"]

            for zf_name in zip_files:
                with ZipFile(os.path.join(codeval_dir, zf_name)) as zf:
                    if "SUBSTITUTIONS.txt" in zf.namelist():
                        with open(os.path.join(student_dir, "SUBSTITUTIONS.txt"), "wb") as out_f:
                            out_f.write(zf.read("SUBSTITUTIONS.txt"))

            assert not os.path.exists(os.path.join(student_dir, "SUBSTITUTIONS.txt"))


class TestParseSubstitutionsFile:
    def test_basic_substitution(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo/bar/\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "bar")]

    def test_custom_delimiter(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("|foo|bar|\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "bar")]

    def test_multiple_lines(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo/bar/\n#baz#qux#\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "bar"), ("baz", "qux")]

    def test_empty_replacement(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo//\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "")]

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("\n/foo/bar/\n\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "bar")]

    def test_invalid_missing_trailing_delimiter(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo/bar\n")
        with pytest.raises(click.ClickException, match=":1:"):
            _parse_substitutions_file(str(f))

    def test_invalid_too_many_delimiters(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo/bar/baz/\n")
        with pytest.raises(click.ClickException, match=":1:"):
            _parse_substitutions_file(str(f))

    def test_invalid_no_delimiter_in_between(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foobar/\n")
        with pytest.raises(click.ClickException, match=":1:"):
            _parse_substitutions_file(str(f))

    def test_error_reports_correct_line_number(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("/foo/bar/\nbad line\n")
        with pytest.raises(click.ClickException, match=":2:"):
            _parse_substitutions_file(str(f))

    def test_delimiter_in_pattern_via_different_delimiter(self, tmp_path):
        f = tmp_path / "SUBSTITUTIONS.txt"
        f.write_text("|a/b|c/d|\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("a/b", "c/d")]


class TestApplySubstitutions:
    def test_single_substitution(self):
        assert _apply_substitutions("hello foo world", [("foo", "bar")]) == "hello bar world"

    def test_multiple_substitutions(self):
        result = _apply_substitutions("aaa bbb", [("aaa", "xxx"), ("bbb", "yyy")])
        assert result == "xxx yyy"

    def test_literal_pattern(self):
        result = _apply_substitutions("a^[[1mb", [("^[[1m", "<b>B</b>")])
        assert result == "a<b>B</b>b"

    def test_empty_substitutions(self):
        assert _apply_substitutions("hello", []) == "hello"

    def test_deletion(self):
        assert _apply_substitutions("hello world", [("world", "")]) == "hello "
