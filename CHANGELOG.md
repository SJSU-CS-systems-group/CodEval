# Changelog

## 0.0.20

- Add github_repo field to metadata.txt during download-submissions
- Simplify github-setup-repo to read repo URL from metadata.txt instead of Canvas
- Add global --debug flag to CLI for debug output
- Fix GitHub repo lookup to use course.get_user() instead of canvas.get_user()

## 0.0.19

- Add recent-comments command to list recent codeval comments on Canvas submissions
  - --time-period option with flexible format (30m, 2h, 1d, 1w)
  - --active flag to check all active courses
  - --verbose flag to show progress
  - --show-uncommented flag to show submissions needing grading
  - Displays times in local timezone
  - Shows first/last 3 lines of each comment

## 0.0.18

- Make CODEVAL_DIR argument optional in evaluate-submissions; uses [CODEVAL] directory from config if not specified

## 0.0.17

- Fix GitHub detection to check .git at submission root instead of nested directory

## 0.0.16

- Add install-assignment command to copy codeval files and zip dependencies to local or remote destinations
- Auto-detect GitHub submissions and use assignment name as working directory when no CD tag is specified
- Fix zip file extraction to use correct working directory for GitHub submissions

## 0.0.15

- Add list-codeval-assignments command
- Add --active flag to download-submissions for all active courses/assignments
- Make course and assignment optional for github-setup-repo
- Add last-comment.txt file when downloading submissions
- Merge eval comments with any github comments
- Add g++ to the docker image

## 0.0.14

- Ignore CD tag in run-evaluation
- Add limits
- Don't fail hard if a submission directory doesn't exist
