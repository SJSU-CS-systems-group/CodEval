import os
import re
import shutil
import subprocess
import time
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from functools import cache
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import click
import requests

from assignment_codeval.canvas_utils import connect_to_canvas, get_course, get_courses, get_assignment
from assignment_codeval.commons import debug, error, info, warn, despace


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
                        comment = comment.replace("\0", "\\0").strip().replace("<", "&lt;")
                        submission = get_submissions_by_id(assignment).get(student_id)
                        if submission:
                            submission.edit(comment={'text_comment': f'{codeval_prefix}<pre>\n{comment}</pre>'})
                        else:
                            warn(f"no submission found for {student_id} in {course_name}: {assignment_name}")
                    with open(f"{dirpath}/comments.txt.sent", "w") as fd:
                        fd.write(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))


@click.command()
@click.argument('codeval_dir', metavar="CODEVAL_DIR")
@click.option("--submissions-dir", help="directory containing submissions COURSE/ASSIGNMENT/STUDENT_ID",
              default='./submissions', show_default=True)
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

        info(f"processing {dirpath}")

        assignment_name = match.group(2)
        submission_dir = os.path.abspath(os.path.join(dirpath, "submission"))

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
                    assignment_working_dir = os.path.normpath(
                        os.path.join(assignment_working_dir, line.split()[1].strip()))
                    if not os.path.isdir(os.path.join(submission_dir, assignment_working_dir)):
                        out = f"{assignment_working_dir} does not exist or is not a directory\n".encode('utf-8')
                        move_to_next_submission = True
                        break
                if line.startswith("Z"):
                    zipfile = line.split(None, 1)[1]
                    # unzip into the submission directory
                    with ZipFile(os.path.join(codeval_dir, zipfile)) as zf:
                        for f in zf.infolist():
                            dest_dir = os.path.join(submission_dir, assignment_working_dir)
                            zf.extract(f, dest_dir)
                            if not f.is_dir():
                                perms = f.external_attr >> 16
                                if perms:
                                    os.chmod(os.path.join(dest_dir, f.filename), perms)

        if not move_to_next_submission:
            command = raw_command.replace("EVALUATE", "cd /submissions; assignment-codeval run-evaluation codeval.txt")

            with TemporaryDirectory("cedir", dir="/var/tmp") as link_dir:
                submission_link = os.path.join(link_dir, "submissions")
                os.symlink(submission_dir, submission_link)
                full_assignment_working_dir = os.path.join(submission_link, assignment_working_dir)
                if not os.path.isdir(full_assignment_working_dir):
                    out = b"no submission directory found"
                else:
                    shutil.copy(codeval_file, os.path.join(full_assignment_working_dir, "codeval.txt"))

                    command = command.replace("SUBMISSIONS", full_assignment_working_dir)
                    info(f"command to execute: {command}")
                    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    try:
                        out, err = p.communicate(timeout=compile_timeout)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        out, err = p.communicate()
                        out += bytes(f"\nTOOK LONGER THAN {compile_timeout} seconds to run. FAILED\n", encoding='utf-8')
                    except Exception as e:
                        error(f"exception {e} running evaluation for {dirpath}")
                        p.kill()
                        out, err = p.communicate()
                        out += bytes(f"\nFAILED with exception {e}\n", encoding='utf-8')
                    finally:
                        info("finished executing docker")

        info("writing results")
        with open(f"{dirpath}/comments.txt", "ab") as fd:
            fd.write(out)
        info("continuing")


@click.command()
@click.argument("course_name", metavar="COURSE", required=False)
@click.argument("assignment_name", metavar="ASSIGNMENT", required=False)
@click.option("--active", is_flag=True, help="download from all active assignments in all active courses")
@click.option("--until-window", default=24, show_default=True,
              help="hours after the until date to still consider an assignment active")
@click.option("--target-dir", help="directory to download submissions to", default='./submissions', show_default=True)
@click.option("--include-commented", is_flag=True,
              help="even download submissionsthat already have codeval comments since last submission")
@click.option("--uncommented_for",
              help="only download submission where the last comment is more than these minutes ago", default=0,
              show_default=True)
@click.option("--codeval-prefix", help="prefix for codeval comments", default="codeval: ", show_default=True)
@click.option("--include-empty", is_flag=True, help="include empty submissions")
@click.option("--for-name", help="only download submissions for this student name")
def download_submissions(course_name, assignment_name, active, until_window, target_dir, include_commented,
                         codeval_prefix, include_empty, uncommented_for, for_name):
    """
    Download submissions for a given assignment in a course from Canvas.

    The COURSE and ASSIGNMENT arguments can be partial names.

    Use --active to download from all active assignments in all active courses
    (COURSE and ASSIGNMENT are not required when --active is used).
    """
    if not active and (not course_name or not assignment_name):
        raise click.UsageError("COURSE and ASSIGNMENT are required unless --active is specified")

    (canvas, user) = connect_to_canvas()

    if active:
        # Load codeval directory from config
        parser = ConfigParser()
        config_file = click.get_app_dir("codeval.ini")
        parser.read(config_file)
        if 'CODEVAL' not in parser or 'directory' not in parser['CODEVAL']:
            raise click.UsageError(f"[CODEVAL] section with directory= is required in {config_file}")
        codeval_dir = parser['CODEVAL']['directory']

        courses = get_courses(canvas, course_name or "", is_active=True)
        if not courses:
            error("no active courses found")
            return

        now = datetime.now(timezone.utc)
        for course in courses:
            for assignment in course.get_assignments():
                if assignment_name and assignment_name.lower() not in despace(assignment.name).lower():
                    continue
                # Check if assignment is active: availability date passed and until date + window not passed
                unlock_at = getattr(assignment, 'unlock_at_date', None)
                lock_at = getattr(assignment, 'lock_at_date', None)
                if unlock_at and unlock_at > now:
                    continue  # not yet available
                if lock_at:
                    window = timedelta(hours=until_window)
                    if lock_at + window < now:
                        continue  # past the until window

                # Filter by submission type: only text_entry (GitHub) or file upload assignments
                submission_types = getattr(assignment, 'submission_types', [])
                if "online_text_entry" not in submission_types and "online_upload" not in submission_types:
                    continue

                # Only download if a corresponding codeval file exists
                codeval_file = os.path.join(codeval_dir, f"{despace(assignment.name)}.codeval")
                if not os.path.exists(codeval_file):
                    continue

                info(f"downloading submissions for {course.name}: {assignment.name}")
                _download_assignment_submissions(
                    course, assignment, target_dir, include_commented, codeval_prefix,
                    include_empty, uncommented_for, for_name
                )
        return

    course = get_course(canvas, course_name)
    assignment = get_assignment(course, assignment_name)
    _download_assignment_submissions(
        course, assignment, target_dir, include_commented, codeval_prefix,
        include_empty, uncommented_for, for_name
    )


def _download_assignment_submissions(course, assignment, target_dir, include_commented, codeval_prefix,
                                     include_empty, uncommented_for, for_name):
    """Download submissions for a single assignment."""
    submission_dir = os.path.join(target_dir, despace(course.name), despace(assignment.name))
    os.makedirs(submission_dir, exist_ok=True)

    for submission in assignment.get_submissions(include=["submission_comments", "user"]):
        if not submission.attempt and not include_empty:
            continue

        student_id = str(submission.user_id)
        student_name = submission.user['name']

        if for_name and for_name not in student_name:
            continue

        submission_comments = [c['created_at'] for c in submission.submission_comments if
                               'comment' in c and c['comment'].startswith(codeval_prefix)]
        submission_comments.sort()
        if submission_comments:
            last_comment_date = submission_comments[-1]
        else:
            last_comment_date = None
        if not include_commented and last_comment_date and submission.submitted_at and submission.submitted_at <= last_comment_date:
            continue

        if uncommented_for > 0 and last_comment_date:
            last_comment_dt = datetime.strptime(last_comment_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - last_comment_dt
            if delta.total_seconds() < uncommented_for * 60:
                continue

        student_submission_dir = os.path.join(submission_dir, student_id)
        os.makedirs(student_submission_dir, exist_ok=True)

        metapath = os.path.join(student_submission_dir, "metadata.txt")
        with open(metapath, "w") as fd:
            print(f"""id={student_id}
name={student_name}
course={course.name}
assignment={assignment.name}
attempt={submission.attempt}
late={submission.late}
date={submission.submitted_at}
last_comment={last_comment_date}""", file=fd)

        # Save the last comment (any comment, not just codeval ones) to last-comment.txt
        if submission.submission_comments:
            all_comments = sorted(submission.submission_comments, key=lambda c: c['created_at'])
            last_comment = all_comments[-1]
            last_comment_path = os.path.join(student_submission_dir, "last-comment.txt")
            with open(last_comment_path, "w") as fd:
                print(f"date={last_comment['created_at']}", file=fd)
                print(f"author={last_comment.get('author_name', 'unknown')}", file=fd)
                print("", file=fd)
                print(last_comment.get('comment', ''), file=fd)

        body = submission.body
        if body:
            filepath = os.path.join(student_submission_dir, "content.txt")
            with open(filepath, "w") as fd:
                fd.write(body)
            debug(f"Downloaded content for student {student_id} to {filepath}")

        if hasattr(submission, "attachments"):
            for attachment in submission.attachments:
                fname = attachment.filename
                filepath = os.path.join(student_submission_dir, fname)
                attachment.download(filepath)

            debug(f"Downloaded submission for student {student_id} to {filepath}")

    return submission_dir


@cache
def get_submissions_by_id(assignment):
    submissions_by_id = {}
    for submission in assignment.get_submissions(include=["user"]):
        student_id = str(submission.user_id)
        submissions_by_id[student_id] = submission
    return submissions_by_id


@click.command()
@click.argument("course_name", metavar="COURSE", required=False)
def list_codeval_assignments(course_name):
    """
    List all assignments that have corresponding codeval files.

    Optionally filter by COURSE (partial name match).
    Reports errors for codeval files that don't match any assignment.
    """
    # Load codeval directory from config
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    if 'CODEVAL' not in parser or 'directory' not in parser['CODEVAL']:
        raise click.UsageError(f"[CODEVAL] section with directory= is required in {config_file}")
    codeval_dir = parser['CODEVAL']['directory']

    if not os.path.isdir(codeval_dir):
        raise click.UsageError(f"CODEVAL directory does not exist: {codeval_dir}")

    # Get all codeval files in the directory
    codeval_files = {f[:-8] for f in os.listdir(codeval_dir) if f.endswith('.codeval')}
    matched_codeval_files = set()

    (canvas, user) = connect_to_canvas()
    courses = get_courses(canvas, course_name or "", is_active=True)
    if not courses:
        error("no active courses found")
        return

    for course in courses:
        for assignment in course.get_assignments():
            assignment_key = despace(assignment.name)
            if assignment_key in codeval_files:
                matched_codeval_files.add(assignment_key)
                info(f"{course.name}: {assignment.name}")

    # Report codeval files that don't match any assignment
    unmatched = codeval_files - matched_codeval_files
    for codeval_name in sorted(unmatched):
        error(f"codeval file has no matching assignment: {codeval_name}.codeval")
