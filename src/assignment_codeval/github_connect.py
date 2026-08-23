import os
import re
import shutil
import subprocess
from time import sleep

import click

from assignment_codeval.commons import error, info

HEX_DIGITS = "0123456789abcdefABCDEF"


def _is_safe_repo_url(url):
    """Reject repo URLs that git would treat as an option or a code-executing transport.

    A clone URL is partly derived from a student-controlled GitHub id, so a value
    beginning with '-' (argument injection) or using git's ext::/file::/fd:: transport
    helpers (arbitrary command execution) must never reach `git clone`.
    """
    if not url or url.startswith('-'):
        return False
    authority = url.split('/', 1)[0]
    # ext::sh -c ... and friends use a "<helper>::" prefix before the first slash.
    if '::' in authority:
        return False
    # Require a recognized remote form: scheme://... or scp-like git@host:path.
    if re.match(r'^(https?|git|ssh)://', url, re.IGNORECASE):
        return True
    if re.match(r'^[\w.-]+@[\w.-]+:', url):
        return True
    return False


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


def _read_desired_commit(content_path):
    """Return the validated (hex) commit hash from content.txt, or None.

    content.txt holds the commit the student submitted, possibly wrapped in HTML
    tags/entities from Canvas; strip those and accept it only if it is all hex.
    """
    if not os.path.exists(content_path):
        return None
    with open(content_path, "r") as cfd:
        content = re.sub(r"<.*?>", "", cfd.readline().strip()).strip()
        content = re.sub(r"&[a-z]+;", "", content).strip()
    if content and all(c in HEX_DIGITS for c in content):
        return content
    return None


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
            # A clone already exists. If the student resubmitted a new commit,
            # the old checkout would grade the wrong attempt — re-clone in that
            # case. If we can't determine the desired commit, leave it as-is.
            desired_commit = _read_desired_commit(content_path)
            recorded_commit = None
            if os.path.exists(success_path):
                with open(success_path, "r") as sfd:
                    recorded_commit = sfd.readline().strip()
            if not desired_commit or recorded_commit == desired_commit:
                info(f"skipping {ssid_dir}, repo already at {recorded_commit or 'existing checkout'}")
                continue
            info(f"re-cloning {ssid_dir}: checked-out {recorded_commit} != submitted {desired_commit}")
            # Guard against removing anything but the clone directory.
            if os.path.basename(submission_path.rstrip("/")) == "submission":
                shutil.rmtree(submission_path)

        metadata = _read_metadata(ssid_dir)
        repo_url = metadata.get('github_repo', '')

        if not repo_url:
            continue

        click.echo(f"Setting up repo for {ssid_dir}")

        if not _is_safe_repo_url(repo_url):
            error(f"❌ refusing to clone unsafe repo url for {ssid}: {repo_url!r}")
            with open(result_path, "w") as fd:
                print(f"❌ refusing to clone unsafe repo url: {repo_url}", file=fd)
            continue

        with open(result_path, "w") as fd:
            # Read commit hash from content.txt
            content = _read_desired_commit(content_path)
            if not content:
                print(f"❌ an invalid git digest was found in {content_path}", file=fd)
                continue

            click.echo(f"Cloning {repo_url} to {ssid_dir}")
            print(f"cloning {repo_url}", file=fd)
            rc = subprocess.run(['git', 'clone', '--', repo_url, submission_path], stdout=fd, stderr=subprocess.STDOUT)
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
