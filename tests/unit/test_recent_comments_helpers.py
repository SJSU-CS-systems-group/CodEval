"""Unit tests for pure helper functions in recent_comments.py."""
from datetime import datetime, timedelta, timezone
import pytest
import click

from assignment_codeval.recent_comments import (
    format_comment_preview,
    format_local_time,
    parse_time_period,
)


# ---------------------------------------------------------------------------
# format_comment_preview
# ---------------------------------------------------------------------------

class TestFormatCommentPreview:
    def test_short_comment_returned_as_is(self):
        result = format_comment_preview("codeval: line1\nline2\n", "codeval: ")
        assert "line1" in result
        assert "line2" in result

    def test_prefix_stripped(self):
        result = format_comment_preview("codeval: score: 10/10", "codeval: ")
        assert "codeval: " not in result
        assert "score" in result

    def test_no_prefix_left_intact(self):
        result = format_comment_preview("no prefix here", "codeval: ")
        assert "no prefix here" in result

    def test_long_comment_truncated_with_ellipsis(self):
        lines = [f"line{i}" for i in range(10)]
        comment = "codeval: " + "\n".join(lines)
        result = format_comment_preview(comment, "codeval: ")
        assert "..." in result

    def test_long_comment_shows_first_three_lines(self):
        lines = [f"line{i}" for i in range(10)]
        comment = "codeval: " + "\n".join(lines)
        result = format_comment_preview(comment, "codeval: ")
        assert "line0" in result
        assert "line1" in result
        assert "line2" in result

    def test_long_comment_shows_last_three_lines(self):
        lines = [f"line{i}" for i in range(10)]
        comment = "codeval: " + "\n".join(lines)
        result = format_comment_preview(comment, "codeval: ")
        assert "line7" in result
        assert "line8" in result
        assert "line9" in result

    def test_exactly_six_lines_no_truncation(self):
        lines = [f"line{i}" for i in range(6)]
        comment = "\n".join(lines)
        result = format_comment_preview(comment, "")
        assert "..." not in result

    def test_seven_lines_triggers_truncation(self):
        lines = [f"line{i}" for i in range(7)]
        comment = "\n".join(lines)
        result = format_comment_preview(comment, "")
        assert "..." in result

    def test_indentation_added(self):
        result = format_comment_preview("hello", "")
        assert result.startswith("    ")

    def test_empty_comment(self):
        # empty string → [""] → one blank line with indentation
        result = format_comment_preview("", "")
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# format_local_time
# ---------------------------------------------------------------------------

class TestFormatLocalTime:
    def test_returns_string(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_local_time(dt)
        assert isinstance(result, str)

    def test_contains_year(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_local_time(dt)
        assert "2024" in result

    def test_format_pattern(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_local_time(dt)
        # Should match YYYY-MM-DD HH:MM:SS TZ
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result)


# ---------------------------------------------------------------------------
# parse_time_period
# ---------------------------------------------------------------------------

class TestParseTimePeriod:
    def test_minutes(self):
        assert parse_time_period("30m") == timedelta(minutes=30)

    def test_hours(self):
        assert parse_time_period("2h") == timedelta(hours=2)

    def test_days(self):
        assert parse_time_period("1d") == timedelta(days=1)

    def test_weeks(self):
        assert parse_time_period("1w") == timedelta(weeks=1)

    def test_single_minute(self):
        assert parse_time_period("1m") == timedelta(minutes=1)

    def test_large_number(self):
        assert parse_time_period("100h") == timedelta(hours=100)

    def test_uppercase_accepted(self):
        assert parse_time_period("2H") == timedelta(hours=2)

    def test_invalid_format_raises(self):
        with pytest.raises(click.BadParameter):
            parse_time_period("2 hours")

    def test_invalid_unit_raises(self):
        with pytest.raises(click.BadParameter):
            parse_time_period("2x")

    def test_empty_string_raises(self):
        with pytest.raises(click.BadParameter):
            parse_time_period("")

    def test_no_number_raises(self):
        with pytest.raises(click.BadParameter):
            parse_time_period("m")

    def test_zero_minutes(self):
        assert parse_time_period("0m") == timedelta(minutes=0)
