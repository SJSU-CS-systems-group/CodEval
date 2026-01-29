import click

from assignment_codeval.ai_benchmark import get_benchmark_command
from assignment_codeval.create_assignment import create_assignment
from assignment_codeval.evaluate import run_evaluation
from assignment_codeval.github_connect import github_setup_repo
from assignment_codeval.submissions import download_submissions, upload_submission_comments, evaluate_submissions, list_codeval_assignments


@click.group()
def cli():
    pass

cli.add_command(run_evaluation)
cli.add_command(download_submissions)
cli.add_command(upload_submission_comments)
cli.add_command(github_setup_repo)
cli.add_command(evaluate_submissions)
cli.add_command(create_assignment)
cli.add_command(list_codeval_assignments)
cli.add_command(get_benchmark_command())

if __name__ == "__main__":
    cli()