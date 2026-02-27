"""Tests for check_codeval module."""

import pytest

from assignment_codeval.check_codeval import _has_codeval_comment_after_submission


def _make_submission(submitted_at, comments=None):
    """Build a submission node matching the GraphQL shape."""
    nodes = []
    for c in (comments or []):
        nodes.append({"comment": c[0], "createdAt": c[1]})
    return {
        "submittedAt": submitted_at,
        "commentsConnection": {"nodes": nodes},
    }


class TestHasCodevalCommentAfterSubmission:
    def test_no_submission(self):
        """submittedAt is None → treated as not needing evaluation."""
        sub = _make_submission(None)
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is True

    def test_no_comments(self):
        """submitted but no comments at all → missing."""
        sub = _make_submission("2025-01-15T10:00:00Z")
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is False

    def test_only_non_codeval_comments(self):
        """comments exist but none start with the codeval prefix → missing."""
        sub = _make_submission("2025-01-15T10:00:00Z", [
            ("great work!", "2025-01-16T12:00:00Z"),
            ("please resubmit", "2025-01-16T13:00:00Z"),
        ])
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is False

    def test_codeval_comment_older_than_submission(self):
        """codeval comment exists but is older than the submission → missing."""
        sub = _make_submission("2025-01-15T10:00:00Z", [
            ("codeval: passed 3/5 tests", "2025-01-14T08:00:00Z"),
        ])
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is False

    def test_codeval_comment_newer_than_submission(self):
        """codeval comment newer than submission → has evaluation."""
        sub = _make_submission("2025-01-15T10:00:00Z", [
            ("codeval: passed 5/5 tests", "2025-01-16T12:00:00Z"),
        ])
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is True

    def test_multiple_comments_one_matching(self):
        """multiple comments, only one is a codeval comment after submission."""
        sub = _make_submission("2025-01-15T10:00:00Z", [
            ("nice try", "2025-01-14T08:00:00Z"),
            ("codeval: failed 0/5 tests", "2025-01-14T09:00:00Z"),
            ("please fix", "2025-01-16T11:00:00Z"),
            ("codeval: passed 5/5 tests", "2025-01-16T12:00:00Z"),
        ])
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is True

    def test_custom_prefix(self):
        """works with a custom prefix."""
        sub = _make_submission("2025-01-15T10:00:00Z", [
            ("EVAL: passed", "2025-01-16T12:00:00Z"),
        ])
        assert _has_codeval_comment_after_submission(sub, "EVAL: ") is True
        assert _has_codeval_comment_after_submission(sub, "codeval: ") is False
