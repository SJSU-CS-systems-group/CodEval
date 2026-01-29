import os
import re
import subprocess
from configparser import ConfigParser
from time import sleep

import click

from assignment_codeval.canvas_utils import get_course, connect_to_canvas, get_assignment
from assignment_codeval.commons import error, info, despace

HEX_DIGITS = "0123456789abcdefABCDEF"


@click.command()
@click.argument("course_name", metavar="COURSE", required=False)
@click.argument("assignment_name", metavar="ASSIGNMENT", required=False)
@click.option("--all-repos", is_flag=True,
              help="download all repositories, even if they don't have a valid commit hash")
@click.option("--target-dir", help="directory to download submissions to", default='./submissions', show_default=True)
@click.option("--github-field", help="GitHub field name in canvas profile", default="github", show_default=True)
@click.option("--clone-delay",
              help="seconds to wait between cloning repos. github will sometimes return an error if you clone to fast.e",
              default=1, show_default=True)
def github_setup_repo(course_name, assignment_name, target_dir, github_field, all_repos, clone_delay):
    """
    Connect to a GitHub repository for a given course and assignment.

    COURSE can be a unique substring of the actual course name.

    If COURSE and ASSIGNMENT are not specified, will process all course/assignment
    subdirectories found in the submissions directory.
    """
    canvas, user = connect_to_canvas()
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    parser.config_file = config_file

    if course_name and assignment_name:
        # Explicit course and assignment specified
        course = get_course(canvas, course_name, True)
        assignment = get_assignment(course, assignment_name)
        _setup_repo_for_assignment(
            canvas, parser, course, assignment, target_dir, github_field, all_repos, clone_delay
        )
    elif course_name or assignment_name:
        raise click.UsageError("Both COURSE and ASSIGNMENT must be specified, or neither")
    else:
        # Scan submissions directory for course/assignment subdirectories
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
                course = get_course(canvas, course_dir, True)
                assignment = get_assignment(course, assignment_dir)
                _setup_repo_for_assignment(
                    canvas, parser, course, assignment, target_dir, github_field, all_repos, clone_delay
                )


def _setup_repo_for_assignment(canvas, parser, course, assignment, target_dir, github_field, all_repos, clone_delay):
    """Set up GitHub repos for a single assignment."""
    submission_dir = os.path.join(target_dir, despace(course.name), despace(assignment.name))
    os.makedirs(submission_dir, exist_ok=True)

    gh_key = course.name.replace(":", "").replace("=", "")
    if 'GITHUB' not in parser or gh_key not in parser['GITHUB']:
        error(f"did not find mapping for {gh_key} in GITHUB section of {parser.config_file}.")
        return

    gh_repo_prefix = parser['GITHUB'][gh_key]

    users = course.get_users(include=["enrollments"])
    for user in users:
        ssid = str(user.id)
        ssid_dir = os.path.join(submission_dir, ssid)
        click.echo(f"Checking {ssid_dir}")
        if not all_repos and not os.path.exists(ssid_dir):
            continue
        click.echo(f"Finding repo for {ssid_dir}")

        os.makedirs(ssid_dir, exist_ok=True)
        result_path = f"{ssid_dir}/comments.txt"
        success_path = f"{ssid_dir}/gh_success.txt"
        content_path = f"{ssid_dir}/content.txt"
        submission_path = os.path.join(ssid_dir, "submission")
        if os.path.exists(submission_path):
            info(f"skipping {ssid_dir}, repo already exists at {submission_path}")
            continue
        with open(result_path, "w") as fd:
            content = None
            if os.path.exists(content_path):
                with open(f"{ssid_dir}/content.txt", "r") as cfd:
                    content = re.sub(r"<.*?>", "", cfd.readline().strip()).strip()
                    content = re.sub(r"&[a-z]+;", "", content).strip()
            if not content or not all(c in HEX_DIGITS for c in content):
                print(f"❌ an invalid git digest was found: {content}", file=fd)
                continue

            profile = user.get_profile(include=["links", "link"])
            gh_links = None
            if 'links' in profile:
                gh_links = [m['url'] for m in profile['links'] if m['title'].lower() == github_field.lower()]
            if not gh_links:
                print(f"❌ no {github_field} link found in canvas profile", file=fd)
                continue
            if len(gh_links) != 1:
                print(f"❌ multiple {github_field} links found in canvas profile", file=fd)
                continue
            gh_url = gh_links[0]
            gh_id = gh_url.rstrip('/').rsplit('/', 1)[-1]
            repo_url = f"{gh_repo_prefix}-{gh_id}.git"
            click.echo(f"Cloning repo for {gh_id} to {ssid_dir}")
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
