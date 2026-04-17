"""Unit tests for pure helper functions in check_grading.py."""
from datetime import datetime, timedelta, timezone
import pytest

from assignment_codeval.check_grading import (
    _format_elapsed,
    _has_codeval_comment_after_submission,
)


# ---------------------------------------------------------------------------
# _format_elapsed
# ---------------------------------------------------------------------------

class TestFormatElapsed:
    def _iso(self, delta_ago: timedelta) -> str:
        return (datetime.now(timezone.utc) - delta_ago).isoformat()

    def test_minutes_only(self):
        result = _format_elapsed(self._iso(timedelta(minutes=45)))
        assert result == "45m"

    def test_exactly_one_hour(self):
        result = _format_elapsed(self._iso(timedelta(hours=1)))
        assert "1h" in result

    def test_hours_and_minutes(self):
        result = _format_elapsed(self._iso(timedelta(hours=2, minutes=30)))
        assert "2h" in result
        assert "30m" in result

    def test_hours_only_no_trailing_zero_minutes(self):
        result = _format_elapsed(self._iso(timedelta(hours=3)))
        assert result == "3h"
        assert "m" not in result

    def test_days_only(self):
        result = _format_elapsed(self._iso(timedelta(days=2)))
        assert result == "2d"

    def test_days_and_hours(self):
        result = _format_elapsed(self._iso(timedelta(days=1, hours=5)))
        assert "1d" in result
        assert "5h" in result

    def test_less_than_one_minute(self):
        result = _format_elapsed(self._iso(timedelta(seconds=30)))
        assert result == "0m"

    def test_returns_string(self):
        assert isinstance(_format_elapsed(self._iso(timedelta(minutes=10))), str)


# ---------------------------------------------------------------------------
# _has_codeval_comment_after_submission
# ---------------------------------------------------------------------------

class TestHasCodevalCommentAfterSubmission:
    def _make_node(self, submitted_at=None, comments=None):
        return {
            "submittedAt": submitted_at,
            "commentsConnection": {"nodes": comments or []},
        }

    def _iso(self, dt: datetime) -> str:
        return dt.isoformat()

    def test_no_submitted_at_returns_true(self):
        node = self._make_node(submitted_at=None)
        assert _has_codeval_comment_after_submission(node, "codeval: ") is True

    def test_no_comments_returns_false(self):
        submitted = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        node = self._make_node(submitted_at=self._iso(submitted), comments=[])
        assert _has_codeval_comment_after_submission(node, "codeval: ") is False

    def test_codeval_comment_after_submission_returns_true(self):
        submitted = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        comment_time = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        node = self._make_node(
            submitted_at=self._iso(submitted),
            comments=[{
                "comment": "codeval: score 10/10",
                "createdAt": self._iso(comment_time),
            }],
        )
        assert _has_codeval_comment_after_submission(node, "codeval: ") is True

    def test_codeval_comment_before_submission_returns_false(self):
        submitted = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        comment_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        node = self._make_node(
            submitted_at=self._iso(submitted),
            comments=[{
                "comment": "codeval: old comment",
                "createdAt": self._iso(comment_time),
            }],
        )
        assert _has_codeval_comment_after_submission(node, "codeval: ") is False

    def test_non_codeval_comment_ignored(self):
        submitted = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        comment_time = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        node = self._make_node(
            submitted_at=self._iso(submitted),
            comments=[{
                "comment": "instructor: looks good",
                "createdAt": self._iso(comment_time),
            }],
        )
        assert _has_codeval_comment_after_submission(node, "codeval: ") is False

    def test_custom_prefix(self):
        submitted = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        comment_time = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        node = self._make_node(
            submitted_at=self._iso(submitted),
            comments=[{
                "comment": "auto: result: pass",
                "createdAt": self._iso(comment_time),
            }],
        )
        assert _has_codeval_comment_after_submission(node, "auto:") is True
