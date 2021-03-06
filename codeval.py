from canvasapi import Canvas
from configparser import ConfigParser
from distutils.dir_util import copy_tree
import click
import datetime
import os, shutil, sys
import requests
import zipfile
import subprocess
import tempfile
import time
import traceback


show_debug = False

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def debug(message):
    if show_debug:
        click.echo(click.style(f"{_now()} D {message}", fg='magenta'))

def error(message, exit=False):
    click.echo(click.style(f"{_now()} E {message}", fg='red'))
    if exit: exit(2)
    raise EnvironmentError(message)


def info(message):
    click.echo(click.style(f"{_now()} I {message}", fg='blue'))


def warn(message):
    click.echo(click.style(f"{_now()} W {message}", fg='yellow'))


class CanvasHandler:
    def __init__(self):
        self.parser = ConfigParser()
        config_file = click.get_app_dir("codeval.ini")
        self.parser.read(config_file)
        self.parser.config_file = config_file

        for key in ['url', 'token']:
            self._check_config('SERVER', key) 
        for key in ['command']:
            self._check_config('RUN', key) 
        try:
            self.canvas = Canvas(self.parser['SERVER']['url'], self.parser['SERVER']['token'])
            user = self.canvas.get_current_user()
            info(f"connected to canvas as {user.name} ({user.id})")
        except:
            error(f"there was a problem accessing canvas.")
        self.executable = None

    def _check_config(self, section, key):
        if section not in self.parser:
            error(f"did not find [{section}] section in {self.config_file}.")
            sys.exit(1)
        if key not in self.parser[section]:
            error(f"did not find {key} in [{section}] in {self.config_file}.")
            sys.exit(1)

    def get_course(self, name, is_active=True):
        ''' find one course based on partial match '''
        course_list = self.get_courses(name, is_active)
        if len(course_list) == 0:
            error(f'no courses found that contain {name}. options are:')
            for c in self.get_courses("", is_active):
                error(fr"    {c.name}")
            sys.exit(2)
        elif len(course_list) > 1:
            error(f"multiple courses found for {name}: {[c.name for c in course_list]}")
            for c in course_list:
                error(f"    {c.name}")
            sys.exit(2)
        return course_list[0]

    def get_courses(self, name: str, is_active=True, is_finished=False):
        ''' find the courses based on partial match '''
        courses = self.canvas.get_courses(enrollment_type="teacher")
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

    @staticmethod
    def get_assignments(course):
        all_assignments = course.get_assignments()
        for assignment in all_assignments:
            if assignment.name.startswith("[CE]"):
                debug(f'grading {assignment.name}')
                yield assignment
            else:
                debug(f'skipping {assignment.name} (no [CE])')


    def download_attachment(self, directory, a):
        curPath = os.getcwd()
        os.chdir(os.path.join(curPath, directory))

        fname = a['display_name']
        prefix = os.path.splitext(fname)[0]
        suffix = os.path.splitext(fname)[1]
        durl = a['url']
        with requests.get(durl) as response:
            if response.status_code != 200:
                error(f'error {response.status_code} fetching {durl}')
            with open(f"{prefix}{suffix}", "wb") as fd:
                for chunk in response.iter_content():
                    fd.write(chunk)

        os.chdir(curPath)
        return os.path.join(directory, fname)

    def get_valid_test_file(self, course_name, assignment_name, dest_dir):
        '''download testcase file and extra files required for evaluate.sh to run'''
        debug(f'getting {assignment_name} from {course_name}')
        testcase_path = self.get_file(course_name, assignment_name + ".txt", f"{dest_dir}/testcases.txt")
        if not testcase_path:
            error(f"Cannot process assignment - {assignment_name} as the testcase file doesn't exist.")
        debug(f"testcase file downloaded at {testcase_path}")
        with open(testcase_path, "r") as f:
            self.executable = None
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line_args = line.split(" ")
                if line_args[0] == "Z":
                    file_name = "".join(line_args[1:])
                    debug(f'downloading {file_name}')
                    extra_files = self.get_file(course_name, file_name, f"{dest_dir}/extrafiles.zip")
                    unzip(extra_files, dest_dir,  delete=True)
                    debug(f'unzipped {file_name}')

                elif line_args[0] == "USING":
                    file_name = line_args[1]
                    if file_name not in os.listdir(dest_dir):
                        error(f"{file_name} not found in the {dest_dir} directory")
                    else:
                        self.executable = file_name
                        debug(f"main executable set to {file_name}. this will replace execute.sh in the config command.")

    def should_check_submission(self, submission):
        '''check whether a submission needs to be evaluated'''
        comments = submission.submission_comments
        if comments:
            # if submission is after comment, we need to check again
            for comment in comments[::-1]:
                if comment['comment'].startswith('[AG]') and comment['created_at'] > submission.submitted_at:
                    return False
        return True

    def grade_submissions(self, course_name, dry_run, force):
        course = self.get_course(course_name)
        for assignment in self.get_assignments(course):
            with tempfile.TemporaryDirectory(prefix="codeval", suffix="fixed") as temp_fixed:
                try:
                    self.get_valid_test_file(course_name, assignment.name, temp_fixed)
                    for submission in assignment.get_submissions(include=["submission_comments", "user"]):
                        if hasattr(submission, 'attachments') and (
                                force or self.should_check_submission(submission)):
                            with tempfile.TemporaryDirectory(prefix="codeval", suffix="submission") as tmpdir:
                                debug(f"tmpdir is {tmpdir}")
                                message = 'problem grading assignment'
                                try:
                                    debug(f"checking submission by user {submission.user['name']}.")
                                    self.download_submission_attachments(submission, tmpdir)
                                    copy_tree(temp_fixed, tmpdir)
                                    shutil.copy("evaluate.sh", f"{tmpdir}/evaluate.sh")
                                    shutil.copy("runvalgrind.sh", f"{tmpdir}/runvalgrind.sh")

                                    output = self.evaluate(tmpdir)
                                    message = output.decode();
                                except Exception as e:
                                    traceback.print_exc()
                                    message = str(e)
                                    info(f"Could not evaluate submission {submission.id} due to error: {e}")

                                if dry_run:
                                    info(f"would have said {message} to {submission.user['name']}")
                                else:
                                    debug(f"said {message} to {submission.user['name']}")
                                    submission.edit(comment={'text_comment': f'[AG]\n{message}'})

                except Exception as e:
                    warn(f"Could not process {assignment.name} due to error. skipping assignment: {e}")

    def download_submission_attachments(self, submission, submission_dir):
        for attachment in submission.attachments:
            attachment_path = self.download_attachment(submission_dir, attachment)
            unzip(attachment_path, submission_dir, delete=True)

    def get_file(self, course_name, file_name, outpath=""):
        '''get file from the course in canvas'''
        course = self.get_course(course_name)
        files = course.get_files()
        filtered_files = [file for file in files if file_name == file.display_name]
        if not file_name:
            error("No file name was given.")
        if len(filtered_files) == 0:
            error(f"{file_name} file not found in canvas.")
        if len(filtered_files) > 1:
            error(f"Multiple files found matching {file_name}.")
        file = course.get_file(filtered_files[0].id)
        filepath = outpath if outpath else file.display_name
        file.download(filepath)
        debug(f"{file_name} downloaded at {filepath}.")
        return filepath

    def evaluate(self, tmpdir):
        ''' run commands specified in codeval.ini'''
        command = self.parser["RUN"]["command"]
        if not command:
            error(f"commands section under [RUN] in {config_file} is empty")

        if "precommand" in self.parser['RUN']:
            precommand = self.parser["RUN"]["precommand"]
            debug(f"running precommand - {precommand}")
            p = subprocess.Popen(precommand, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate(timeout=20)
            debug(f"precommand result - {out}")
            if err:
                error(err)

        debug(f"command before {command}")
        if self.executable:
            command = command.replace("EVALUATE", self.executable)
        else:
            command = command.replace("EVALUATE", "./evaluate.sh")

        command = command.replace("SUBMISSIONS", tmpdir)
        debug(f"command after {command}")
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try: 
            out, err = p.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            out += b"\nTOOK LONGER THAN 20 seconds to run. FAILED\n"
        return out


def unzip(filepath, dir, delete=False):
    with zipfile.ZipFile(filepath) as file:
        for zi in file.infolist():
            file.extract(zi.filename, path=dir)
            debug(f"extracting {zi.filename}")
            fname = os.path.join(dir, zi.filename)
            s = os.stat(fname)
            # the user executable bit is set
            perms = (s.st_mode | (zi.external_attr >> 16)) & 0o777
            os.chmod(fname, perms)

        debug(f"{filepath} extracted to {dir}.")
    if delete:
        os.remove(filepath)
        debug(f"{filepath} deleted.")


@click.command("codeval")
@click.argument("course_name")
@click.option("--dry-run/--no-dry-run", default=True, show_default=True,
              help="Grade submissions but don't update canvas")
@click.option("--verbose/--no-verbose", default=False, show_default=True,
              help="Verbose actions")
@click.option("--force/--no-force", default=False, show_default=True,
              help="Grade submissions even if already graded")
def grade_course_submissions(course_name, dry_run, verbose, force):
    """
    Grade unsubmitted graded submission in the given course.
    """
    if dry_run:
        warn("This is a dry run. No updates to canvas will be made.")

    canvasHandler = CanvasHandler()
    global show_debug
    show_debug = verbose
    canvasHandler.grade_submissions(course_name, dry_run, force)


if __name__ == "__main__":
    grade_course_submissions()
