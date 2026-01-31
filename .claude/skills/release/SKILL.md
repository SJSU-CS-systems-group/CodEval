---
name: release
description: Bump version, update changelog, commit, push, and publish to PyPI
argument-hint: "[version]"
---

# Release assignment-codeval to PyPI

Release a new version of assignment-codeval. If a version number is provided as `$ARGUMENTS`, use it. Otherwise, auto-increment the patch version (e.g., 0.0.14 -> 0.0.15).

## Pre-flight checks

1. Check for uncommitted changes with `git status`. If there are uncommitted changes, warn the user and stop.
2. Get the current version from `pyproject.toml`

## Gather changelog entries

1. Find the commit that bumped to the current version: `git log --oneline --grep="bump version to"`
2. Get all commits since that version bump: `git log --oneline <version-bump-commit>..HEAD`
3. Summarize these commits into changelog bullet points (exclude merge commits and trivial changes)

## Update files

1. Update `version` in `pyproject.toml` to the new version
2. Update `CHANGELOG.md`:
   - Add a new section at the top (after the `# Changelog` header) with the new version number
   - Add bullet points summarizing the changes

## Commit and push

1. Stage the changes: `git add pyproject.toml CHANGELOG.md`
2. Commit with message: `bump version to <new-version>`
3. Push to remote: `git push`

## Build and publish

1. Build the package: `python -m build`
2. Upload to PyPI: `twine upload dist/<package>-<new-version>*`
3. Report the PyPI URL to the user

## On failure

If any step fails, stop and report the error. Do not continue with partial releases.
