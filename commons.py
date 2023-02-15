import click
import time


show_debug = False

def set_debug(value):
    global show_debug
    show_debug = value

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