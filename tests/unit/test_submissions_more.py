"""Tests for additional functions in submissions.py not covered elsewhere."""
import os
import pytest
from configparser import ConfigParser
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

import assignment_codeval.submissions as sub_mod
from assignment_codeval.submissions import (
    get_github_repo_url,
    github_safe_name,
    _parse_substitutions_file,
    _apply_substitutions,
    _is_within_tree,
    _safe_copy_into_tree,
    _download_assignment_submissions,
    download_submissions,
    list_codeval_assignments,
)
from assignment_codeval.canvas_utils import get_course, get_assignment


# ---------------------------------------------------------------------------
# _safe_copy_into_tree / _is_within_tree (symlink-escape protection)
# ---------------------------------------------------------------------------

class TestSafeCopyIntoTree:
    def test_copies_normal_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data")
        tree = tmp_path / "tree"
        tree.mkdir()
        dst = tree / "out.txt"
        assert _safe_copy_into_tree(str(src), str(dst), str(tree)) is True
        assert dst.read_text() == "data"

    def test_overwrites_symlink_in_tree_without_following(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("real")
        outside = tmp_path / "secret.txt"
        outside.write_text("secret")
        tree = tmp_path / "tree"
        tree.mkdir()
        dst = tree / "codeval.txt"
        os.symlink(str(outside), str(dst))  # student-planted symlink
        assert _safe_copy_into_tree(str(src), str(dst), str(tree)) is True
        # The symlink target must be untouched; dst is now a real file.
        assert outside.read_text() == "secret"
        assert not os.path.islink(str(dst))
        assert dst.read_text() == "real"

    def test_refuses_when_parent_resolves_outside_tree(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("real")
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        tree = tmp_path / "tree"
        tree.mkdir()
        # Student makes a directory inside the tree a symlink pointing out.
        escape = tree / "sub"
        os.symlink(str(outside_dir), str(escape))
        dst = escape / "codeval.txt"
        assert _safe_copy_into_tree(str(src), str(dst), str(tree)) is False
        assert not (outside_dir / "codeval.txt").exists()


@pytest.fixture(autouse=True)
def clear_caches():
    get_course.cache_clear()
    get_assignment.cache_clear()
    yield
    get_course.cache_clear()
    get_assignment.cache_clear()


# ---------------------------------------------------------------------------
# get_github_repo_url
# ---------------------------------------------------------------------------

class TestGetGithubRepoUrl:
    def _config(self, gh_key, prefix):
        p = ConfigParser()
        p['GITHUB'] = {gh_key: prefix}
        return p

    def _course(self, name):
        c = MagicMock()
        c.name = name
        return c

    def test_returns_none_when_github_not_configured(self):
        course = self._course("CS101")
        config = ConfigParser()
        assert get_github_repo_url(course, 1, config) is None

    def test_returns_none_when_user_has_no_links(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        user = MagicMock()
        user.get_profile.return_value = {}
        course.get_user.return_value = user
        assert get_github_repo_url(course, 1, config) is None

    def test_returns_none_when_no_github_link(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        user = MagicMock()
        user.get_profile.return_value = {
            "links": [{"title": "Twitter", "url": "https://twitter.com/user"}]
        }
        course.get_user.return_value = user
        assert get_github_repo_url(course, 1, config) is None

    def test_returns_repo_url_when_github_link_found(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        user = MagicMock()
        user.get_profile.return_value = {
            "links": [{"title": "GitHub", "url": "https://github.com/johndoe"}]
        }
        course.get_user.return_value = user
        result = get_github_repo_url(course, 1, config)
        assert result == "https://github.com/org/cs101-johndoe.git"

    def test_returns_none_on_exception(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        course.get_user.side_effect = Exception("network error")
        result = get_github_repo_url(course, 1, config)
        assert result is None

    def test_returns_none_when_multiple_github_links(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        user = MagicMock()
        user.get_profile.return_value = {
            "links": [
                {"title": "GitHub", "url": "https://github.com/user1"},
                {"title": "GitHub", "url": "https://github.com/user2"},
            ]
        }
        course.get_user.return_value = user
        assert get_github_repo_url(course, 1, config) is None

    def test_key_sanitizes_course_name(self):
        course = self._course("CS:101=A")
        config = ConfigParser()
        config['GITHUB'] = {"CS101A": "https://github.com/org/cs101"}
        user = MagicMock()
        user.get_profile.return_value = {
            "links": [{"title": "GitHub", "url": "https://github.com/alice"}]
        }
        course.get_user.return_value = user
        result = get_github_repo_url(course, 1, config)
        assert result == "https://github.com/org/cs101-alice.git"

    def test_from_name_builds_url_without_profile(self):
        course = self._course("CS101")
        config = self._config("CS101", "https://github.com/org/cs101")
        result = get_github_repo_url(course, 1, config, from_name="José García")
        assert result == "https://github.com/org/cs101-Jose-Garcia.git"
        course.get_user.assert_not_called()

    def test_from_name_still_requires_github_config(self):
        course = self._course("CS101")
        config = ConfigParser()
        assert get_github_repo_url(course, 1, config, from_name="Alice") is None


# ---------------------------------------------------------------------------
# github_safe_name
# ---------------------------------------------------------------------------

class TestGithubSafeName:
    def test_plain_name_spaces_become_dashes(self):
        assert github_safe_name("John Doe") == "John-Doe"

    def test_accents_are_stripped(self):
        assert github_safe_name("José García") == "Jose-Garcia"

    def test_runs_collapse_and_edges_trim(self):
        assert github_safe_name("  A  B  ") == "A-B"

    def test_allowed_punctuation_kept(self):
        assert github_safe_name("mary.jane_o-connor") == "mary.jane_o-connor"

    def test_empty_falls_back_to_x(self):
        assert github_safe_name("!!!") == "x"


# ---------------------------------------------------------------------------
# _parse_substitutions_file
# ---------------------------------------------------------------------------

class TestParseSubstitutionsFile:
    def test_parses_simple_substitution(self, tmp_path):
        f = tmp_path / "subs.txt"
        f.write_text("/hello/world/\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("hello", "world")]

    def test_parses_multiple_substitutions(self, tmp_path):
        f = tmp_path / "subs.txt"
        f.write_text("/foo/bar/\n/baz/qux/\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("foo", "bar"), ("baz", "qux")]

    def test_skips_empty_lines(self, tmp_path):
        f = tmp_path / "subs.txt"
        f.write_text("/a/b/\n\n/c/d/\n")
        result = _parse_substitutions_file(str(f))
        assert len(result) == 2

    def test_custom_delimiter(self, tmp_path):
        f = tmp_path / "subs.txt"
        f.write_text("|hello|world|\n")
        result = _parse_substitutions_file(str(f))
        assert result == [("hello", "world")]

    def test_raises_on_invalid_line(self, tmp_path):
        import click
        f = tmp_path / "subs.txt"
        f.write_text("/badline\n")
        with pytest.raises(click.ClickException):
            _parse_substitutions_file(str(f))

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "subs.txt"
        f.write_text("")
        result = _parse_substitutions_file(str(f))
        assert result == []


# ---------------------------------------------------------------------------
# _apply_substitutions
# ---------------------------------------------------------------------------

class TestApplySubstitutions:
    def test_applies_single_substitution(self):
        result = _apply_substitutions("hello world", [("hello", "hi")])
        assert result == "hi world"

    def test_applies_multiple_substitutions(self):
        result = _apply_substitutions("foo bar", [("foo", "a"), ("bar", "b")])
        assert result == "a b"

    def test_no_match_returns_unchanged(self):
        result = _apply_substitutions("unchanged", [("other", "x")])
        assert result == "unchanged"

    def test_empty_substitutions(self):
        result = _apply_substitutions("text", [])
        assert result == "text"


# ---------------------------------------------------------------------------
# download_submissions command — basic paths via CliRunner
# ---------------------------------------------------------------------------

class TestDownloadSubmissionsCommand:
    def test_requires_course_and_assignment_without_active(self):
        result = CliRunner().invoke(download_submissions, [])
        assert result.exit_code != 0

    def test_basic_download_with_mocked_canvas(self, tmp_path):
        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.name = "CS101"
        course.id = "42"
        assignment = MagicMock()
        assignment.name = "HW1"
        assignment.id = "10"
        submission = MagicMock()
        submission.attempt = 1
        submission.user_id = "99"
        submission.user = {"name": "Alice"}
        submission.submission_comments = []
        submission.submitted_at = "2024-01-01T12:00:00Z"
        submission.late = False
        submission.body = None
        del submission.attachments
        assignment.get_submissions.return_value = [submission]

        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.submissions.get_course", return_value=course):
                with patch("assignment_codeval.submissions.get_assignment",
                           return_value=assignment):
                    with patch("assignment_codeval.submissions.get_github_repo_url",
                               return_value=None):
                        result = CliRunner().invoke(
                            download_submissions,
                            ["CS101", "HW1", "--target-dir", str(tmp_path)]
                        )
        assert result.exit_code == 0
        meta = tmp_path / "CS101" / "HW1" / "99" / "metadata.txt"
        assert meta.exists()

    def test_repo_from_name_flag_uses_student_name(self, tmp_path):
        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.name = "CS101"
        course.id = "42"
        assignment = MagicMock()
        assignment.name = "HW1"
        assignment.id = "10"
        submission = MagicMock()
        submission.attempt = 1
        submission.user_id = "99"
        submission.user = {"name": "José García"}
        submission.submission_comments = []
        submission.submitted_at = "2024-01-01T12:00:00Z"
        submission.late = False
        submission.body = None
        del submission.attachments
        assignment.get_submissions.return_value = [submission]

        repo_lookup = MagicMock(return_value="https://github.com/org/cs101-Jose-Garcia.git")
        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.submissions.get_course", return_value=course):
                with patch("assignment_codeval.submissions.get_assignment",
                           return_value=assignment):
                    with patch("assignment_codeval.submissions.get_github_repo_url",
                               repo_lookup):
                        result = CliRunner().invoke(
                            download_submissions,
                            ["CS101", "HW1", "--target-dir", str(tmp_path),
                             "--repo-from-name"]
                        )
        assert result.exit_code == 0
        assert repo_lookup.call_args.kwargs["from_name"] == "José García"
        meta = tmp_path / "CS101" / "HW1" / "99" / "metadata.txt"
        assert "github_repo=https://github.com/org/cs101-Jose-Garcia.git" in meta.read_text()

    def test_attachment_cannot_overwrite_control_files(self, tmp_path):
        """A student attachment named SUBSTITUTIONS.txt must not be written (grade forgery)."""
        course = MagicMock()
        course.name = "CS101"
        assignment = MagicMock()
        assignment.name = "HW1"

        downloaded = []

        def make_attachment(name):
            att = MagicMock()
            att.filename = name
            att.download = MagicMock(side_effect=lambda p: downloaded.append(p))
            return att

        submission = MagicMock()
        submission.attempt = 1
        submission.user_id = "99"
        submission.user = {"name": "Mallory"}
        submission.submission_comments = []
        submission.submitted_at = "2024-01-01T12:00:00Z"
        submission.late = False
        submission.body = None
        submission.attachments = [
            make_attachment("SUBSTITUTIONS.txt"),   # reserved -> skipped
            make_attachment("../../escape.txt"),     # traversal -> collapsed
            make_attachment("homework.py"),          # normal -> kept
        ]
        assignment.get_submissions.return_value = [submission]

        parser = ConfigParser()
        with patch("assignment_codeval.submissions.click.get_app_dir",
                   return_value=str(tmp_path / "codeval.ini")):
            with patch("assignment_codeval.submissions.ConfigParser", return_value=parser):
                with patch("assignment_codeval.submissions.get_github_repo_url", return_value=None):
                    _download_assignment_submissions(
                        MagicMock(), course, assignment, str(tmp_path),
                        include_commented=True, codeval_prefix="codeval: ",
                        include_empty=False, uncommented_for=0, for_name=None)

        student_dir = tmp_path / "CS101" / "HW1" / "99"
        # The forgery file was never written; the real bookkeeping file is intact.
        assert not any(p.endswith("SUBSTITUTIONS.txt") for p in downloaded)
        # Traversal name collapsed to a basename inside the student dir.
        assert str(student_dir / "escape.txt") in downloaded
        assert str(student_dir / "homework.py") in downloaded

    def test_active_requires_codeval_config(self, tmp_path):
        canvas = MagicMock()
        user = MagicMock()
        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("click.get_app_dir", return_value=str(tmp_path / "missing.ini")):
                result = CliRunner().invoke(download_submissions, ["--active"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# list_codeval_assignments command
# ---------------------------------------------------------------------------

class TestListCodevalAssignmentsCommand:
    def test_requires_codeval_config(self, tmp_path):
        with patch("click.get_app_dir", return_value=str(tmp_path / "missing.ini")):
            result = CliRunner().invoke(list_codeval_assignments, [])
        assert result.exit_code != 0

    def test_lists_assignments_matching_codeval_files(self, tmp_path):
        codeval_dir = tmp_path / "codevals"
        codeval_dir.mkdir()
        (codeval_dir / "hw1.codeval").write_text("ASSIGNMENT START HW1\nT cmd\n")

        config_file = tmp_path / "codeval.ini"
        config_file.write_text(f"[CODEVAL]\ndirectory = {codeval_dir}\n[SERVER]\nurl = https://x.com\ntoken = t\n")

        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.name = "CS101"
        assignment = MagicMock()
        assignment.name = "hw1"
        course.get_assignments.return_value = [assignment]

        with patch("click.get_app_dir", return_value=str(config_file)):
            with patch("assignment_codeval.submissions.connect_to_canvas",
                       return_value=(canvas, user)):
                with patch("assignment_codeval.submissions.get_courses",
                           return_value=[course]):
                    result = CliRunner().invoke(list_codeval_assignments, [])
        assert result.exit_code == 0
