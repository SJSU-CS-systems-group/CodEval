"""Unit tests for helper functions in github_connect.py."""
import os
import pytest
from unittest.mock import patch, MagicMock

from assignment_codeval.github_connect import _read_metadata, _setup_repos_for_assignment


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
