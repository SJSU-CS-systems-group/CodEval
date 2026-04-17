"""Unit tests for canvas_utils.py (mocked — no real Canvas connection)."""
import configparser
import sys
from configparser import ConfigParser
from unittest.mock import MagicMock, patch, call
import pytest
import requests

from assignment_codeval.canvas_utils import (
    _check_config,
    is_teacher,
    get_course,
    get_courses,
    get_assignment,
    get_canvas_credentials,
    graphql_request,
    fetch_all_submissions,
)


# ---------------------------------------------------------------------------
# _check_config
# ---------------------------------------------------------------------------

class TestCheckConfig:
    def _make_parser(self, sections):
        parser = ConfigParser()
        for section, keys in sections.items():
            parser[section] = keys
        parser.config_file = "fake.ini"
        return parser

    def test_passes_when_section_and_key_exist(self):
        parser = self._make_parser({"SERVER": {"url": "http://x", "token": "abc"}})
        _check_config(parser, "SERVER", "url")  # should not raise

    def test_exits_when_section_missing(self):
        parser = self._make_parser({})
        with pytest.raises(SystemExit):
            _check_config(parser, "SERVER", "url")

    def test_exits_when_key_missing(self):
        parser = self._make_parser({"SERVER": {}})
        with pytest.raises(SystemExit):
            _check_config(parser, "SERVER", "url")


# ---------------------------------------------------------------------------
# is_teacher
# ---------------------------------------------------------------------------

class TestIsTeacher:
    def _make_course(self, enrollments):
        course = MagicMock()
        course.enrollments = enrollments
        return course

    def test_teacher_enrollment(self):
        course = self._make_course([{"role": "TeacherEnrollment"}])
        assert is_teacher(course) is True

    def test_ta_enrollment(self):
        course = self._make_course([{"role": "TaEnrollment"}])
        assert is_teacher(course) is True

    def test_student_enrollment(self):
        course = self._make_course([{"role": "StudentEnrollment"}])
        assert is_teacher(course) is False

    def test_no_enrollments(self):
        course = self._make_course([])
        assert is_teacher(course) is False

    def test_missing_role_key_skipped(self):
        course = self._make_course([{"type": "TeacherEnrollment"}])
        assert is_teacher(course) is False

    def test_no_enrollments_attribute(self):
        course = MagicMock(spec=[])  # no attributes
        assert is_teacher(course) is False

    def test_multiple_enrollments_teacher_present(self):
        course = self._make_course([
            {"role": "StudentEnrollment"},
            {"role": "TeacherEnrollment"},
        ])
        assert is_teacher(course) is True


# ---------------------------------------------------------------------------
# get_courses
# ---------------------------------------------------------------------------

class TestGetCourses:
    def _make_canvas(self, courses):
        canvas = MagicMock()
        canvas.get_courses.return_value = courses
        return canvas

    def _make_course(self, name, enrollments, start=None, end=None):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        course = MagicMock()
        course.name = name
        course.enrollments = enrollments
        if start:
            course.start_at_date = start
        elif hasattr(course, "start_at_date"):
            del course.start_at_date
        if end:
            course.end_at_date = end
        elif hasattr(course, "end_at_date"):
            del course.end_at_date
        return course

    def test_returns_matching_teacher_course(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(days=30)
        future = now + datetime.timedelta(days=30)
        course = MagicMock()
        course.name = "CS101"
        course.enrollments = [{"role": "TeacherEnrollment"}]
        course.start_at_date = past
        course.end_at_date = future
        canvas = self._make_canvas([course])
        result = get_courses(canvas, "CS101")
        assert len(result) == 1
        assert result[0].name == "CS101"

    def test_excludes_student_courses(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(days=30)
        future = now + datetime.timedelta(days=30)
        course = MagicMock()
        course.name = "CS101"
        course.enrollments = [{"role": "StudentEnrollment"}]
        course.start_at_date = past
        course.end_at_date = future
        canvas = self._make_canvas([course])
        result = get_courses(canvas, "CS101")
        assert len(result) == 0

    def test_partial_name_match(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        past = now - datetime.timedelta(days=30)
        future = now + datetime.timedelta(days=30)
        course = MagicMock()
        course.name = "CS101 Introduction"
        course.enrollments = [{"role": "TeacherEnrollment"}]
        course.start_at_date = past
        course.end_at_date = future
        canvas = self._make_canvas([course])
        result = get_courses(canvas, "CS101")
        assert len(result) == 1

    def test_empty_canvas_returns_empty(self):
        canvas = self._make_canvas([])
        result = get_courses(canvas, "anything")
        assert result == []


# ---------------------------------------------------------------------------
# get_course (cached)
# ---------------------------------------------------------------------------

class TestGetCoursesIsFinished:
    def _make_course(self, name, days_past_end):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        course = MagicMock()
        course.name = name
        course.enrollments = [{"role": "TeacherEnrollment"}]
        course.start_at_date = now - datetime.timedelta(days=60)
        course.end_at_date = now - datetime.timedelta(days=days_past_end)
        return course

    def test_is_finished_true_excludes_ended_courses(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        course = MagicMock()
        course.name = "CS101"
        course.enrollments = [{"role": "TeacherEnrollment"}]
        course.start_at_date = now - datetime.timedelta(days=60)
        course.end_at_date = now - datetime.timedelta(days=5)
        canvas = MagicMock()
        canvas.get_courses.return_value = [course]
        result = get_courses(canvas, "CS101", is_active=False, is_finished=True)
        assert len(result) == 0


class TestGetCourse:
    def setup_method(self):
        get_course.cache_clear()

    def teardown_method(self):
        get_course.cache_clear()

    def _active_course(self, name):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        course = MagicMock()
        course.name = name
        course.enrollments = [{"role": "TeacherEnrollment"}]
        course.start_at_date = now - datetime.timedelta(days=30)
        course.end_at_date = now + datetime.timedelta(days=30)
        return course

    def test_returns_single_matching_course(self):
        canvas = MagicMock()
        course = self._active_course("CS101")
        canvas.get_courses.return_value = [course]
        result = get_course(canvas, "CS101")
        assert result.name == "CS101"

    def test_exits_when_no_match(self):
        canvas = MagicMock()
        canvas.get_courses.return_value = []
        with pytest.raises(SystemExit):
            get_course(canvas, "NonExistent")

    def test_exits_when_multiple_matches(self):
        canvas = MagicMock()
        c1 = self._active_course("CS101 Section A")
        c2 = self._active_course("CS101 Section B")
        canvas.get_courses.return_value = [c1, c2]
        with pytest.raises(SystemExit):
            get_course(canvas, "CS101")


# ---------------------------------------------------------------------------
# get_assignment (cached)
# ---------------------------------------------------------------------------

class TestGetAssignment:
    def setup_method(self):
        get_assignment.cache_clear()

    def teardown_method(self):
        get_assignment.cache_clear()

    def _make_assignment(self, name):
        a = MagicMock()
        a.name = name
        return a

    def test_returns_matching_assignment(self):
        course = MagicMock()
        course.get_assignments.return_value = [self._make_assignment("Homework 1")]
        result = get_assignment(course, "Homework 1")
        assert result.name == "Homework 1"

    def test_exits_when_no_match(self):
        course = MagicMock()
        course.get_assignments.return_value = []
        with pytest.raises(SystemExit):
            get_assignment(course, "Missing HW")

    def test_exits_when_multiple_ambiguous_matches(self):
        course = MagicMock()
        assignments = [
            self._make_assignment("Homework 1 Part A"),
            self._make_assignment("Homework 1 Part B"),
        ]
        course.get_assignments.return_value = assignments
        with pytest.raises(SystemExit):
            get_assignment(course, "Homework 1")

    def test_strict_match_single_assignment(self):
        course = MagicMock()
        assignments = [self._make_assignment("HW1")]
        course.get_assignments.return_value = assignments
        result = get_assignment(course, "HW1")
        assert result.name == "HW1"


# ---------------------------------------------------------------------------
# get_canvas_credentials
# ---------------------------------------------------------------------------

class TestGetCanvasCredentials:
    def test_reads_url_and_token(self, tmp_path, monkeypatch):
        config_file = tmp_path / "codeval.ini"
        config_file.write_text("[SERVER]\nurl = https://canvas.example.com\ntoken = mytoken\n")
        monkeypatch.setattr("click.get_app_dir", lambda name: str(config_file))
        url, token = get_canvas_credentials()
        assert url == "https://canvas.example.com"
        assert token == "mytoken"

    def test_exits_when_no_server_section(self, tmp_path, monkeypatch):
        config_file = tmp_path / "codeval.ini"
        config_file.write_text("[OTHER]\nkey = value\n")
        monkeypatch.setattr("click.get_app_dir", lambda name: str(config_file))
        with pytest.raises(SystemExit):
            get_canvas_credentials()

    def test_exits_when_token_missing(self, tmp_path, monkeypatch):
        config_file = tmp_path / "codeval.ini"
        config_file.write_text("[SERVER]\nurl = https://canvas.example.com\n")
        monkeypatch.setattr("click.get_app_dir", lambda name: str(config_file))
        with pytest.raises(SystemExit):
            get_canvas_credentials()

    def test_exits_when_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("click.get_app_dir", lambda name: str(tmp_path / "missing.ini"))
        with pytest.raises((SystemExit, KeyError)):
            get_canvas_credentials()


# ---------------------------------------------------------------------------
# graphql_request
# ---------------------------------------------------------------------------

class TestGraphqlRequest:
    def test_returns_data_on_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {"key": "value"}}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = graphql_request("https://canvas.example.com", "token123", "query {}", {})
        assert result == {"key": "value"}
        mock_post.assert_called_once()

    def test_includes_bearer_token_in_headers(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {}}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            graphql_request("https://canvas.example.com", "mytoken", "query {}", {})
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer mytoken"

    def test_posts_to_graphql_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": {}}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            graphql_request("https://canvas.example.com", "tok", "q", {})
        args, _ = mock_post.call_args
        assert args[0] == "https://canvas.example.com/api/graphql"

    def test_exits_on_graphql_errors(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"errors": [{"message": "bad query"}], "data": None}
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(SystemExit):
                graphql_request("https://canvas.example.com", "tok", "bad query", {})

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(requests.HTTPError):
                graphql_request("https://canvas.example.com", "tok", "q", {})


# ---------------------------------------------------------------------------
# fetch_all_submissions
# ---------------------------------------------------------------------------

class TestFetchAllSubmissions:
    def _page(self, nodes, has_next=False, cursor=None):
        return {
            "assignment": {
                "submissionsConnection": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                    "nodes": nodes,
                }
            }
        }

    def test_single_page(self):
        nodes = [{"_id": "1"}, {"_id": "2"}]
        with patch(
            "assignment_codeval.canvas_utils.graphql_request",
            return_value=self._page(nodes),
        ):
            result = fetch_all_submissions("https://x.com", "tok", "42")
        assert result == nodes

    def test_multiple_pages_concatenated(self):
        page1 = self._page([{"_id": "1"}], has_next=True, cursor="c1")
        page2 = self._page([{"_id": "2"}], has_next=False)
        with patch(
            "assignment_codeval.canvas_utils.graphql_request",
            side_effect=[page1, page2],
        ):
            result = fetch_all_submissions("https://x.com", "tok", "99")
        assert len(result) == 2
        assert result[0]["_id"] == "1"
        assert result[1]["_id"] == "2"

    def test_empty_result(self):
        with patch(
            "assignment_codeval.canvas_utils.graphql_request",
            return_value=self._page([]),
        ):
            result = fetch_all_submissions("https://x.com", "tok", "0")
        assert result == []
