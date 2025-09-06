#!/bin/bash

set -e

SCRIPT_DIR="$(dirname $0)"

(cd "$SCRIPT_DIR"; pyproject-build)
pipx install "$SCRIPT_DIR" --force
