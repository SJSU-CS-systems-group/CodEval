#!/bin/bash

while true; do
    # Check if the mysqld process is running
    if pgrep mysqld > /dev/null; then
        echo "MySQL is running."
        break
    else
        echo "MySQL is not running. Waiting..."
        sleep 1
    fi
done





