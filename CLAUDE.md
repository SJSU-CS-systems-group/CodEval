# Project Description

A python utility to download student submissions to programming assignments from Canvas and GitHub
and evaluate them using codeval scripts.

# Project Structure

```
src/assignment_codeval/
├── cli.py              # Click CLI entry point, registers all subcommands
├── submissions.py      # Download/upload submissions, list assignments
├── evaluate.py         # Run evaluation on submissions (run-evaluation)
├── create_assignment.py # Create assignments on Canvas
├── github_connect.py   # GitHub repository setup and integration
├── canvas_utils.py     # Canvas API utilities
├── ai_benchmark.py     # AI model testing (test-with-ai)
├── install_assignment.py # Install codeval files to local/remote destinations
├── recent_comments.py  # List recent codeval comments on Canvas
├── convertMD2Html.py   # Markdown to HTML conversion
├── commons.py          # Shared utilities
└── file_utils.py       # File handling utilities

tests/
├── test_codeval.py           # Main test suite
├── test_create_assignment.py # Assignment creation tests
├── test_evaluate_submissions.py # Evaluate submissions tests
├── test_install_assignment.py # Install assignment tests
└── sample_*.py               # Sample programs for testing
```

# CLI Commands

The CLI is `assignment-codeval` with these subcommands:

| Command | Description |
|---------|-------------|
| `create-assignment` | Create assignment in Canvas from codeval spec |
| `download-submissions` | Download submissions from Canvas/GitHub |
| `evaluate-submissions` | Evaluate downloaded submissions |
| `run-evaluation` | Run evaluation in docker container |
| `upload-submission-comments` | Upload grading comments to Canvas |
| `github-setup-repo` | Connect GitHub repo for assignment |
| `list-codeval-assignments` | List assignments with codeval specs |
| `install-assignment` | Copy codeval file and zip dependencies to local/remote path |
| `recent-comments` | List recent codeval comments on Canvas submissions |
| `test-with-ai` | Benchmark AI models on assignments |

# Common Commands

```bash
# Run tests
pytest tests/

# Install locally for development
pip install -e .

# List all CLI commands
assignment-codeval --help

# Get help for a specific command
assignment-codeval download-submissions --help
```

# Pypi

- The CodEval is published in pypi as assignment-codeval.
- When publishing a new release, use the `/release` skill which will:
    1. create a commit with a new version number and a summary of changes in CHANGELOG.md since the last release
    2. push the commit
    3. build and publish the new version to pypi

# CodEval Scripts

- Files with `.codeval` extension containing tags to specify how to build submissions, populate support files, and run tests
- The beginning of the file usually has markdown (between `CRT_HW START` and `CRT_HW END`) to describe the assignment for Canvas
- Full tag reference is in README.md, key tags:
  - `C` - Compile command
  - `T/HT` - Test case (HT = hidden test)
  - `I/IB/IF` - Input (newline/bare/file)
  - `O/OB/OF` - Expected output (newline/bare/file)
  - `TO` - Timeout in seconds
  - `X` - Expected exit code

# Code Conventions

- Use Click for CLI commands (see cli.py for registration pattern)
- Add new commands in their own module, then register in cli.py
- Canvas API interactions go through canvas_utils.py
- GitHub interactions go through github_connect.py

