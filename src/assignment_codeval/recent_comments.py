"""List recent codeval comments on Canvas submissions."""

import os
import re
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone

import click

from assignment_codeval.canvas_utils import connect_to_canvas, get_course, get_courses
from assignment_codeval.commons import despace


def format_comment_preview(comment: str, prefix: str) -> str:
    """Format a comment showing first 3 and last 3 lines.

    Arguments:
        comment: The full comment text
        prefix: The codeval prefix to strip

    Returns:
        Formatted preview string
    """
    # Strip the prefix
    text = comment[len(prefix):] if comment.startswith(prefix) else comment
    lines = text.strip().split('\n')

    if len(lines) <= 6:
        return '\n'.join(f"    {line}" for line in lines)

    first_lines = lines[:3]
    last_lines = lines[-3:]
    result = []
    for line in first_lines:
        result.append(f"    {line}")
    result.append(f"    ... ({len(lines) - 6} more lines) ...")
    for line in last_lines:
        result.append(f"    {line}")
    return '\n'.join(result)


def format_local_time(dt: datetime) -> str:
    """Format a datetime in local timezone.

    Arguments:
        dt: datetime object (should be timezone-aware)

    Returns:
        Formatted string in local timezone
    """
    local_dt = dt.astimezone()
    return local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')


def parse_time_period(value: str) -> timedelta:
    """Parse a time period string like '30m', '2h', '1d', '1w' into a timedelta.

    Arguments:
        value: Time period string (e.g., '30m', '2h', '1d', '1w')

    Returns:
        timedelta representing the time period

    Raises:
        click.BadParameter: If the format is invalid
    """
    match = re.match(r'^(\d+)([mhdw])$', value.lower())
    if not match:
        raise click.BadParameter(
            f"Invalid time period '{value}'. Use format like '30m', '2h', '1d', '1w'"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == 'm':
        return timedelta(minutes=amount)
    elif unit == 'h':
        return timedelta(hours=amount)
    elif unit == 'd':
        return timedelta(days=amount)
    elif unit == 'w':
        return timedelta(weeks=amount)


@click.command()
@click.argument("course_name", metavar="COURSE", required=False)
@click.option("--active", is_flag=True, help="Show comments from all active courses")
@click.option("--time-period", default="1h", show_default=True,
              help="Time period to look back (e.g., 30m, 2h, 1d, 1w)")
@click.option("--codeval-prefix", default="codeval: ", show_default=True,
              help="Prefix used to identify codeval comments")
@click.option("--verbose", "-v", is_flag=True, help="Show which courses and assignments are being checked")
@click.option("--show-uncommented", is_flag=True,
              help="Also show submissions newer than their last codeval comment")
def recent_comments(course_name, active, time_period, codeval_prefix, verbose, show_uncommented):
    """
    List recent codeval comments on Canvas submissions.

    Shows all comments added by codeval within the specified time period.
    Use COURSE to filter to a specific course, or --active for all active courses.
    """
    if not active and not course_name:
        raise click.UsageError("COURSE is required unless --active is specified")

    (canvas, user) = connect_to_canvas()

    delta = parse_time_period(time_period)
    cutoff_time = datetime.now(timezone.utc) - delta

    # Load codeval directory from config if showing uncommented
    codeval_dir = None
    if show_uncommented:
        parser = ConfigParser()
        config_file = click.get_app_dir("codeval.ini")
        parser.read(config_file)
        if 'CODEVAL' in parser and 'directory' in parser['CODEVAL']:
            codeval_dir = parser['CODEVAL']['directory']
        else:
            click.echo("Warning: [CODEVAL] directory not configured, --show-uncommented may not filter by codeval assignments", err=True)

    if active:
        courses = get_courses(canvas, course_name or "", is_active=True)
        if not courses:
            click.echo("No active courses found")
            return
    else:
        courses = [get_course(canvas, course_name)]

    total_comments = 0
    total_uncommented = 0

    for course in courses:
        if verbose:
            click.echo(f"Checking course: {course.name}", err=True)
        for assignment in course.get_assignments():
            if verbose:
                click.echo(f"  Checking assignment: {assignment.name}", err=True)

            # Check if this assignment has a codeval file
            has_codeval = True
            if codeval_dir:
                codeval_file = os.path.join(codeval_dir, f"{despace(assignment.name)}.codeval")
                has_codeval = os.path.exists(codeval_file)
                if not has_codeval:
                    if verbose:
                        click.echo(f"    (no codeval file)", err=True)
                    continue

            assignment_comments = []
            uncommented_submissions = []

            for submission in assignment.get_submissions(include=["submission_comments", "user"]):
                student_name = submission.user.get('name', 'Unknown') if submission.user else 'Unknown'

                # Find codeval comments
                codeval_comments = []
                if submission.submission_comments:
                    for comment in submission.submission_comments:
                        comment_text = comment.get('comment', '')
                        if not comment_text.startswith(codeval_prefix):
                            continue

                        created_at_str = comment.get('created_at', '')
                        if not created_at_str:
                            continue

                        try:
                            created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue

                        codeval_comments.append({
                            'time': created_at,
                            'comment': comment_text
                        })

                        if created_at >= cutoff_time:
                            assignment_comments.append({
                                'student': student_name,
                                'time': created_at,
                                'comment': comment_text
                            })

                # Check for uncommented submissions
                if show_uncommented and has_codeval and submission.submitted_at:
                    try:
                        submitted_at = datetime.strptime(submission.submitted_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue

                    # Find the most recent codeval comment
                    last_codeval_time = None
                    if codeval_comments:
                        last_codeval_time = max(c['time'] for c in codeval_comments)

                    # Submission is uncommented if no codeval comment or submitted after last comment
                    if not last_codeval_time or submitted_at > last_codeval_time:
                        uncommented_submissions.append({
                            'student': student_name,
                            'submitted': submitted_at,
                            'last_comment': last_codeval_time
                        })

            if assignment_comments:
                click.echo(f"\n{course.name}: {assignment.name}")
                click.echo("-" * 60)
                for c in sorted(assignment_comments, key=lambda x: x['time']):
                    time_str = format_local_time(c['time'])
                    click.echo(f"  {time_str} - {c['student']}:")
                    click.echo(format_comment_preview(c['comment'], codeval_prefix))
                    click.echo()
                    total_comments += 1

            if uncommented_submissions:
                if not assignment_comments:
                    click.echo(f"\n{course.name}: {assignment.name}")
                    click.echo("-" * 60)
                click.echo("  Uncommented submissions:")
                for s in sorted(uncommented_submissions, key=lambda x: x['submitted']):
                    time_str = format_local_time(s['submitted'])
                    click.echo(f"    {time_str} - {s['student']}")
                    total_uncommented += 1

    click.echo(f"\nTotal: {total_comments} comments in the last {time_period}")
    if show_uncommented:
        click.echo(f"Total: {total_uncommented} uncommented submissions")
