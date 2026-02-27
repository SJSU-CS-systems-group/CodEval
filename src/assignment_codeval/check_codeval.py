"""Check which submissions are missing a codeval comment newer than the submission."""

import sys
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from math import floor

import click
import requests

from assignment_codeval.canvas_utils import connect_to_canvas, get_course
from assignment_codeval.commons import debug, error

ASSIGNMENTS_QUERY = """
query AssignmentsQuery($courseId: ID!) {
  course(id: $courseId) {
    assignmentGroupsConnection {
      nodes {
        name
        assignmentsConnection {
          nodes {
            _id
            name
          }
        }
      }
    }
  }
}
"""

SUBMISSIONS_QUERY = """
query SubmissionsQuery($assignmentId: ID!, $cursor: String) {
  assignment(id: $assignmentId) {
    submissionsConnection(after: $cursor) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        _id
        submittedAt
        user {
          name
        }
        commentsConnection(filter: {allComments: true}) {
          nodes {
            comment
            createdAt
          }
        }
      }
    }
  }
}
"""


def _get_canvas_credentials():
    """Read raw url and token from codeval.ini config file."""
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    if 'SERVER' not in parser:
        error(f"did not find [SERVER] section in {config_file}.")
        sys.exit(1)
    for key in ['url', 'token']:
        if key not in parser['SERVER']:
            error(f"did not find {key} in [SERVER] in {config_file}.")
            sys.exit(1)
    return parser['SERVER']['url'], parser['SERVER']['token']


def _graphql_request(base_url, token, query, variables):
    """POST a GraphQL query to Canvas and return the data."""
    url = f"{base_url}/api/graphql"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query, "variables": variables}
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    result = resp.json()
    if "errors" in result:
        error(f"GraphQL errors: {result['errors']}")
        sys.exit(1)
    return result["data"]


def _fetch_all_submissions(base_url, token, assignment_id):
    """Fetch all submissions for an assignment using relay pagination."""
    all_nodes = []
    cursor = None
    while True:
        variables = {"assignmentId": str(assignment_id)}
        if cursor:
            variables["cursor"] = cursor
        data = _graphql_request(base_url, token, SUBMISSIONS_QUERY, variables)
        conn = data["assignment"]["submissionsConnection"]
        all_nodes.extend(conn["nodes"])
        if conn["pageInfo"]["hasNextPage"]:
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return all_nodes


def _format_elapsed(submitted_at_str):
    """Format elapsed time since submission as a human-readable string."""
    submitted = datetime.fromisoformat(submitted_at_str)
    delta = datetime.now(timezone.utc) - submitted
    total_minutes = floor(delta.total_seconds() / 60)
    if total_minutes < 60:
        return f"{total_minutes}m"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days = hours // 24
    hours = hours % 24
    if hours:
        return f"{days}d {hours}h"
    return f"{days}d"


def _has_codeval_comment_after_submission(submission_node, codeval_prefix):
    """Check if a submission has a codeval comment newer than the submission.

    Returns True if the submission doesn't need evaluation (either not submitted,
    or has a codeval comment after the submission time).
    """
    submitted_at = submission_node.get("submittedAt")
    if submitted_at is None:
        return True

    comments = submission_node.get("commentsConnection", {}).get("nodes", [])
    for comment in comments:
        text = comment.get("comment", "")
        if not text.startswith(codeval_prefix):
            continue
        created_at = comment.get("createdAt")
        if created_at and created_at > submitted_at:
            return True
    return False


@click.command()
@click.argument("course_name", metavar="COURSE")
@click.option("--assignment-group", default="Assignments", show_default=True,
              help="Name of the assignment group to check")
@click.option("--codeval-prefix", default="codeval: ", show_default=True,
              help="Prefix used to identify codeval comments")
@click.option("--verbose", "-v", is_flag=True, help="Show all submissions, not just missing ones")
@click.option("--warn", "-w", is_flag=True, help="Show warnings for recent submissions awaiting comments")
@click.option("--max-comment-delay", default=30, show_default=True,
              help="Minutes to allow before flagging a missing comment as an error")
def check_codeval(course_name, assignment_group, codeval_prefix, verbose, warn, max_comment_delay):
    """Check which submissions are missing a codeval comment.

    Shows submissions that have not been evaluated by codeval, or where
    the submission is newer than the most recent codeval comment.
    """
    (canvas, user) = connect_to_canvas()
    course = get_course(canvas, course_name)
    base_url, token = _get_canvas_credentials()

    debug(f"fetching assignment groups for course {course.name} (id={course.id})")
    data = _graphql_request(base_url, token, ASSIGNMENTS_QUERY, {"courseId": str(course.id)})

    groups = data["course"]["assignmentGroupsConnection"]["nodes"]
    target_group = None
    for group in groups:
        if group["name"] == assignment_group:
            target_group = group
            break

    if target_group is None:
        available = [g["name"] for g in groups]
        error(f"assignment group '{assignment_group}' not found. available: {available}")
        sys.exit(1)

    assignments = target_group["assignmentsConnection"]["nodes"]
    if not assignments:
        click.echo(f"no assignments found in group '{assignment_group}'")
        return

    total_missing = 0
    total_warned = 0
    total_checked = 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_comment_delay)

    for assignment in assignments:
        assignment_id = assignment["_id"]
        assignment_name = assignment["name"]
        debug(f"checking assignment: {assignment_name}")

        submissions = _fetch_all_submissions(base_url, token, assignment_id)

        missing = []
        warned = []
        checked = 0
        for sub in submissions:
            submitted_at_str = sub.get("submittedAt")
            if submitted_at_str is None:
                continue
            checked += 1
            student_name = sub.get("user", {}).get("name", "Unknown")
            has_comment = _has_codeval_comment_after_submission(sub, codeval_prefix)
            if has_comment:
                if verbose:
                    click.echo(f"  \u2705 {student_name}")
            else:
                elapsed = _format_elapsed(submitted_at_str)
                label = f"{student_name} ({elapsed})"
                recent = datetime.fromisoformat(submitted_at_str) >= cutoff
                if recent:
                    warned.append(label)
                    if verbose or warn:
                        click.echo(f"  \u26a0\ufe0f {label}")
                else:
                    missing.append(label)
                    if verbose:
                        click.echo(click.style(f"  \u2717 {label}", fg='red'))

        total_checked += checked
        total_missing += len(missing)
        total_warned += len(warned)

        if missing or warned or verbose:
            parts = [f"{len(missing)}/{checked} missing codeval"]
            click.echo(f"\n{assignment_name}: {', '.join(parts)}")

        if not verbose and missing:
            for label in missing:
                click.echo(click.style(f"  \u2717 {label}", fg='red'))

    if total_missing:
        sys.exit(2)

