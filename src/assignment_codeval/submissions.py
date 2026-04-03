import os
import re
import shutil
import subprocess
import time
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import cache
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import click
import requests

from assignment_codeval.canvas_utils import connect_to_canvas, get_course, get_courses, get_assignment
from assignment_codeval.commons import debug, error, info, warn, despace


def _extract_codeval_title(filepath):
    """Extract the assignment title from the CRT_HW START line of a codeval file.
    Returns None if no CRT_HW START line is found."""
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if 'CRT_HW START' in line:
                    idx = line.index('CRT_HW START') + len('CRT_HW START')
                    title = line[idx:].strip()
                    return title if title else None
    except (OSError, UnicodeDecodeError):
        pass
    return None


def find_codeval_file(codeval_dir, assignment_name):
    """Find a codeval file by assignment name, case-insensitive.
    First tries matching by filename, then falls back to checking
    CRT_HW START titles inside each .codeval file.
    Returns the full path if found, or None if not found."""
    target = f"{assignment_name}.codeval".lower()
    codeval_files = []
    for f in os.listdir(codeval_dir):
        if f.lower() == target:
            return os.path.join(codeval_dir, f)
        if f.endswith('.codeval'):
            codeval_files.append(f)

    # Fallback: check CRT_HW START titles
    target_name = assignment_name.lower()
    for f in codeval_files:
        filepath = os.path.join(codeval_dir, f)
        title = _extract_codeval_title(filepath)
        if title and despace(title).lower() == target_name:
            return filepath
    return None


def get_github_repo_url(course, user_id, config_parser, github_field="github"):
    """
    Get the GitHub repo URL for a user in a course.

    Returns the repo URL string if found, or None if GitHub is not configured
    for this course or the user doesn't have a GitHub link in their profile.
    """
    gh_key = course.name.replace(":", "").replace("=", "")
    if 'GITHUB' not in config_parser or gh_key not in config_parser['GITHUB']:
        return None

    gh_repo_prefix = config_parser['GITHUB'][gh_key]

    try:
        user = course.get_user(user_id)
        profile = user.get_profile(include=["links", "link"])
        if 'links' not in profile:
            debug(f"user {user_id}: no links in canvas profile")
            return None
        link_titles = [m['title'] for m in profile['links']]
        gh_links = [m['url'] for m in profile['links'] if m['title'].lower() == github_field.lower()]
        if len(gh_links) == 0:
            debug(f"user {user_id}: no '{github_field}' link found, available: {link_titles}")
            return None
        if len(gh_links) > 1:
            debug(f"user {user_id}: multiple '{github_field}' links in canvas profile")
            return None
        gh_url = gh_links[0]
        gh_id = gh_url.rstrip('/').rsplit('/', 1)[-1]
        return f"{gh_repo_prefix}-{gh_id}.git"
    except Exception as e:
        warn(f"user {user_id}: error getting github repo: {e}")
        return None


def _get_canvas_config():
    """Get Canvas URL and token from config."""
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    return parser['SERVER']['url'].rstrip('/'), parser['SERVER']['token']


def write_html_file(dirpath):
    import html as _html

    assignment_name = student_name = attempt_no = last_submitted = ""
    with open(f"{dirpath}/metadata.txt", "r") as f:
        for line in f:
            if line.startswith("assignment="):
                assignment_name = line.strip().split("=", 1)[1]
            elif line.startswith("name="):
                student_name = line.strip().split("=", 1)[1]
            elif line.startswith("attempt="):
                attempt_no = line.strip().split("=", 1)[1]
            elif line.startswith("date="):
                last_submitted = line.strip().split("=", 1)[1]

    with open(f"{dirpath}/comments.txt", "r") as f:
        comments_content = f.read()

    # Color each line based on PASS/FAIL/error keywords
    def colorize_lines(text):
        lines_html = []
        for line in text.split('\n'):
            escaped = _html.escape(line)
            if line.startswith('PASS'):
                lines_html.append(f'<span class="pass">{escaped}</span>')
            elif line.startswith('FAIL'):
                lines_html.append(f'<span class="fail">{escaped}</span>')
            elif any(line.startswith(k) for k in ('ERROR', 'TOOK LONGER', 'FAILED')):
                lines_html.append(f'<span class="error">{escaped}</span>')
            else:
                lines_html.append(escaped)
        return '\n'.join(lines_html)

    try:
        dt = datetime.strptime(last_submitted, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        dt = dt.astimezone(ZoneInfo('America/Los_Angeles'))
        last_submitted = dt.strftime('%B %d, %Y at %I:%M %p %Z')
    except (ValueError, TypeError):
        pass

    pass_count = sum(1 for l in comments_content.split('\n') if l.startswith('PASS'))
    fail_count = sum(1 for l in comments_content.split('\n') if l.startswith('FAIL'))

    template_path = os.path.join(os.path.dirname(__file__), 'test_template.html')
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    html_content = (html_content
        .replace('{{ASSIGNMENT_NAME}}', _html.escape(assignment_name))
        .replace('{{STUDENT_NAME}}', _html.escape(student_name))
        .replace('{{SUBMITTED}}', _html.escape(last_submitted))
        .replace('{{ATTEMPT}}', _html.escape(attempt_no))
        .replace('{{PASS_COUNT}}', str(pass_count))
        .replace('{{FAIL_COUNT}}', str(fail_count))
        .replace('{{OUTPUT}}', colorize_lines(comments_content))
    )

    with open(f"{dirpath}/results.html", "w", encoding="utf-8") as dst:
        dst.write(html_content)


def upload_file_for_comment(canvas, course_id, assignment_id, user_id, file_path):
    """
    Upload a file to attach to a submission comment.
    Returns the file_id to use when creating/editing the comment.
    """
    canvas_url, canvas_token = _get_canvas_config()
    auth = {'Authorization': f'Bearer {canvas_token}'}

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Step 1: Request upload URL
    r1 = requests.post(
        f'{canvas_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}/comments/files',
        headers=auth,
        data={'name': file_name, 'size': file_size, 'content_type': 'text/html'}
    )
    r1.raise_for_status()
    upload_info = r1.json()

    # Step 2: Upload file to storage
    with open(file_path, 'rb') as f:
        r2 = requests.post(
            upload_info['upload_url'],
            data=upload_info['upload_params'],
            files={'file': (file_name, f, 'text/html')},
            allow_redirects=False
        )

    # Step 3: Confirm upload
    if r2.status_code in (301, 302, 303):
        r3 = requests.get(r2.headers['Location'], headers=auth)
        r3.raise_for_status()
        return r3.json()['id']
    else:
        r2.raise_for_status()
        return r2.json()['id']


def delete_submission_comment(canvas, course_id, assignment_id, user_id, comment_id):
    """Delete a submission comment."""
    canvas_url, canvas_token = _get_canvas_config()
    resp = requests.delete(
        f'{canvas_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}/comments/{comment_id}',
        headers={'Authorization': f'Bearer {canvas_token}'}
    )
    resp.raise_for_status()


def _parse_substitutions_file(filepath):
    """Parse a substitutions file where each line has the form /pattern/replacement/.

    The first character of each line defines the delimiter. The delimiter must appear
    exactly once in-between (separating pattern from replacement) and once at the end.
    Returns a list of (pattern, replacement) tuples.
    Raises click.ClickException on parse errors.
    """
    substitutions = []
    with open(filepath, "r") as fd:
        for lineno, line in enumerate(fd, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            delim = line[0]
            parts = line[1:].split(delim)
            if len(parts) != 3 or parts[2] != "":
                raise click.ClickException(
                    f"{filepath}:{lineno}: invalid substitution line: {line}"
                )
            substitutions.append((parts[0], parts[1]))
    return substitutions


def _apply_substitutions(comment, substitutions):
    """Apply a list of (pattern, replacement) substitutions to comment text."""
    for pattern, replacement in substitutions:
        comment = comment.replace(pattern, replacement)
    return comment


@click.command()
@click.argument("submissions_dir", metavar="SUBMISSIONS_DIR")
@click.option("--codeval-prefix", help="prefix for codeval comments", default="codeval: ", show_default=True)
@click.option("--delete", is_flag=True, help="deletes the previous comment before uploading")
def upload_submission_comments(submissions_dir, codeval_prefix, delete):
    """
    Upload comments for submissions from a directory.

    the submissions_dir specifies a directory that has comments to upload stored as:

    COURSE/ASSIGNMENT/STUDENT_ID/comments.txt

    if the file comments.txt.sent exists, the comment has already been uploaded and will be skipped.
    """
    (canvas, user) = connect_to_canvas()
    clean_submissions_dir = submissions_dir.rstrip('/').replace('\\', '/')
    for dirpath, dirnames, filenames in os.walk(clean_submissions_dir):
        dirpath = dirpath.replace('\\', '/')
        match = re.match(fr'^{re.escape(clean_submissions_dir)}/([^/]+)/([^/]+)/([^/]+)$', dirpath)
        if match:
            course_name = match.group(1)
            assignment_name = match.group(2)
            student_id = match.group(3)
            if "comments.txt.sent" in filenames:
                info(f"skipping already uploaded comments for {student_id} in {course_name}: {assignment_name}")
            elif "comments.txt" in filenames:
                info(f"uploading comments for {student_id} in {course_name}: {assignment_name}")
                course = get_course(canvas, course_name)
                assignment = get_assignment(course, assignment_name)
                submission = get_submissions_by_id(assignment).get(student_id)
                if submission:
                    write_html_file(dirpath)
                    file_id = upload_file_for_comment(canvas, course.id, assignment.id, student_id, f"{dirpath}/results.html")
                    with open(f"{dirpath}/comments.txt", "rb") as fd:
                        # canvas max is 65000, so 32K will keep us well below that
                        comment_bytes = fd.read(32*1024).replace(b'\0', b'\\0').replace(b'<', b'&lt;')
                        comment = comment_bytes[:32*1024].decode('utf-8', errors='ignore')
                    subs_file = f"{dirpath}/SUBSTITUTIONS.txt"
                    if os.path.isfile(subs_file):
                        substitutions = _parse_substitutions_file(subs_file)
                        comment = _apply_substitutions(comment, substitutions)
                    if delete:
                        all_comments = sorted(submission.submission_comments, key=lambda c: c['created_at'])
                        if all_comments:
                            last_comment_id = all_comments[-1]["id"]
                            delete_submission_comment(canvas, course.id, assignment.id, student_id, last_comment_id)
                    canvas_url, canvas_token = _get_canvas_config()
                    requests.put(
                        f'{canvas_url}/api/v1/courses/{course.id}/assignments/{assignment.id}/submissions/{student_id}',
                        headers={'Authorization': f'Bearer {canvas_token}'},
                        data={
                            'comment[text_comment]': f'{codeval_prefix.rstrip()}\n<pre>{comment}</pre>',
                            'comment[file_ids][]': file_id,
                        }
                    ).raise_for_status()
                else:
                    warn(f"no submission found for {student_id} in {course_name}: {assignment_name}")
                with open(f"{dirpath}/comments.txt.sent", "w") as fd:
                    fd.write(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))


@click.command()
@click.argument('codeval_dir', metavar="CODEVAL_DIR", required=False)
@click.option("--submissions-dir", help="directory containing submissions COURSE/ASSIGNMENT/STUDENT_ID",
              default='./submissions', show_default=True)
def evaluate_submissions(codeval_dir, submissions_dir):
    """
    Evaluate submissions stored in the form COURSE/ASSIGNMENT/STUDENT_ID.

    CODEVAL_DIR specifies a directory that has the codeval files named after the assignment with the .codeval suffix.
    If not specified, uses the directory from [CODEVAL] section in codeval.ini.
    """
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    parser.config_file = config_file

    # Use codeval_dir from config if not specified
    if not codeval_dir:
        if 'CODEVAL' not in parser or 'directory' not in parser['CODEVAL']:
            raise click.UsageError(f"CODEVAL_DIR not specified and [CODEVAL] section with directory= not found in {config_file}")
        codeval_dir = parser['CODEVAL']['directory']

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

        codeval_file = find_codeval_file(codeval_dir, assignment_name)
        if not codeval_file:
            warn(f"no codeval file found for {assignment_name} in {codeval_dir}")
            continue

        # First pass: get CTO, CD tags, and collect Z files (don't extract yet)
        compile_timeout = 20
        assignment_working_dir = "."
        has_cd_tag = False
        zip_files = []
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
                    has_cd_tag = True
                    assignment_working_dir = os.path.normpath(
                        os.path.join(assignment_working_dir, line.split()[1].strip()))
                    if not os.path.isdir(os.path.join(submission_dir, assignment_working_dir)):
                        out = f"{assignment_working_dir} does not exist or is not a directory\n".encode('utf-8')
                        move_to_next_submission = True
                        break
                if line.startswith("Z"):
                    zip_files.append(line.split(None, 1)[1])

        # If no CD tag and this is a GitHub submission (has .git), use assignment name as working dir
        if not has_cd_tag and os.path.exists(os.path.join(submission_dir, ".git")):
            assignment_working_dir = assignment_name
            if not os.path.isdir(os.path.join(submission_dir, assignment_working_dir)):
                out = f"{assignment_working_dir} does not exist or is not a directory\n".encode('utf-8')
                move_to_next_submission = True

        # Now extract zip files to the correct working directory
        if not move_to_next_submission:
            for zf_name in zip_files:
                with ZipFile(os.path.join(codeval_dir, zf_name)) as zf:
                    if "SUBSTITUTIONS.txt" in zf.namelist():
                        with open(os.path.join(dirpath, "SUBSTITUTIONS.txt"), "wb") as out_f:
                            out_f.write(zf.read("SUBSTITUTIONS.txt"))
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
                codeval_file = find_codeval_file(codeval_dir, despace(assignment.name))
                if not codeval_file:
                    continue

                info(f"downloading submissions for {course.name}: {assignment.name}")
                _download_assignment_submissions(
                    canvas, course, assignment, target_dir, include_commented, codeval_prefix,
                    include_empty, uncommented_for, for_name
                )
        return

    course = get_course(canvas, course_name)
    assignment = get_assignment(course, assignment_name)
    _download_assignment_submissions(
        canvas, course, assignment, target_dir, include_commented, codeval_prefix,
        include_empty, uncommented_for, for_name
    )


def _download_assignment_submissions(canvas, course, assignment, target_dir, include_commented, codeval_prefix,
                                     include_empty, uncommented_for, for_name):
    """Download submissions for a single assignment."""
    submission_dir = os.path.join(target_dir, despace(course.name), despace(assignment.name))
    os.makedirs(submission_dir, exist_ok=True)

    # Load config for GitHub repo lookup
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)

    # Check if GitHub is configured for this course
    gh_key = course.name.replace(":", "").replace("=", "")
    if 'GITHUB' in parser and gh_key in parser['GITHUB']:
        info(f"GitHub configured for course (key: {gh_key}), users need 'github' link in Canvas profile")
    else:
        info(f"GitHub not configured (no '{gh_key}' in [GITHUB] section of {config_file})")

    for submission in assignment.get_submissions(include=["submission_comments", "user"]):
        if not submission.attempt and not include_empty:
            continue

        student_id = str(submission.user_id)
        student_name = submission.user['name']

        if for_name and for_name not in student_name:
            continue

        submission_comments = [c['created_at'] for c in submission.submission_comments if
                               'comment' in c and c['comment'].startswith(codeval_prefix.rstrip())]
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
        github_repo = get_github_repo_url(course, submission.user_id, parser)
        with open(metapath, "w") as fd:
            print(f"""id={student_id}
name={student_name}
course={course.name}
assignment={assignment.name}
attempt={submission.attempt}
late={submission.late}
date={submission.submitted_at}
last_comment={last_comment_date}
github_repo={github_repo or ''}""", file=fd)

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
    for submission in assignment.get_submissions(include=["submission_comments", "user"]):
        student_id = str(submission.user_id)
        submissions_by_id[student_id] = submission
    return submissions_by_id


@click.command()
@click.argument("course_name", metavar="COURSE", required=False)
@click.option("--path", is_flag=True, help="Show the path to the codeval file")
def list_codeval_assignments(course_name, path):
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

    # Get all codeval files in the directory (map lowercase name -> original name)
    codeval_files = {}
    codeval_titles = {}  # map despaced-lowercase CRT_HW title -> original filename stem
    for f in os.listdir(codeval_dir):
        if f.endswith('.codeval'):
            stem = f[:-8]
            codeval_files[stem.lower()] = stem
            title = _extract_codeval_title(os.path.join(codeval_dir, f))
            if title:
                codeval_titles[despace(title).lower()] = stem
    matched_codeval_keys = set()

    (canvas, user) = connect_to_canvas()
    courses = get_courses(canvas, course_name or "", is_active=True)
    if not courses:
        error("no active courses found")
        return

    for course in courses:
        for assignment in course.get_assignments():
            assignment_key = despace(assignment.name).lower()
            if assignment_key in codeval_files:
                matched_codeval_keys.add(assignment_key)
                codeval_path = os.path.join(codeval_dir, f"{codeval_files[assignment_key]}.codeval")
                if path:
                    info(f"{course.name}: {assignment.name} [{codeval_path}]")
                else:
                    info(f"{course.name}: {assignment.name}")
            elif assignment_key in codeval_titles:
                matched_codeval_keys.add(codeval_titles[assignment_key].lower())
                codeval_path = os.path.join(codeval_dir, f"{codeval_titles[assignment_key]}.codeval")
                if path:
                    info(f"{course.name}: {assignment.name} [{codeval_path}]")
                else:
                    info(f"{course.name}: {assignment.name}")

    # Report codeval files that don't match any assignment
    unmatched_keys = set(codeval_files.keys()) - matched_codeval_keys
    for key in sorted(unmatched_keys):
        error(f"codeval file has no matching assignment: {codeval_files[key]}.codeval")
