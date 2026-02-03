import os
import re
import subprocess
from time import sleep

import click

from assignment_codeval.commons import error, info

HEX_DIGITS = "0123456789abcdefABCDEF"


def _read_metadata(ssid_dir):
    """Read metadata.txt and return a dict of key=value pairs."""
    metadata_path = os.path.join(ssid_dir, "metadata.txt")
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    metadata[key] = value
    return metadata


@click.command()
@click.argument("target_dir", metavar="SUBMISSIONS_DIR", default='./submissions')
@click.option("--clone-delay",
              help="seconds to wait between cloning repos. github will sometimes return an error if you clone too fast.",
              default=1, show_default=True)
def github_setup_repo(target_dir, clone_delay):
    """
    Clone GitHub repositories for submissions that have github_repo in metadata.txt.

    Scans SUBMISSIONS_DIR for course/assignment/student_id subdirectories and clones
    repos using the github_repo field from metadata.txt.
    """
    if not os.path.isdir(target_dir):
        error(f"submissions directory {target_dir} does not exist")
        return

    for course_dir in sorted(os.listdir(target_dir)):
        course_path = os.path.join(target_dir, course_dir)
        if not os.path.isdir(course_path):
            continue
        for assignment_dir in sorted(os.listdir(course_path)):
            assignment_path = os.path.join(course_path, assignment_dir)
            if not os.path.isdir(assignment_path):
                continue
            info(f"processing {course_dir}/{assignment_dir}")
            _setup_repos_for_assignment(assignment_path, clone_delay)


def _setup_repos_for_assignment(assignment_path, clone_delay):
    """Set up GitHub repos for a single assignment."""
    for ssid in sorted(os.listdir(assignment_path)):
        ssid_dir = os.path.join(assignment_path, ssid)
        if not os.path.isdir(ssid_dir):
            continue

        result_path = os.path.join(ssid_dir, "comments.txt")
        success_path = os.path.join(ssid_dir, "gh_success.txt")
        content_path = os.path.join(ssid_dir, "content.txt")
        submission_path = os.path.join(ssid_dir, "submission")

        if os.path.exists(submission_path):
            info(f"skipping {ssid_dir}, repo already exists at {submission_path}")
            continue

        metadata = _read_metadata(ssid_dir)
        repo_url = metadata.get('github_repo', '')

        if not repo_url:
            continue

        click.echo(f"Setting up repo for {ssid_dir}")

        with open(result_path, "w") as fd:
            # Read commit hash from content.txt
            content = None
            if os.path.exists(content_path):
                with open(content_path, "r") as cfd:
                    content = re.sub(r"<.*?>", "", cfd.readline().strip()).strip()
                    content = re.sub(r"&[a-z]+;", "", content).strip()
            if not content or not all(c in HEX_DIGITS for c in content):
                print(f"❌ an invalid git digest was found: {content}", file=fd)
                continue

            click.echo(f"Cloning {repo_url} to {ssid_dir}")
            print(f"cloning {repo_url}", file=fd)
            rc = subprocess.run(['git', 'clone', repo_url, submission_path], stdout=fd, stderr=subprocess.STDOUT)
            if rc.returncode != 0:
                error(f"❌ error {rc.returncode} connecting to github repo for {ssid} using {repo_url}")
                continue
            subprocess.run(['git', 'config', 'advice.detachedHead', 'false'], cwd=submission_path)
            rc = subprocess.run(['git', 'checkout', content], cwd=submission_path, stdout=fd, stderr=subprocess.STDOUT)
            if rc.returncode != 0:
                print(f"❌ error {rc.returncode} checking out {content}", file=fd)
                continue
            print(f"✅ successfully connected to {repo_url} and checked out {content}", file=fd)
            with open(success_path, "w") as sfd:
                print(content, file=sfd)
        sleep(clone_delay)
