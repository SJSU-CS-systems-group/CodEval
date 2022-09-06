#!/bin/bash

valgrind --leak-check=full --error-exitcode=99 --log-file=val.err ${@}
rc=$?
if [ $rc -eq 99 ]
then
    script_output 'FAIL!!!! YOU HAVE A MEMORY PROBLEM'
    cat val.err
fi
rm -f val.err
exit $rc
