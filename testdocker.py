import sys, os
import click
import subprocess, shutil
from distutils.dir_util import copy_tree



def error(message):
    click.echo(click.style(message, fg='red'))


if __name__ == "__main__":
    create_docker_container_cmd = "docker build . -t codeval:1"
    p = subprocess.Popen(create_docker_container_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=20)
    if err:
        error(err, True)
    print(out)

    evaluate_submission = "docker run codeval:1 "
    p = subprocess.Popen(evaluate_submission, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate(timeout=20)

    print(out)


