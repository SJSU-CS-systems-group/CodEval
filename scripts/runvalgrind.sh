#!/bin/bash

valgrind --xml=yes --xml-file=val.err --leak-check=full --error-exitcode=99 "${@}"
rc=$?
if [ $rc -eq 99 ]
then
    script_output 'FAIL!!!! YOU HAVE A MEMORY PROBLEM'
    mkdir -p evaluationLogs
    ./parsevalgrind val.err > ./evaluationLogs/log_of_valgrind
fi
rm -f val.err
exit $rc
