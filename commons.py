import click
import time
import dataclasses


@dataclasses.dataclass(init=True, repr=True, frozen=True)
class _Config():
    """Global configuration object for the CLI"""
    show_debug: bool
    dry_run: bool
    force: bool
    copy_tmpdir: bool
    student_name: str

    # static global config instance
    _instance: '_Config' = None


def get_config():
    if _Config._instance is None:
        _Config._instance = _Config(False, True, False, False, None)
    return _Config._instance


def set_config(show_debug, dry_run, force, copy_tmpdir, student_name):
    _Config._instance = _Config(show_debug, dry_run, force, copy_tmpdir, student_name)
    return _Config._instance


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def debug(message):
    if get_config().show_debug:
        click.echo(click.style(f"{_now()} D {message}", fg='magenta'))

def error(message):
    click.echo(click.style(f"{_now()} E {message}", fg='red'))

def errorWithException(message):
    error(message)
    raise EnvironmentError(message)

def info(message):
    click.echo(click.style(f"{_now()} I {message}", fg='blue'))


def warn(message):
    click.echo(click.style(f"{_now()} W {message}", fg='yellow'))
