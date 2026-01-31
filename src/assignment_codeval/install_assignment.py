#! /usr/bin/python3
"""Install a codeval assignment file and its referenced zip files to a destination."""

import os
import re
import shutil
import subprocess

import click


def parse_z_tags(codeval_path: str) -> list[str]:
    """Parse a codeval file and return a list of zip files referenced by Z tags.

    Arguments:
        codeval_path: Path to the codeval file

    Returns:
        List of zip file paths referenced by Z tags
    """
    zip_files = []
    with open(codeval_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('Z '):
                zip_file = line[2:].strip()
                if zip_file:
                    zip_files.append(zip_file)
    return zip_files


def is_remote_destination(destination: str) -> bool:
    """Check if destination is a remote path (host:path format).

    Arguments:
        destination: The destination path

    Returns:
        True if destination is remote (contains : but not a Windows drive letter)
    """
    # Match host:path pattern but not Windows drive letters like C:\
    if ':' not in destination:
        return False
    # Windows drive letter check (e.g., C:\path)
    if re.match(r'^[A-Za-z]:\\', destination):
        return False
    return True


def copy_file(source: str, destination: str, verbose: bool = False) -> None:
    """Copy a file to a local or remote destination.

    Arguments:
        source: Path to the source file
        destination: Destination path (local or host:path for remote)
        verbose: Print verbose output

    Raises:
        click.ClickException: If copy fails
    """
    if is_remote_destination(destination):
        # Use scp for remote destinations
        cmd = ['scp', source, destination]
        if verbose:
            click.echo(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise click.ClickException(f"scp failed: {result.stderr}")
    else:
        # Local copy
        if verbose:
            click.echo(f"Copying {source} to {destination}")
        os.makedirs(destination, exist_ok=True)
        shutil.copy2(source, destination)


@click.command()
@click.argument('codeval_file', type=click.Path(exists=True))
@click.argument('destination')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def install_assignment(codeval_file: str, destination: str, verbose: bool):
    """Install a codeval file and its referenced zip files to a destination.

    CODEVAL_FILE is the path to the codeval specification file.

    DESTINATION is either a local path or a remote path in host:path format.
    If remote, scp will be used to copy files.

    \b
    Examples:
        # Local install
        assignment-codeval install-assignment myassign.codeval /path/to/dest

        # Remote install
        assignment-codeval install-assignment myassign.codeval server:/home/user/assignments
    """
    codeval_path = os.path.abspath(codeval_file)
    codeval_dir = os.path.dirname(codeval_path)
    codeval_name = os.path.basename(codeval_path)

    # Parse Z tags to find referenced zip files
    zip_files = parse_z_tags(codeval_path)

    # Build list of files to copy
    files_to_copy = [codeval_path]

    for zip_file in zip_files:
        # Zip files are relative to the codeval file's directory
        zip_path = os.path.join(codeval_dir, zip_file)
        if os.path.exists(zip_path):
            files_to_copy.append(zip_path)
        else:
            click.echo(f"Warning: Referenced zip file not found: {zip_path}", err=True)

    # Show summary
    click.echo(f"Codeval file: {codeval_name}")
    if zip_files:
        click.echo(f"Referenced zip files: {', '.join(zip_files)}")
    else:
        click.echo("No zip files referenced")
    click.echo(f"Destination: {destination}")

    if is_remote_destination(destination):
        click.echo("Using scp for remote copy")

    # Copy files
    for source_path in files_to_copy:
        filename = os.path.basename(source_path)
        if is_remote_destination(destination):
            # For remote, append filename to destination
            dest_path = f"{destination}/{filename}"
        else:
            dest_path = destination

        try:
            copy_file(source_path, dest_path, verbose)
            click.echo(f"Copied: {filename}")
        except click.ClickException as e:
            raise e
        except Exception as e:
            raise click.ClickException(f"Failed to copy {filename}: {e}")

    click.echo("Done")
