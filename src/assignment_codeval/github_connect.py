import os.path
import subprocess
from configparser import ConfigParser

import click

from assignment_codeval.canvas_utils import get_course, connect_to_canvas
from assignment_codeval.commons import error, debug


@click.command()
@click.argument("course_name", metavar="COURSE")
@click.option("--github-field", help="GitHub field name in canvas profile", default="github", show_default=True)
def github_setup_repo(course_name, github_field):
    """
    Connect to a GitHub repository for a given course and assignment.

    COURSE can be a unique substring of the actual course name.

    GITHUB_PREFIX is the prefix of the GitHub repository name, it should have a form similar to:

    git@github.com:<gh_classroom_account>/<gh_classroom_assignment>
    """
    canvas, user = connect_to_canvas()
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    parser.config_file = config_file
    course = get_course(canvas, course_name, True)

    gh_key = course.name.replace(":", "").replace("=", "")
    if 'GITHUB' not in parser or gh_key not in parser['GITHUB']:
        error(f"did not find mapping for {gh_key} in GITHUB section of {parser.config_file}.")
        return

    gh_repo_prefix = parser['GITHUB'][gh_key]

    users = course.get_users(include=["enrollments"])
    for user in users:
        ssid = user.login_id
        os.makedirs(ssid, exist_ok=True)
        with open(f"{ssid}/gh_result.txt", "w") as fd:
            profile = user.get_profile(include=["links", "link"])
            gh_links = None
            if 'links' in profile:
                gh_links = [m['url'] for m in profile['links'] if m['title'].lower() == github_field.lower()]
            if not gh_links:
                print(f"no {github_field} link found in canvas profile", file=fd)
                continue
            if len(gh_links) != 1:
                print(f"multiple {github_field} links found in canvas profile", file=fd)
                continue
            gh_url = gh_links[0]
            gh_id = gh_url.rstrip('/').rsplit('/', 1)[-1]
            repo_url = f"{gh_repo_prefix}-{gh_id}.git"
            if os.path.exists(f'{ssid}/repo'):
                print(f"pulling {repo_url}", file=fd)
                rc = subprocess.run(['git', 'pull'], cwd=f'{ssid}/repo', stdout=fd, stderr=subprocess.STDOUT)
            else:
                print(f"cloning {repo_url}", file=fd)
                rc = subprocess.run(['git', 'clone', repo_url, f'{ssid}/repo'], stdout=fd, stderr=subprocess.STDOUT)
            if rc.returncode != 0:
                error(f"error {rc.returncode} connecting to github repo for {ssid} using {repo_url}")
