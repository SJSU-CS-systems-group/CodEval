import os
import traceback
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import click

from assignment_codeval import convertMD2Html
from assignment_codeval.canvas_utils import connect_to_canvas, get_course
from assignment_codeval.commons import debug, errorWithException, info, get_config, set_config, error, warn

file_dict = {}
zip_files = []
canvas_folder = None


def get_codeval_folder(course):
    canvas_folders = course.get_folders()
    for folder in canvas_folders:
        if folder.name == "CodEval":
            return folder
    error("could not file CodEval folder")
    exit(2)


def upload_assignment_files(folder, files):
    global file_dict
    for file in files:
        if get_config().dry_run:
            info(f'would upload the {file}')
            file_dict[file] = f"http://bogus/{file}"
        else:
            try:
                file_spec = folder.upload(file)
            except Exception as e:
                traceback.print_exc()
                errorWithException(f'Error uploading the file {file} in CodEval folder due to error : {e}. Exiting!!')
            else:
                file_dict[file_spec[1]['filename']] = file_spec[1]['url']


def files_resolver(filename):
    global file_dict
    global canvas_folder
    global zip_files

    if filename in file_dict:
        return file_dict[filename]
    for z in zip_files:
        with ZipFile(z) as zf:
            matches = [f for f in zf.namelist() if os.path.basename(f) == filename]
            if not matches:
                warn(f"could not find {filename} in {z}")
            elif len(matches) > 1:
                warn("found multiple matches for {filename} in {z}: {matches}")
            if matches:
                zfname = matches[0]
                with TemporaryDirectory("ce") as tmpdir:
                    extracted_path = zf.extract(zfname, path=tmpdir)
                    upload_assignment_files(canvas_folder, [extracted_path])
                    return file_dict[filename]
    else:
        return f"FILE[{filename}]"


@click.command()
@click.argument("course_name")
@click.argument("specname")
@click.argument("extra", nargs=-1)
@click.option("--dryrun/--no-dryrun", default=True, show_default=True,
              help="Create assignment but don't update Canvas.")
@click.option("--verbose/--no-verbose", default=False, show_default=True, help="Verbose actions")
@click.option("--group_name", default="Assignments", show_default=True,
              help="Group name in which assignments needs to be created.")
def create_assignment(dryrun, verbose, course_name, group_name, specname, extra):
    """
        Create the assignment in the given course.
    """
    global canvas_folder
    global zip_files
    set_config(verbose, dryrun, False, False)
    if not os.path.isfile(specname):
        errorWithException(f'The specification file:{specname} does not exist in the CodEval folder. Exiting!!')

    (canvas, user) = connect_to_canvas()

    try:
        course = get_course(canvas, course_name)
    except Exception as e:
        errorWithException(f'get_course api failed with following error : {e}')
    else:
        debug(f'Successfully retrieved the course: {course_name}')
    canvas_folder = get_codeval_folder(course)
    if extra:
        upload_assignment_files(canvas_folder, extra)
    # find zipfiles in spec
    with open(specname) as f:
        for line in f:
            if line.startswith("Z "):
                zipfile = line[2:].strip()
                if zipfile not in zip_files:
                    zip_files.append(zipfile)

    debug(f'Successfully uploaded the files in the CodEval folder')
    try:
        (assign_name, html) = convertMD2Html.mdToHtml(specname, files_resolver)
    except Exception as e:
        traceback.print_exc()
        errorWithException(f'Error in convertMD2Html::mdToHtml function')
    else:
        debug(f'Successfully converted the assignment description to HTML')

    grp_name = None
    for assign_group in course.get_assignment_groups():
        if assign_group.name == group_name:
            grp_name = assign_group
            debug(f'The group id is: {grp_name.id}')
    if grp_name is None:
        errorWithException(f'The group name : {group_name} does not exist. Exiting!')

    canvas_assignments = course.get_assignments()
    debug(f'Successfully got all the assignments from the desired course')
    canvas_assign_names = [assign.name for assign in canvas_assignments]
    if assign_name in canvas_assign_names:
        for assignment in canvas_assignments:
            if assignment.name == assign_name:
                if dryrun:
                    info(f"would update {assign_name}.")
                else:
                    for discussion in course.get_discussion_topics():
                        if discussion.title == assign_name:
                            disUrlHtml = f'<a href={discussion.html_url}>{discussion.title}</a>'
                    try:
                        assignment.edit(assignment={'name': assign_name, 'assignment_group_id': grp_name.id,
                                                    'description': html.replace("DISCUSSION_LINK", disUrlHtml),
                                                    'points_possible': 100, 'allowed_extensions': ["zip"], })
                    except Exception as e:
                        traceback.print_exc()
                        errorWithException(f'Editing assignment {assign_name} failed with the exception : {e}')
                    else:
                        info(f'Successfully edited assignment {assign_name}')

    else:
        if dryrun:
            info(f"would create {assign_name}")
        else:
            try:
                # Create the discussion Topic
                dis_topic = course.create_discussion_topic(title=assign_name, message="")
                debug(f'Created Discussion Topic: {assign_name}')
                # get the url of the discussion topic
                disUrlHtml = f'<a href={dis_topic.html_url}>{dis_topic.title}</a>'
                # Create the assignment with the assign_name
                created_assignment = course.create_assignment({'name': assign_name, 'assignment_group_id': grp_name.id,
                                                               'description': html.replace("DISCUSSION_LINK",
                                                                                           disUrlHtml),
                                                               'points_possible': 100, 'published': False,
                                                               'submission_types': ["online_upload"],
                                                               'allowed_extensions': ["zip"], })
                debug(f'Created new assignment: {assign_name}')
                # Update the discussion topic with the assignment link
                dis_topic.update(
                    message=f'This Discussion is for Assignment <a href={created_assignment.html_url}>{assign_name}</a>', )
                debug(f'Updated the Discussion Topic by linking it with the corresponding assignment: {assign_name}')
            except Exception as e:
                traceback.print_exc()
                errorWithException(f'Creating Discussion topic and assignment failed due to the exception: {e}')
            else:
                info(f'Successfully created assignment and Discussion Topic {assign_name}')
