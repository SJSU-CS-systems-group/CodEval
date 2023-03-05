import os
import shutil
import sys
import subprocess
import requests
from distutils.dir_util import copy_tree
import zipfile
from commons import *

# TODO: rename this file to file_utils.py


def download_attachment(directory, attachment):
    curPath = os.getcwd()
    os.chdir(os.path.join(curPath, directory))

    fname = attachment['display_name']
    prefix = os.path.splitext(fname)[0]
    suffix = os.path.splitext(fname)[1]
    durl = attachment['url']
    with requests.get(durl) as response:
        if response.status_code != 200:
            error(f'error {response.status_code} fetching {durl}')
        with open(f"{prefix}{suffix}", "wb") as fd:
            for chunk in response.iter_content():
                fd.write(chunk)

    os.chdir(curPath)
    return os.path.join(directory, fname)


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


def set_acls(temp_dir):
    """Set ACLs for the temporary directory"""
    if sys.platform == 'darwin':
        subprocess.call(["chmod", "-R", "o+rwx", temp_dir])
    else:
        subprocess.call(["setfacl", "-d", "-m", "o::rwx", temp_dir])


def copy_files_to_submission_dir(temp_fixed, temp_dir):
    copy_tree(temp_fixed, temp_dir)
    shutil.copy("evaluate.sh", f"{temp_dir}/evaluate.sh")
    shutil.copy("runvalgrind.sh", f"{temp_dir}/runvalgrind.sh")
    shutil.copy("parsediff", f"{temp_dir}/parsediff")
    shutil.copy("parsevalgrind", f"{temp_dir}/parsevalgrind")
