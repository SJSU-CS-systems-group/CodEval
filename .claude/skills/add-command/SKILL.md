---
name: add-command
description: Add a new Click CLI subcommand to assignment-codeval
argument-hint: "<command-name>"
---

# Add a New CLI Command

Create a new Click subcommand for assignment-codeval.

## Required argument

`$ARGUMENTS` should be the name of the new command (e.g., `grade-submissions`).

If no argument is provided, ask the user for the command name and what it should do.

## Steps

1. **Create the command module** (if it doesn't fit in an existing module):
   - Create a new file in `src/assignment_codeval/`
   - Follow the pattern of existing commands (see `evaluate.py` or `submissions.py`)

2. **Define the Click command**:
   ```python
   import click

   @click.command()
   @click.argument('required_arg')
   @click.option('--optional', default='value', help='Description')
   def command_name(required_arg, optional):
       """Command description shown in --help."""
       # Implementation
   ```

3. **Register in cli.py**:
   ```python
   from assignment_codeval.new_module import command_name
   cli.add_command(command_name)
   ```

4. **Add tests** in `tests/test_<module>.py`

## Code conventions

- Use `click.echo()` for output
- Use `click.ClickException()` for errors
- Follow existing naming: `kebab-case` for command names, `snake_case` for functions
- Add `--dry-run` flag for commands that modify external state (Canvas, GitHub)
- Add `--verbose` flag for commands that benefit from detailed output

## Example

See `src/assignment_codeval/evaluate.py` for a well-structured command example.
