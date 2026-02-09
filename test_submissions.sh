#!/bin/bash

PATH=$PATH:~/.local/bin

set -e

# use flock so that we don't have overlapping builds
exec 200<> ~/deploy.lock
flock -w 2 200

if [ -d submissions ]
then
    echo "submissions directory exists. exiting."
    exit 2
fi

if [ $# -ne 1 ]
then
    echo "USAGE: $0 COURSE"
    exit 1
fi

COURSE="$1"

trap 'rm -rf submissions' EXIT
rm -rf submissions

setfacl -d -m u:$(whoami):rwX .
ulimit -f 1000000
assignment-codeval download-submissions "$COURSE" --active --uncommented_for 20
assignment-codeval github-setup-repo
assignment-codeval evaluate-submissions
assignment-codeval upload-submission-comments submissions

if [[ -n $WATCHDOG_CMD ]]
then
    $WATCHDOG_CMD
fi
