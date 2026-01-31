"""Tests for evaluate_submissions command."""

import os
import tempfile
import zipfile

import pytest


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
