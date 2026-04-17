"""Tests for the check_grading CLI command (mocked Canvas/GraphQL)."""
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from assignment_codeval.check_grading import check_grading
from assignment_codeval.canvas_utils import get_course


def _iso(dt):
    return dt.isoformat()


def _course(name="CS101", course_id="42"):
    c = MagicMock()
    c.name = name
    c.id = course_id
    return c


def _graphql_data(groups):
    return {"course": {"assignmentGroupsConnection": {"nodes": groups}}}


def _assignment_node(name, aid):
    return {"_id": aid, "name": name}


def _sub(student_name, submitted_at, comments=None):
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


class TestCheckGradingCommand:
    def _invoke(self, args, canvas, user, course, graphql_data, submissions):
        with patch("assignment_codeval.check_grading.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.check_grading.get_course",
                       return_value=course):
                with patch("assignment_codeval.check_grading.get_canvas_credentials",
                           return_value=("https://canvas.example.com", "tok")):
                    with patch("assignment_codeval.check_grading.graphql_request",
                               return_value=graphql_data):
                        with patch("assignment_codeval.check_grading.fetch_all_submissions",
                                   return_value=submissions):
                            return CliRunner().invoke(check_grading, args)

    def test_exits_2_when_missing_grading(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)
        submissions = [_sub("Alice", _iso(old))]
        groups = [{"name": "Assignments", "assignmentsConnection": {
            "nodes": [_assignment_node("HW1", "1")]}}]
        result = self._invoke(["CS101"], canvas, user, course,
                              _graphql_data(groups), submissions)
        assert result.exit_code == 2

    def test_exit_0_when_all_graded(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        now = datetime.now(timezone.utc)
        old_sub = _iso(now - timedelta(hours=2))
        comment_time = _iso(now - timedelta(hours=1))
        submissions = [_sub("Alice", old_sub, [_comment("codeval: grade", comment_time)])]
        groups = [{"name": "Assignments", "assignmentsConnection": {
            "nodes": [_assignment_node("HW1", "1")]}}]
        result = self._invoke(["CS101"], canvas, user, course,
                              _graphql_data(groups), submissions)
        assert result.exit_code == 0

    def test_assignment_group_not_found_exits(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        groups = [{"name": "Other", "assignmentsConnection": {"nodes": []}}]
        result = self._invoke(["CS101", "--assignment-group", "Missing"],
                              canvas, user, course, _graphql_data(groups), [])
        assert result.exit_code != 0

    def test_no_assignments_in_group(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        groups = [{"name": "Assignments", "assignmentsConnection": {"nodes": []}}]
        result = self._invoke(["CS101"], canvas, user, course,
                              _graphql_data(groups), [])
        assert result.exit_code == 0
        assert "no assignments" in result.output

    def test_verbose_shows_checked_submissions(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        now = datetime.now(timezone.utc)
        old_sub = _iso(now - timedelta(hours=2))
        comment_time = _iso(now - timedelta(hours=1))
        submissions = [_sub("Alice", old_sub, [_comment("codeval: grade", comment_time)])]
        groups = [{"name": "Assignments", "assignmentsConnection": {
            "nodes": [_assignment_node("HW1", "1")]}}]
        result = self._invoke(["CS101", "--verbose"], canvas, user, course,
                              _graphql_data(groups), submissions)
        assert "Alice" in result.output

    def test_recent_submission_warns_not_errors(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        now = datetime.now(timezone.utc)
        recent_sub = _iso(now - timedelta(minutes=5))
        submissions = [_sub("Bob", recent_sub)]
        groups = [{"name": "Assignments", "assignmentsConnection": {
            "nodes": [_assignment_node("HW1", "1")]}}]
        result = self._invoke(["CS101", "--warn"], canvas, user, course,
                              _graphql_data(groups), submissions)
        assert "Bob" in result.output

    def test_skips_unsubmitted(self):
        canvas, user = MagicMock(), MagicMock()
        course = _course()
        submissions = [{"submittedAt": None, "user": {"name": "Anon"},
                        "commentsConnection": {"nodes": []}}]
        groups = [{"name": "Assignments", "assignmentsConnection": {
            "nodes": [_assignment_node("HW1", "1")]}}]
        result = self._invoke(["CS101"], canvas, user, course,
                              _graphql_data(groups), submissions)
        assert result.exit_code == 0
