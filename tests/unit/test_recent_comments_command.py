"""Tests for the recent_comments CLI command (mocked Canvas/GraphQL)."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from assignment_codeval.recent_comments import recent_comments
from assignment_codeval.canvas_utils import get_course


def _iso(dt):
    return dt.isoformat()


def _course(name="CS101", course_id="42"):
    c = MagicMock()
    c.name = name
    c.id = course_id
    return c


def _graphql_data(assignments):
    return {"course": {"assignmentsConnection": {"nodes": assignments}}}


def _sub(student_name, submitted_at=None, comments=None):
    return {
        "submittedAt": submitted_at,
        "user": {"name": student_name},
        "commentsConnection": {"nodes": comments or []},
    }


def _comment(text, created_at):
    return {"comment": text, "createdAt": created_at}


@pytest.fixture(autouse=True)
def clear_cache():
    get_course.cache_clear()
    yield
    get_course.cache_clear()


class TestRecentCommentsCommand:
    def _invoke(self, args, course=None, courses=None, graphql_data=None,
                submissions=None):
        course = course or _course()
        graphql_data = graphql_data or _graphql_data([])
        submissions = submissions or []

        patches = [
            patch("assignment_codeval.recent_comments.connect_to_canvas",
                  return_value=(MagicMock(), MagicMock())),
            patch("assignment_codeval.recent_comments.get_course", return_value=course),
            patch("assignment_codeval.recent_comments.get_courses",
                  return_value=courses or [course]),
            patch("assignment_codeval.recent_comments.get_canvas_credentials",
                  return_value=("https://canvas.example.com", "tok")),
            patch("assignment_codeval.recent_comments.graphql_request",
                  return_value=graphql_data),
            patch("assignment_codeval.recent_comments.fetch_all_submissions",
                  return_value=submissions),
        ]
        for p in patches:
            p.start()
        try:
            return CliRunner().invoke(recent_comments, args)
        finally:
            for p in patches:
                p.stop()

    def test_requires_course_or_active(self):
        result = CliRunner().invoke(recent_comments, [])
        assert result.exit_code != 0

    def test_no_comments_shows_total_zero(self):
        now = datetime.now(timezone.utc)
        assignments = [{"_id": "1", "name": "HW1"}]
        result = self._invoke(["CS101"],
                              graphql_data=_graphql_data(assignments),
                              submissions=[_sub("Alice")])
        assert "Total: 0 comments" in result.output

    def test_shows_recent_comment(self):
        now = datetime.now(timezone.utc)
        comment_time = _iso(now - timedelta(minutes=30))
        assignments = [{"_id": "1", "name": "HW1"}]
        submissions = [_sub("Alice", _iso(now - timedelta(hours=1)),
                            [_comment("codeval: 10/10", comment_time)])]
        result = self._invoke(["CS101"],
                              graphql_data=_graphql_data(assignments),
                              submissions=submissions)
        assert "Total: 1 comments" in result.output
        assert "Alice" in result.output

    def test_old_comment_not_in_period(self):
        now = datetime.now(timezone.utc)
        old_comment = _iso(now - timedelta(hours=5))
        assignments = [{"_id": "1", "name": "HW1"}]
        submissions = [_sub("Alice", _iso(now - timedelta(hours=6)),
                            [_comment("codeval: 8/10", old_comment)])]
        result = self._invoke(["CS101", "--time-period", "1h"],
                              graphql_data=_graphql_data(assignments),
                              submissions=submissions)
        assert "Total: 0 comments" in result.output

    def test_active_flag_uses_get_courses(self):
        now = datetime.now(timezone.utc)
        course = _course()
        result = self._invoke(["--active"],
                              courses=[course],
                              graphql_data=_graphql_data([]),
                              submissions=[])
        assert result.exit_code == 0
        assert "Total: 0 comments" in result.output

    def test_active_no_courses_returns_early(self):
        with patch("assignment_codeval.recent_comments.connect_to_canvas",
                   return_value=(MagicMock(), MagicMock())):
            with patch("assignment_codeval.recent_comments.get_courses", return_value=[]):
                result = CliRunner().invoke(recent_comments, ["--active"])
        assert "No active courses" in result.output

    def test_verbose_shows_course_name(self):
        now = datetime.now(timezone.utc)
        assignments = [{"_id": "1", "name": "HW1"}]
        result = self._invoke(["CS101", "--verbose"],
                              graphql_data=_graphql_data(assignments),
                              submissions=[])
        assert result.exit_code == 0

    def test_show_uncommented_flag(self):
        now = datetime.now(timezone.utc)
        assignments = [{"_id": "1", "name": "HW1"}]
        submissions = [_sub("Bob", _iso(now - timedelta(hours=1)))]
        result = self._invoke(["CS101", "--show-uncommented"],
                              graphql_data=_graphql_data(assignments),
                              submissions=submissions)
        assert result.exit_code == 0

    def test_show_uncommented_with_codeval_comment_not_listed(self):
        now = datetime.now(timezone.utc)
        sub_time = _iso(now - timedelta(hours=2))
        comment_time = _iso(now - timedelta(hours=1))
        assignments = [{"_id": "1", "name": "HW1"}]
        submissions = [_sub("Carol", sub_time,
                            [_comment("codeval: 9/10", comment_time)])]
        result = self._invoke(["CS101", "--show-uncommented"],
                              graphql_data=_graphql_data(assignments),
                              submissions=submissions)
        assert result.exit_code == 0
