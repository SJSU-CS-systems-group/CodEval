import click
from assignment_codeval.evaluate import run_evaluation
from assignment_codeval.github_connect import github_setup_repo
from assignment_codeval.submissions import download_submissions, upload_submission_comments


@click.group()
def cli():
    pass

cli.add_command(run_evaluation)
cli.add_command(download_submissions)
cli.add_command(upload_submission_comments)
cli.add_command(github_setup_repo)

if __name__ == "__main__":
    cli()