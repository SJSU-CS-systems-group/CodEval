#!/bin/bash

PATH=$PATH:~/.local/bin

set -e

# use flock so that we don't have overlapping builds
exec 200<> ~/deploy.lock
flock -w 2 200


if [ $# -ne 2 ]
then
    echo "USAGE: $0 COURSE ASSIGNMENT"
    exit 1
fi

COURSE="$1"
ASSIGNMENT="$2"

setfacl -d -m g::rwX .
assignment-codeval download-submissions "$COURSE" "$ASSIGNMENT" --uncommented_for 60
assignment-codeval github-setup-repo "$COURSE" "$ASSIGNMENT"
assignment-codeval evaluate-submissions ~/codeval
assignment-codeval upload-submission-comments submissions
rm -rf submissions
