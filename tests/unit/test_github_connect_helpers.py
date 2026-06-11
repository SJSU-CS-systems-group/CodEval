"""Unit tests for helper functions in github_connect.py."""
import os
import pytest
from unittest.mock import patch, MagicMock

from assignment_codeval.github_connect import (
    _read_metadata, _setup_repos_for_assignment, _is_safe_repo_url, _read_desired_commit,
)


class TestIsSafeRepoUrl:
    @pytest.mark.parametrize("url", [
        "https://github.com/org/assign-123.git",
        "http://example.com/r.git",
        "git://github.com/u/r.git",
        "ssh://git@github.com/u/r.git",
        "git@github.com:u/r.git",
    ])
    def test_accepts_normal_remotes(self, url):
        assert _is_safe_repo_url(url) is True

    @pytest.mark.parametrize("url", [
        "",
        "-oProxyCommand=evil",
        "--upload-pack=evil",
        "ext::sh -c 'touch pwned'",
        "file::/etc/passwd",
        "fd::0",
        "/local/path",
        "just-a-string",
    ])
    def test_rejects_dangerous_or_unknown(self, url):
        assert _is_safe_repo_url(url) is False


class TestReadMetadata:
    def test_reads_key_value_pairs(self, tmp_path):
        meta = tmp_path / "metadata.txt"
        meta.write_text("name=John Doe\ngithub_repo=https://github.com/user/repo.git\n")
        result = _read_metadata(str(tmp_path))
        assert result["name"] == "John Doe"
        assert result["github_repo"] == "https://github.com/user/repo.git"

    def test_returns_empty_dict_when_no_file(self, tmp_path):
        result = _read_metadata(str(tmp_path))
        assert result == {}

    def test_skips_lines_without_equals(self, tmp_path):
        meta = tmp_path / "metadata.txt"
        meta.write_text("invalid line\nname=Alice\n")
        result = _read_metadata(str(tmp_path))
        assert "name" in result
        assert "invalid line" not in result

    def test_value_can_contain_equals(self, tmp_path):
        meta = tmp_path / "metadata.txt"
        meta.write_text("url=https://x.com?a=1&b=2\n")
        result = _read_metadata(str(tmp_path))
        assert result["url"] == "https://x.com?a=1&b=2"

    def test_empty_file_returns_empty_dict(self, tmp_path):
        meta = tmp_path / "metadata.txt"
        meta.write_text("")
        result = _read_metadata(str(tmp_path))
        assert result == {}


class TestSetupReposForAssignment:
    def test_skips_existing_submission_dir(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "submission").mkdir()
        with patch("assignment_codeval.github_connect.subprocess.run") as mock_run:
            _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
            mock_run.assert_not_called()

    def test_skips_when_no_github_repo(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "metadata.txt").write_text("name=Alice\n")
        with patch("assignment_codeval.github_connect.subprocess.run") as mock_run:
            _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
            mock_run.assert_not_called()

    def test_skips_invalid_git_digest(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "metadata.txt").write_text("github_repo=https://github.com/u/r.git\n")
        (ssid_dir / "content.txt").write_text("not-a-valid-hex-digest\n")
        with patch("assignment_codeval.github_connect.subprocess.run") as mock_run:
            _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
            mock_run.assert_not_called()

    def test_clones_repo_with_valid_digest(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "metadata.txt").write_text("github_repo=https://github.com/u/r.git\n")
        # Valid hex digest
        valid_hash = "a" * 40
        (ssid_dir / "content.txt").write_text(f"{valid_hash}\n")
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("assignment_codeval.github_connect.subprocess.run", return_value=mock_result):
            with patch("assignment_codeval.github_connect.sleep"):
                _setup_repos_for_assignment(str(tmp_path), clone_delay=0)

    def test_refuses_unsafe_repo_url(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "metadata.txt").write_text("github_repo=ext::sh -c touch\n")
        (ssid_dir / "content.txt").write_text("a" * 40 + "\n")
        with patch("assignment_codeval.github_connect.subprocess.run") as mock_run:
            _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
            mock_run.assert_not_called()
        assert "refusing to clone unsafe repo url" in (ssid_dir / "comments.txt").read_text()

    def test_reclones_when_commit_changed(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "submission").mkdir()
        (ssid_dir / "metadata.txt").write_text("github_repo=https://github.com/u/r.git\n")
        (ssid_dir / "content.txt").write_text("b" * 40 + "\n")
        (ssid_dir / "gh_success.txt").write_text("a" * 40 + "\n")  # old commit
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("assignment_codeval.github_connect.subprocess.run", return_value=mock_result) as mock_run:
            with patch("assignment_codeval.github_connect.sleep"):
                _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
        # Commit changed -> stale clone removed and a fresh clone attempted.
        assert mock_run.called

    def test_skips_when_commit_unchanged(self, tmp_path):
        ssid_dir = tmp_path / "12345"
        ssid_dir.mkdir()
        (ssid_dir / "submission").mkdir()
        (ssid_dir / "metadata.txt").write_text("github_repo=https://github.com/u/r.git\n")
        same = "c" * 40
        (ssid_dir / "content.txt").write_text(same + "\n")
        (ssid_dir / "gh_success.txt").write_text(same + "\n")
        with patch("assignment_codeval.github_connect.subprocess.run") as mock_run:
            _setup_repos_for_assignment(str(tmp_path), clone_delay=0)
            mock_run.assert_not_called()


class TestReadDesiredCommit:
    def test_reads_plain_hash(self, tmp_path):
        (tmp_path / "content.txt").write_text("a" * 40 + "\n")
        assert _read_desired_commit(str(tmp_path / "content.txt")) == "a" * 40

    def test_strips_html_wrapping(self, tmp_path):
        (tmp_path / "content.txt").write_text("<p>abcdef1234</p>\n")
        assert _read_desired_commit(str(tmp_path / "content.txt")) == "abcdef1234"

    def test_rejects_non_hex(self, tmp_path):
        (tmp_path / "content.txt").write_text("not-hex-zzz\n")
        assert _read_desired_commit(str(tmp_path / "content.txt")) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert _read_desired_commit(str(tmp_path / "nope.txt")) is None
