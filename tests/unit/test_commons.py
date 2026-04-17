"""Unit tests for commons.py utility functions."""
import pytest
import assignment_codeval.commons as _commons_mod
from assignment_codeval.commons import (
    despace, get_config, set_config, debug, error, errorWithException, info, warn,
)


@pytest.fixture(autouse=True)
def reset_config():
    """Reset singleton config instance before each test."""
    _commons_mod._Config._instance = None
    yield
    _commons_mod._Config._instance = None


class TestDespace:
    def test_replaces_spaces_with_underscore(self):
        assert despace("hello world") == "hello_world"

    def test_removes_colons(self):
        assert despace("foo:bar") == "foobar"

    def test_both_transformations(self):
        assert despace("CS 101: Intro") == "CS_101_Intro"

    def test_empty_string(self):
        assert despace("") == ""

    def test_no_changes_needed(self):
        assert despace("helloworld") == "helloworld"

    def test_multiple_spaces(self):
        assert despace("a b c") == "a_b_c"

    def test_multiple_colons(self):
        assert despace("a:b:c") == "abc"


class TestGetConfig:
    def test_returns_config_instance(self):
        config = get_config()
        assert config is not None

    def test_default_show_debug_false(self):
        assert get_config().show_debug is False

    def test_default_dry_run_true(self):
        assert get_config().dry_run is True

    def test_returns_same_instance_on_repeated_calls(self):
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


class TestSetConfig:
    def test_sets_all_values(self):
        config = set_config(show_debug=True, dry_run=False, force=True, copy_tmpdir=True)
        assert config.show_debug is True
        assert config.dry_run is False
        assert config.force is True
        assert config.copy_tmpdir is True

    def test_debug_false_dry_run_true(self):
        config = set_config(show_debug=False, dry_run=True, force=False, copy_tmpdir=False)
        assert config.show_debug is False
        assert config.dry_run is True

    def test_get_config_returns_set_config(self):
        set_config(show_debug=True, dry_run=False, force=False, copy_tmpdir=False)
        assert get_config().show_debug is True


class TestDebug:
    def test_not_printed_when_show_debug_false(self, capsys):
        set_config(show_debug=False, dry_run=False, force=False, copy_tmpdir=False)
        debug("hidden message")
        assert "hidden message" not in capsys.readouterr().out

    def test_printed_when_show_debug_true(self, capsys):
        set_config(show_debug=True, dry_run=False, force=False, copy_tmpdir=False)
        debug("visible message")
        assert "visible message" in capsys.readouterr().out

    def test_output_contains_d_marker(self, capsys):
        set_config(show_debug=True, dry_run=False, force=False, copy_tmpdir=False)
        debug("test")
        assert " D " in capsys.readouterr().out


class TestError:
    def test_always_printed(self, capsys):
        error("something went wrong")
        assert "something went wrong" in capsys.readouterr().out

    def test_output_contains_e_marker(self, capsys):
        error("msg")
        assert " E " in capsys.readouterr().out


class TestErrorWithException:
    def test_raises_environment_error(self):
        with pytest.raises(EnvironmentError):
            errorWithException("fatal error")

    def test_exception_message_matches(self):
        with pytest.raises(EnvironmentError, match="bad config"):
            errorWithException("bad config")

    def test_also_prints_error(self, capsys):
        with pytest.raises(EnvironmentError):
            errorWithException("printed error")
        assert "printed error" in capsys.readouterr().out


class TestInfo:
    def test_always_printed(self, capsys):
        info("info message")
        assert "info message" in capsys.readouterr().out

    def test_output_contains_i_marker(self, capsys):
        info("msg")
        assert " I " in capsys.readouterr().out


class TestWarn:
    def test_always_printed(self, capsys):
        warn("warning message")
        assert "warning message" in capsys.readouterr().out

    def test_output_contains_w_marker(self, capsys):
        warn("msg")
        assert " W " in capsys.readouterr().out
