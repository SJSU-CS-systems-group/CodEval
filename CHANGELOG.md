# Changelog

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
