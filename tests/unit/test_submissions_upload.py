"""Tests for upload-related functions in submissions.py."""
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
import pytest
from click.testing import CliRunner

from assignment_codeval.submissions import (
    delete_submission_comment,
    upload_file_for_comment,
    upload_submission_comments,
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
# delete_submission_comment
# ---------------------------------------------------------------------------

class TestDeleteSubmissionComment:
    def test_sends_delete_request(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        with patch("assignment_codeval.submissions._get_canvas_config",
                   return_value=("https://canvas.example.com", "tok")):
            with patch("requests.delete", return_value=resp) as mock_del:
                delete_submission_comment(MagicMock(), "course1", "assign1", "user1", "comment1")
        mock_del.assert_called_once()
        url = mock_del.call_args[0][0]
        assert "comment1" in url
        assert "user1" in url

    def test_raises_on_http_error(self):
        import requests
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("403")
        with patch("assignment_codeval.submissions._get_canvas_config",
                   return_value=("https://canvas.example.com", "tok")):
            with patch("requests.delete", return_value=resp):
                with pytest.raises(Exception):
                    delete_submission_comment(MagicMock(), "c", "a", "u", "x")


# ---------------------------------------------------------------------------
# upload_file_for_comment
# ---------------------------------------------------------------------------

class TestUploadFileForComment:
    def _mock_upload_sequence(self, tmp_path, redirect=False):
        f = tmp_path / "results.html"
        f.write_text("<html>test</html>")

        r1 = MagicMock()
        r1.raise_for_status.return_value = None
        r1.json.return_value = {
            "upload_url": "https://storage.example.com/upload",
            "upload_params": {"key": "value"},
        }

        r2 = MagicMock()
        if redirect:
            r2.status_code = 301
            r2.headers = {"Location": "https://storage.example.com/confirm"}
            r3 = MagicMock()
            r3.raise_for_status.return_value = None
            r3.json.return_value = {"id": 99}
        else:
            r2.status_code = 200
            r2.json.return_value = {"id": 42}

        with patch("assignment_codeval.submissions._get_canvas_config",
                   return_value=("https://canvas.example.com", "tok")):
            with patch("requests.post", side_effect=[r1, r2]):
                if redirect:
                    with patch("requests.get", return_value=r3):
                        file_id = upload_file_for_comment(
                            MagicMock(), "course1", "assign1", "user1", str(f)
                        )
                else:
                    file_id = upload_file_for_comment(
                        MagicMock(), "course1", "assign1", "user1", str(f)
                    )
        return file_id

    def test_returns_file_id_direct(self, tmp_path):
        file_id = self._mock_upload_sequence(tmp_path, redirect=False)
        assert file_id == 42

    def test_follows_redirect_and_confirms(self, tmp_path):
        file_id = self._mock_upload_sequence(tmp_path, redirect=True)
        assert file_id == 99


# ---------------------------------------------------------------------------
# upload_submission_comments command
# ---------------------------------------------------------------------------

class TestUploadSubmissionComments:
    def _make_submission_dir(self, tmp_path, course="CS101", assignment="HW1",
                             student_id="42", already_sent=False):
        sub_dir = tmp_path / course / assignment / student_id
        sub_dir.mkdir(parents=True)
        (sub_dir / "comments.txt").write_text("codeval: 10/10\nPassed\n")
        (sub_dir / "metadata.txt").write_text(
            f"id={student_id}\nname=Alice\nassignment={assignment}\nattempt=1\n"
            f"late=False\ndate=2024-01-01T12:00:00Z\nlast_comment=\ngithub_repo=\n"
        )
        if already_sent:
            (sub_dir / "comments.txt.sent").write_text("2024-01-01T12:00:00Z")
        return str(tmp_path)

    def test_skips_already_sent(self, tmp_path):
        base = self._make_submission_dir(tmp_path, already_sent=True)
        canvas = MagicMock()
        user = MagicMock()
        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            result = CliRunner().invoke(upload_submission_comments, [base])
        assert result.exit_code == 0

    def test_uploads_comments_txt(self, tmp_path):
        base = self._make_submission_dir(tmp_path)
        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.id = "1"
        assignment = MagicMock()
        assignment.id = "2"
        submission = MagicMock()
        submission.submission_comments = []

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.submissions.get_course", return_value=course):
                with patch("assignment_codeval.submissions.get_assignment",
                           return_value=assignment):
                    with patch("assignment_codeval.submissions.get_submissions_by_id",
                               return_value={"42": submission}):
                        with patch("assignment_codeval.submissions.write_html_file"):
                            with patch("assignment_codeval.submissions.upload_file_for_comment",
                                       return_value=99):
                                with patch("assignment_codeval.submissions._get_canvas_config",
                                           return_value=("https://canvas.example.com", "tok")):
                                    with patch("requests.put", return_value=mock_resp):
                                        result = CliRunner().invoke(
                                            upload_submission_comments, [base]
                                        )

        assert result.exit_code == 0
        sent_file = (
            tmp_path / "CS101" / "HW1" / "42" / "comments.txt.sent"
        )
        assert sent_file.exists()

    def test_applies_substitutions_file(self, tmp_path):
        base = self._make_submission_dir(tmp_path)
        subs_file = tmp_path / "CS101" / "HW1" / "42" / "SUBSTITUTIONS.txt"
        subs_file.write_text("|Passed|Great job|\n")
        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.id = "1"
        assignment = MagicMock()
        assignment.id = "2"
        submission = MagicMock()
        submission.submission_comments = []

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.submissions.get_course", return_value=course):
                with patch("assignment_codeval.submissions.get_assignment",
                           return_value=assignment):
                    with patch("assignment_codeval.submissions.get_submissions_by_id",
                               return_value={"42": submission}):
                        with patch("assignment_codeval.submissions.write_html_file"):
                            with patch("assignment_codeval.submissions.upload_file_for_comment",
                                       return_value=99):
                                with patch("assignment_codeval.submissions._get_canvas_config",
                                           return_value=("https://canvas.example.com", "tok")):
                                    with patch("requests.put", return_value=mock_resp):
                                        result = CliRunner().invoke(
                                            upload_submission_comments, [base]
                                        )
        assert result.exit_code == 0

    def test_warns_when_no_submission_found(self, tmp_path):
        base = self._make_submission_dir(tmp_path)
        canvas = MagicMock()
        user = MagicMock()
        course = MagicMock()
        course.id = "1"
        assignment = MagicMock()
        assignment.id = "2"

        with patch("assignment_codeval.submissions.connect_to_canvas",
                   return_value=(canvas, user)):
            with patch("assignment_codeval.submissions.get_course", return_value=course):
                with patch("assignment_codeval.submissions.get_assignment",
                           return_value=assignment):
                    with patch("assignment_codeval.submissions.get_submissions_by_id",
                               return_value={}):
                        with patch("assignment_codeval.submissions.write_html_file"):
                            result = CliRunner().invoke(
                                upload_submission_comments, [base]
                            )
        assert result.exit_code == 0
