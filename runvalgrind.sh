#!/bin/bash

valgrind --log-file="valgrindout" $@
retval=$?
script_output $(grep definitely valgrindout)
exit $retval