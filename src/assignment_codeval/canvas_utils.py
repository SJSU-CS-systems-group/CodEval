import datetime
import sys
from configparser import ConfigParser
from functools import cache
from typing import NamedTuple

import click
import requests
from canvasapi import Canvas
from canvasapi.current_user import CurrentUser

from assignment_codeval.commons import error, info, errorWithException, despace

CanvasConnection = NamedTuple('CanvasConnection', [('canvas', Canvas), ('user', CurrentUser)])


def _check_config(parser, section, key):
    if section not in parser:
        error(f"did not find [{section}] section in {parser.config_file}.")
        sys.exit(1)
    if key not in parser[section]:
        error(f"did not find {key} in [{section}] in {parser.config_file}.")
        sys.exit(1)


def connect_to_canvas():
    parser = ConfigParser()
    config_file = click.get_app_dir("codeval.ini")
    parser.read(config_file)
    parser.config_file = config_file

    for key in ['url', 'token']:
        _check_config(parser, 'SERVER', key)
    try:
        canvas = Canvas(parser['SERVER']['url'], parser['SERVER']['token'])
        user = canvas.get_current_user()
        info(f"connected to canvas as {user.name} ({user.id})")
        return CanvasConnection(canvas, user)
    except:
        errorWithException(f"there was a problem accessing canvas.")


@cache
def get_course(canvas, name, is_active=True):
    ''' find one course based on partial match '''
    course_list = get_courses(canvas, name, is_active)
    if len(course_list) == 0:
        error(f'no courses found that contain {name}. options are:')
        for c in get_courses(canvas, "", is_active):
            error(fr"    {c.name}")
        sys.exit(2)
    elif len(course_list) > 1:
        error(f"multiple courses found for {name}: {[c.name for c in course_list]}")
        for c in course_list:
            error(f"    {c.name}")
        sys.exit(2)
    return course_list[0]


def is_teacher(course):
    if hasattr(course, "enrollments"):
        for e in course.enrollments:
            if 'role' not in e:
                continue
            type = e['role']
            if type == 'TeacherEnrollment' or type == 'TaEnrollment':
                return True
    return False


def get_courses(canvas, name: str, is_active=True, is_finished=False):
    ''' find the courses based on partial match '''
    name = despace(name)
    courses = [c for c in canvas.get_courses() if is_teacher(c)]
    now = datetime.datetime.now(datetime.timezone.utc)
    course_list = []
    for c in courses:
        start = c.start_at_date if hasattr(c, "start_at_date") else now
        end = c.end_at_date if hasattr(c, "end_at_date") else now
        if is_active and (start > now or end < now):
            continue
        if is_finished and end < now:
            continue
        if name in despace(c.name):
            c.start = start
            c.end = end
            course_list.append(c)
    return course_list


@cache
def get_assignment(course, assignment_name):
    assignment_name = despace(assignment_name)
    assignments = [a for a in course.get_assignments() if assignment_name.lower() in despace(a.name).lower()]
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


def get_canvas_credentials():
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


def graphql_request(base_url, token, query, variables):
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


def fetch_all_submissions(base_url, token, assignment_id):
    """Fetch all submissions for an assignment using relay pagination."""
    all_nodes = []
    cursor = None
    while True:
        variables = {"assignmentId": str(assignment_id)}
        if cursor:
            variables["cursor"] = cursor
        data = graphql_request(base_url, token, SUBMISSIONS_QUERY, variables)
        conn = data["assignment"]["submissionsConnection"]
        all_nodes.extend(conn["nodes"])
        if conn["pageInfo"]["hasNextPage"]:
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return all_nodes
