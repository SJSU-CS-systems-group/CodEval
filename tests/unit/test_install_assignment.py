"""Tests for install_assignment command."""

import os
import tempfile
import zipfile
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from assignment_codeval.install_assignment import (
    install_assignment,
    is_remote_destination,
    parse_z_tags,
)


class TestIsRemoteDestination:
    """Tests for is_remote_destination function."""

    def test_local_path(self):
        assert is_remote_destination('/home/user/path') is False

    def test_relative_path(self):
        assert is_remote_destination('relative/path') is False

    def test_remote_path(self):
        assert is_remote_destination('server:/home/user/path') is True

    def test_remote_path_with_user(self):
        assert is_remote_destination('user@server:/path') is True

    def test_windows_drive_letter(self):
        assert is_remote_destination('C:\\Users\\path') is False

    def test_windows_drive_lowercase(self):
        assert is_remote_destination('c:\\Users\\path') is False


class TestParseZTags:
    """Tests for parse_z_tags function."""

    def test_no_z_tags(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.codeval', delete=False) as f:
            f.write('C gcc -o test test.c\n')
            f.write('T ./test\n')
            f.name
        try:
            result = parse_z_tags(f.name)
            assert result == []
        finally:
            os.unlink(f.name)

    def test_single_z_tag(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.codeval', delete=False) as f:
            f.write('Z support.zip\n')
            f.write('C gcc -o test test.c\n')
        try:
            result = parse_z_tags(f.name)
            assert result == ['support.zip']
        finally:
            os.unlink(f.name)

    def test_multiple_z_tags(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.codeval', delete=False) as f:
            f.write('Z first.zip\n')
            f.write('Z second.zip\n')
            f.write('C gcc -o test test.c\n')
        try:
            result = parse_z_tags(f.name)
            assert result == ['first.zip', 'second.zip']
        finally:
            os.unlink(f.name)

    def test_z_tag_with_whitespace(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.codeval', delete=False) as f:
            f.write('Z   support.zip  \n')
        try:
            result = parse_z_tags(f.name)
            assert result == ['support.zip']
        finally:
            os.unlink(f.name)


class TestInstallAssignmentCommand:
    """Tests for the install_assignment CLI command."""

    def test_local_install_codeval_only(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a codeval file
            codeval_path = os.path.join(tmpdir, 'test.codeval')
            with open(codeval_path, 'w') as f:
                f.write('C gcc -o test test.c\n')
                f.write('T ./test\n')

            # Create destination directory
            dest_dir = os.path.join(tmpdir, 'dest')
            os.makedirs(dest_dir)

            result = runner.invoke(install_assignment, [codeval_path, dest_dir])
            assert result.exit_code == 0
            assert 'No zip files referenced' in result.output
            assert 'Done' in result.output
            assert os.path.exists(os.path.join(dest_dir, 'test.codeval'))

    def test_local_install_with_zip(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a zip file
            zip_path = os.path.join(tmpdir, 'support.zip')
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr('helper.txt', 'test content')

            # Create a codeval file referencing the zip
            codeval_path = os.path.join(tmpdir, 'test.codeval')
            with open(codeval_path, 'w') as f:
                f.write('Z support.zip\n')
                f.write('C gcc -o test test.c\n')

            # Create destination directory
            dest_dir = os.path.join(tmpdir, 'dest')
            os.makedirs(dest_dir)

            result = runner.invoke(install_assignment, [codeval_path, dest_dir])
            assert result.exit_code == 0
            assert 'support.zip' in result.output
            assert 'Done' in result.output
            assert os.path.exists(os.path.join(dest_dir, 'test.codeval'))
            assert os.path.exists(os.path.join(dest_dir, 'support.zip'))

    def test_missing_zip_warning(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a codeval file referencing a non-existent zip
            codeval_path = os.path.join(tmpdir, 'test.codeval')
            with open(codeval_path, 'w') as f:
                f.write('Z missing.zip\n')
                f.write('C gcc -o test test.c\n')

            # Create destination directory
            dest_dir = os.path.join(tmpdir, 'dest')
            os.makedirs(dest_dir)

            result = runner.invoke(install_assignment, [codeval_path, dest_dir])
            assert result.exit_code == 0
            assert 'Warning: Referenced zip file not found' in result.output

    def test_verbose_output(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            codeval_path = os.path.join(tmpdir, 'test.codeval')
            with open(codeval_path, 'w') as f:
                f.write('C gcc -o test test.c\n')

            dest_dir = os.path.join(tmpdir, 'dest')
            os.makedirs(dest_dir)

            result = runner.invoke(install_assignment, [codeval_path, dest_dir, '--verbose'])
            assert result.exit_code == 0
            assert 'Copying' in result.output

    @patch('assignment_codeval.install_assignment.subprocess.run')
    def test_remote_destination_detected(self, mock_run):
        # Mock successful scp
        mock_run.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            codeval_path = os.path.join(tmpdir, 'test.codeval')
            with open(codeval_path, 'w') as f:
                f.write('C gcc -o test test.c\n')

            result = runner.invoke(install_assignment, [codeval_path, 'server:/path'])
            assert result.exit_code == 0
            assert 'Using scp for remote copy' in result.output
            # Verify scp was called
            mock_run.assert_called()

    def test_nonexistent_codeval_file(self):
        runner = CliRunner()
        result = runner.invoke(install_assignment, ['/nonexistent/file.codeval', '/dest'])
        assert result.exit_code != 0
