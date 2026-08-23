"""Unit tests for file_utils.py."""
import os
import stat
import zipfile
from unittest.mock import patch, MagicMock
import pytest

from assignment_codeval.file_utils import unzip, set_acls, download_attachment


class TestUnzip:
    def _make_zip(self, path, files):
        """Create a zip file at path containing the given {name: content} files."""
        with zipfile.ZipFile(path, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return path

    def test_extracts_files(self, tmp_path):
        zip_path = tmp_path / "test.zip"
        self._make_zip(str(zip_path), {"hello.txt": "hello world"})
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest))
        assert (dest / "hello.txt").exists()
        assert (dest / "hello.txt").read_text() == "hello world"

    def test_extracts_multiple_files(self, tmp_path):
        zip_path = tmp_path / "multi.zip"
        self._make_zip(str(zip_path), {"a.txt": "aaa", "b.txt": "bbb"})
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest))
        assert (dest / "a.txt").exists()
        assert (dest / "b.txt").exists()

    def test_delete_option_removes_zip(self, tmp_path):
        zip_path = tmp_path / "del.zip"
        self._make_zip(str(zip_path), {"f.txt": "content"})
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest), delete=True)
        assert not zip_path.exists()

    def test_no_delete_keeps_zip(self, tmp_path):
        zip_path = tmp_path / "keep.zip"
        self._make_zip(str(zip_path), {"f.txt": "content"})
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest), delete=False)
        assert zip_path.exists()

    def test_executable_bit_preserved(self, tmp_path):
        """Files with executable external_attr should have exec bit set after extraction."""
        zip_path = tmp_path / "exec.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            info = zipfile.ZipInfo("script.sh")
            # Set owner-executable bit in external_attr (Unix permissions in high 16 bits)
            info.external_attr = (0o755 << 16)
            zf.writestr(info, "#!/bin/bash\necho hi\n")
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest))
        extracted = dest / "script.sh"
        assert extracted.exists()
        file_mode = os.stat(str(extracted)).st_mode
        assert file_mode & stat.S_IXUSR  # owner execute bit

    def test_zip_slip_chmod_does_not_escape_dir(self, tmp_path):
        """A '../' member must not cause chmod on a file outside the extract dir."""
        outside = tmp_path / "outside.txt"
        outside.write_text("do not touch")
        outside.chmod(0o600)
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            info = zipfile.ZipInfo("../outside.txt")
            info.external_attr = (0o777 << 16)
            zf.writestr(info, "pwned")
        dest = tmp_path / "out"
        dest.mkdir()
        unzip(str(zip_path), str(dest))
        # The pre-existing file outside the extract dir keeps its mode.
        assert stat.S_IMODE(os.stat(str(outside)).st_mode) == 0o600
        assert outside.read_text() == "do not touch"


class TestDownloadAttachment:
    def _attachment(self, name, url):
        return {"display_name": name, "url": url}

    def test_downloads_file_to_directory(self, tmp_path):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status_code = 200
        resp.iter_content.return_value = [b"hello"]
        with patch("requests.get", return_value=resp):
            result = download_attachment(str(tmp_path),
                                         self._attachment("file.txt", "http://x.com/f"))
        assert (tmp_path / "file.txt").exists()
        assert (tmp_path / "file.txt").read_bytes() == b"hello"

    def test_uses_relative_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "subdir").mkdir()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status_code = 200
        resp.iter_content.return_value = [b"data"]
        with patch("requests.get", return_value=resp):
            result = download_attachment("subdir",
                                         self._attachment("out.txt", "http://x.com/f"))
        assert (tmp_path / "subdir" / "out.txt").exists()

    def test_raises_and_writes_nothing_on_bad_status(self, tmp_path):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status_code = 404
        resp.iter_content.return_value = [b"<html>not found</html>"]
        with patch("requests.get", return_value=resp):
            with pytest.raises(EnvironmentError):
                download_attachment(str(tmp_path),
                                    self._attachment("f.txt", "http://x.com/f"))
        # The error page body must not be saved as if it were the attachment.
        assert not (tmp_path / "f.txt").exists()

    def test_traversal_filename_is_collapsed_to_basename(self, tmp_path):
        (tmp_path / "safe").mkdir()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status_code = 200
        resp.iter_content.return_value = [b"x"]
        with patch("requests.get", return_value=resp):
            result = download_attachment(str(tmp_path / "safe"),
                                         self._attachment("../../evil.txt", "http://x.com/f"))
        # Must stay inside the target directory, not escape via "..".
        assert result == str(tmp_path / "safe" / "evil.txt")
        assert (tmp_path / "safe" / "evil.txt").exists()
        assert not (tmp_path / "evil.txt").exists()


class TestSetAcls:
    def test_calls_chmod_on_macos(self, tmp_path):
        with patch("sys.platform", "darwin"):
            with patch("subprocess.call") as mock_call:
                set_acls(str(tmp_path))
                mock_call.assert_called_once_with(["chmod", "-R", "o+rwx", str(tmp_path)])

    def test_calls_setfacl_on_linux(self, tmp_path):
        with patch("sys.platform", "linux"):
            with patch("subprocess.call") as mock_call:
                set_acls(str(tmp_path))
                mock_call.assert_called_once_with(
                    ["setfacl", "-d", "-m", "o::rwx", str(tmp_path)]
                )
