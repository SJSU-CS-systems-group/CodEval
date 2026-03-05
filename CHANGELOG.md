# Changelog

## 0.0.27

- Upload assignment files to per-assignment subfolder under CodEval instead of the root CodEval folder

## 0.0.26

- Replace `cat -te | head -22` shell pipeline with pure Python `_render_diff_output()` for diff output rendering
- Add SUBSTITUTIONS.txt support for comment text replacement before Canvas upload
  - evaluate-submissions copies SUBSTITUTIONS.txt from zip files to submission directory
  - upload-submission-comments applies literal string substitutions from SUBSTITUTIONS.txt
  - File format: each line is `<delim>pattern<delim>replacement<delim>` (first char defines delimiter)
- Add OLEN tag to override the default 4096-byte diff output length limit
- Escape `<` as `&lt;` in comments and wrap in `<pre>` tags for Canvas upload

## 0.0.25

- Add export-tests command to extract test cases from codeval files into a zip archive
  - Exports in.X, out.X, err.X files and a TESTS.md summary for each test case
  - --include-hidden flag to include hidden test cases
  - Reads IF/OF file contents from Z-tag zip archives
- Updated submission file UI
- Replace regex function detection with objdump/javap/ast for CF tag
- Add PRINT tag for printing section labels
- Track file timestamps and compare outputs for file-based test cases

## 0.0.24

- Convert recent-comments to use Canvas GraphQL API instead of REST for faster performance
- Extract shared GraphQL helpers (get_canvas_credentials, graphql_request, fetch_all_submissions) to canvas_utils.py
- Fix missing comments when a student has more than 20 codeval comments by sorting newest-first

## 0.0.23

- Add check-grading command to find submissions missing a codeval comment
  - Shows elapsed time since submission for ungraded students
  - --warn flag to show recent submissions awaiting comments
  - --max-comment-delay to configure warning threshold
  - --verbose flag to show all submissions

## 0.0.22

- Fix HTML generation for create-assignment ignoring OF, OB, IF, IB, EB tags
- Inline OF/IF file content in sample test case HTML instead of showing filename
- Convert ANSI escape codes in OF/IF file content to styled HTML spans
- Add COMPILE macro that expands to the C tag value in assignment descriptions
- Fix tag parser stripping leading whitespace from I, O, E tag values
- Fix case-insensitive codeval file lookup

## 0.0.21

- Truncate large submission comments to 4K characters to avoid Canvas API limits

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
