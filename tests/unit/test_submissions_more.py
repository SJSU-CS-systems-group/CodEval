"""Tests for additional functions in submissions.py not covered elsewhere."""
import os
import pytest
from configparser import ConfigParser
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

import assignment_codeval.submissions as sub_mod
from assignment_codeval.submissions import (
    get_github_repo_url,
    _parse_substitutions_file,
    _apply_substitutions,
    download_submissions,
    list_codeval_assignments,
)
from assignment_codeval.canvas_utils import get_course, get_assignment


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
