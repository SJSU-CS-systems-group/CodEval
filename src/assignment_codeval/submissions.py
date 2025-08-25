import os
import re
import sys
from datetime import datetime, timezone
from functools import cache

import click
import requests

from assignment_codeval.canvas_utils import connect_to_canvas, get_course
from assignment_codeval.commons import debug, error, info, warn


@click.command()
@click.argument("submissions_dir", metavar="SUBMISSIONS_DIR")
@click.option("--codeval-prefix", help="prefix for codeval comments", default="codeval: ", show_default=True)
def upload_submission_comments(submissions_dir, codeval_prefix):
    """
    Upload comments for submissions from a directory.

    the submissions_dir specifies a directory that has comments to upload stored as:

    COURSE/ASSIGNMENT/STUDENT_ID/comments.txt

    if the file comments.txt.sent exts, the comment has already been uploaded and will be skipped.
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
                        comment = comment.replace("\0", "\\0")
                        comment.strip()
                        submission = get_submissions_by_id(assignment).get(student_id)
                        if submission:
                            submission.edit(comment={'text_comment': f'{codeval_prefix} {comment}'})
                        else:
                            warn(f"no submission found for {student_id} in {course_name}: {assignment_name}")
                    with open(f"{dirpath}/comments.txt.sent", "w") as fd:
                        fd.write(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))


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
def get_assignment(course, assignment_name):
    assignments = [a for a in course.get_assignments() if assignment_name.lower() in a.name.lower()]
    if len(assignments) == 0:
        error(f'no assignments found that contain {assignment_name}. options are:')
        for a in course.get_assignments():
            error(fr"    {a.name}")
        sys.exit(2)
    elif len(assignments) > 1:
        strict_name_assignments = [a for a in assignments if a.name == assignment_name]
        if len(strict_name_assignments) == 1:
            assignments = strict_name_assignments
        else:
            error(f"multiple assignments found for {assignment_name}: {[a.name for a in assignments]}")
            for a in assignments:
                error(f"    {a.name}")
            sys.exit(2)
    assignment = assignments[0]
    return assignment


@cache
def get_submissions_by_id(assignment):
    submissions_by_id = {}
    for submission in assignment.get_submissions(include=["user"]):
        student_id = submission.user['login_id']
        submissions_by_id[student_id] = submission
    return submissions_by_id