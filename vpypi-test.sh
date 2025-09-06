#!/bin/bash

set -e

if [[ -n "$VIRTUAL_ENV" ]]
then
    echo "Running inside venv at $VIRTUAL_ENV"
else
    if [[ -n "$FORCE_NO_VENV" ]]
    then
        echo "Running outside of a venv"
    else
        echo "Not in a venv. This script is designed to setup your venv."
        echo "define the FORCE_NO_VENV to skip this check."
        exit 1
    fi
fi

SCRIPT_DIR="$(dirname $0)"

pip install -U pip
pip install "$SCRIPT_DIR"

