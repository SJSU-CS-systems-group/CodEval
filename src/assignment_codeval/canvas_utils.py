import datetime
import sys
from functools import cache
from typing import NamedTuple
from configparser import ConfigParser

import click
from canvasapi import Canvas
from canvasapi.current_user import CurrentUser

from assignment_codeval.commons import error, info, errorWithException

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


def get_courses(canvas, name: str, is_active=True, is_finished=False):
    ''' find the courses based on partial match '''
    courses = canvas.get_courses(enrollment_type="teacher")
    now = datetime.datetime.now(datetime.timezone.utc)
    course_list = []
    for c in courses:
        start = c.start_at_date if hasattr(c, "start_at_date") else now
        end = c.end_at_date if hasattr(c, "end_at_date") else now
        if is_active and (start > now or end < now):
            continue
        if is_finished and end < now:
            continue
        if name in c.name:
            c.start = start
            c.end = end
            course_list.append(c)
    return course_list
