import os
import re
import shutil
import subprocess
from configparser import ConfigParser
from datetime import datetime, timezone
from functools import cache
from tempfile import TemporaryFile, TemporaryDirectory
from zipfile import ZipFile

import click
import requests

from assignment_codeval.canvas_utils import connect_to_canvas, get_course, get_assignment
from assignment_codeval.commons import debug, error, info, warn


@click.command()
@click.argument("submissions_dir", metavar="SUBMISSIONS_DIR")
@click.option("--codeval-prefix", help="prefix for codeval comments", default="codeval: ", show_default=True)
def upload_submission_comments(submissions_dir, codeval_prefix):
    """
    Upload comments for submissions from a directory.

    the submissions_dir specifies a directory that has comments to upload stored as:

    COURSE/ASSIGNMENT/STUDENT_ID/comments.txt

    if the file comments.txt.sent exists, the comment has already been uploaded and will be skipped.
    """
    (canvas, user) = connect_to_canvas()
    clean_submissions_dir = submissions_dir.rstrip('/')
    for dirpath, dirnames, filenames in os.walk(clean_submissions_dir):
        match = re.match(fr'^{clean_submissions_dir}/([^/]+)/([^/]+)/([^/]+)$', dirpath)
        if match:
            course_name = match.group(1)
            assignment_name = match.group(2)
            student_id = match.group(3)
            if "comments.txt" in filenames:
                if "comments.txt.sent" in filenames:
                    info(f"skipping already uploaded comments for {student_id} in {course_name}: {assignment_name}")
                else:
                    info(f"uploading comments for {student_id} in {course_name}: {assignment_name}")
                    course = get_course(canvas, course_name)
                    assignment = get_assignment(course, assignment_name)
                    with open(f"{dirpath}/comments.txt", "r") as fd:
                        comment = fd.read()
                        # nulls seem to be very problematic for canvas
                        comment = comment.replace("\0", "\\0").strip()
                        submission = get_submissions_by_id(assignment).get(student_id)
                        if submission:
                            submission.edit(comment={'text_comment': f'{codeval_prefix} {comment}'})
                        else:
                            warn(f"no submission found for {student_id} in {course_name}: {assignment_name}")
                    with open(f"{dirpath}/comments.txt.sent", "w") as fd:
                        fd.write(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))


@click.command()
@click.argument('codeval_dir', metavar="CODEVAL_DIR")
@click.option("--submissions-dir", help="directory containing submissions COURSE/ASSIGNMENT/STUDENT_ID", default='./submissions', show_default=True)
def evaluate_submissions(codeval_dir, submissions_dir):
    """
    Evaluate submissions stored in the form COURSE/ASSIGNMENT/STUDENT_ID.

    CODEVAL_DIR specifies a directory that has the codeval files named after the assignment with the .codeval suffix.
    """
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    parser.config_file = config_file

    raw_command = parser["RUN"]["command"]
    if not raw_command:
        warn(f"commands section under [RUN] in {parser.config_file} is empty")
    for dirpath, dirnames, filenames in os.walk(submissions_dir):
        match = re.match(fr'^{submissions_dir}/([^/]+)/([^/]+)/([^/]+)$', dirpath)
        if not match:
            continue

        assignment_name = match.group(2)
        repo_dir = os.path.abspath(os.path.join(dirpath, "repo"))

        codeval_file = os.path.join(codeval_dir, f"{assignment_name}.codeval")
        if not os.path.exists(codeval_file):
            warn(f"no codeval file found for {assignment_name} in {codeval_file}")
            continue

        # get the zipfiles (Z tag) and timeout (CTO tag)
        compile_timeout = 20
        assignment_working_dir = "."
        move_to_next_submission = False
        with open(codeval_file, "r") as fd:
            for line in fd:
                line = line.strip()
                if line.startswith("CTO"):
                    try:
                        compile_timeout = int(line.split(None, 1)[1])
                    except Exception:
                        warn(f"could not parse compile timeout from {line}, using default {compile_timeout}")
                if line.startswith("CD"):
                    assignment_working_dir = os.path.normpath(os.path.join(assignment_working_dir, line.split()[1].strip()))
                    if not os.path.exists(os.path.join(repo_dir, assignment_working_dir)):
                        out = f"{assignment_working_dir} does not exist\n".encode('utf-8')
                        move_to_next_submission = True
                        break
                if line.startswith("Z"):
                    zipfile = line.split(None, 1)[1]
                    # unzip into the repo directory
                    with ZipFile(zipfile) as zf:
                        zf.extractall(repo_dir)
        if not move_to_next_submission:
            command = raw_command.replace("EVALUATE", "cd /submissions; assignment-codeval run-evaluation codeval.txt")

            with TemporaryDirectory("cedir", dir="/var/tmp", delete=False) as link_dir:
                repo_link = os.path.join(link_dir, "submissions")
                os.symlink(repo_dir, repo_link)
                submissions_dir = os.path.join(repo_link, assignment_working_dir)
                shutil.copy(codeval_file, os.path.join(submissions_dir, "codeval.txt"))

                command = command.replace("SUBMISSIONS", submissions_dir)
                info(f"command to execute: {command}")
                p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                try:
                    out, err = p.communicate(timeout=compile_timeout)
                except subprocess.TimeoutExpired:
                    p.kill()
                    out, err = p.communicate()
                    out += bytes(f"\nTOOK LONGER THAN {compile_timeout} seconds to run. FAILED\n", encoding='utf-8')

        with open(f"{dirpath}/comments.txt", "wb") as fd:
            fd.write(out)


@click.command()
@click.argument("course_name", metavar="COURSE")
@click.argument("assignment_name", metavar="ASSIGNMENT")
@click.option("--target-dir", help="directory to download submissions to", default='./submissions', show_default=True)
@click.option("--only-uncommented", is_flag=True, help="only download submissions without codeval comments since last submission")
@click.option("--codeval-prefix", help="prefix for codeval comments", default="codeval: ", show_default=True)
@click.option("--include-empty", is_flag=True, help="include empty submissions")
def download_submissions(course_name, assignment_name, target_dir, only_uncommented, codeval_prefix, include_empty):
    """
    Download submissions for a given assignment in a course from Canvas.

    the COURSE and ASSIGNMENT arguments can be partial names.
    """
    (canvas, user) = connect_to_canvas()

    course = get_course(canvas, course_name)
    assignment = get_assignment(course, assignment_name)
    submission_dir = os.path.join(target_dir, course.name, assignment.name)
    os.makedirs(submission_dir, exist_ok=True)

    for submission in assignment.get_submissions(include=["submission_comments", "user"]):
        if not submission.attempt and not include_empty:
            continue
        submission_comments = [c['created_at'] for c in submission.submission_comments if
                               'comment' in c and c['comment'].startswith(codeval_prefix)]
        submission_comments.sort()
        if submission_comments:
            last_comment_date = submission_comments[-1]
        else:
            last_comment_date = None
        if only_uncommented and last_comment_date and submission.submitted_at <= last_comment_date:
            continue

        student_id = submission.user['login_id']
        student_submission_dir = os.path.join(submission_dir, student_id)
        os.makedirs(student_submission_dir, exist_ok=True)

        metapath = os.path.join(student_submission_dir, "metadata.txt")
        with open(metapath, "w") as fd:
            print(f"""id={student_id}
course={course.name}
assignment={assignment.name}
attempt={submission.attempt}
late={submission.late}
date={submission.submitted_at}
last_comment={last_comment_date}""", file=fd)
        body = submission.body
        if body:
            filepath = os.path.join(student_submission_dir, "content.txt")
            with open(filepath, "w") as fd:
                fd.write(body)
            debug(f"Downloaded content for student {student_id} to {filepath}")

        if hasattr(submission, "attachment"):
            attachment = submission.attachment
            fname = attachment['display_name']
            prefix = os.path.splitext(fname)[0]
            suffix = os.path.splitext(fname)[1]
            durl = attachment['url']
            filepath = os.path.join(student_submission_dir, f"{prefix}{suffix}")

            with requests.get(durl) as response:
                if response.status_code != 200:
                    error(f'error {response.status_code} fetching {durl}')
                with open(filepath, "wb") as fd:
                    for chunk in response.iter_content():
                        fd.write(chunk)

            debug(f"Downloaded submission for student {student_id} to {filepath}")

    return submission_dir


@cache
def get_submissions_by_id(assignment):
    submissions_by_id = {}
    for submission in assignment.get_submissions(include=["user"]):
        student_id = submission.user['login_id']
        submissions_by_id[student_id] = submission
    return submissions_by_id