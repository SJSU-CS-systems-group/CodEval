from typing import NoReturn

import click
import time
import dataclasses


def despace(name):
    # we need to replace spaces with _ to work well with scripts
    # we need to remove the : so that it doesn't mess up docker
    return name.replace(" ", "_").replace(":","")


@dataclasses.dataclass(init=True, repr=True, frozen=True)
class _Config():
    """Global configuration object for the CLI"""
    show_debug: bool
    dry_run: bool
    force: bool
    copy_tmpdir: bool

    # static global config instance
    _instance: '_Config' = None


def get_config():
    if _Config._instance is None:
        _Config._instance = _Config(False, True, False, False)
    return _Config._instance


def set_config(show_debug, dry_run, force, copy_tmpdir):
    _Config._instance = _Config(show_debug, dry_run, force, copy_tmpdir)
    return _Config._instance


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def debug(message):
    if get_config().show_debug:
        click.echo(click.style(f"{_now()} D {message}", fg='magenta'))

def error(message):
    click.echo(click.style(f"{_now()} E {message}", fg='red'))

def errorWithException(message) -> NoReturn:
    error(message)
    raise EnvironmentError(message)

def info(message):
    click.echo(click.style(f"{_now()} I {message}", fg='blue'))


def warn(message):
    click.echo(click.style(f"{_now()} W {message}", fg='yellow'))
