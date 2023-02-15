#!/bin/bash

# this script assumes the presence of testcases.txt

timeout_val=10
expected_exit_code=-1
testcase_count=0
test_args=""
pass=0
fail=0
testcase_line=""
declare -a cmps

testcase_total=0
while read -r line args
do
    if [ "$line" = "T" -o "$line" = "HT" -o "$line" = "TCMD" ]
    then
        testcase_total=$((testcase_total+1))
    fi
done < testcases.txt

exec 3> script_output.txt
script_output() {
    echo $@ >&3
}
export -f script_output

# check if there is a test to run. if so, run it.
check_test () {
    if [ -z "$test_args" ]
    then
        return
    fi

    echo -ne "\nTest Case $testcase_count of $testcase_total: "
    passed=yes
    eval timeout $timeout_val $test_args < fileinput > youroutput 2> yourerror
    retval=$?
    if [ "$retval" -eq 124 ]
    then
        echo -e "\n Took more than $timeout_val seconds to run. FAIL"
        passed=no
    fi
    rm -f difflog
    touch difflog
    diff -U1 -a ./youroutput ./expectedoutput | cat -te | head -22 > difflog
    diff -U1 -a ./yourerror ./expectederror | cat -te | head -22 >> difflog
    if [ -s difflog ]
    then
        passed=no
        ./parsediff difflog > ./evaluationLogs/logOfDiff
    fi
    if [ "$expected_exit_code" -ne "-1" ] && [ "$retval" -ne "$expected_exit_code" ]
    then
        passed=no
        echo -e "    Exit Code failure: expected $expected_exit_code got $retval"
    fi
    for cmpfiles in "${cmps[@]}"
    do
        eval cmp $cmpfiles
        if [ $? -ne 0 ]
        then
            passed=no
            break
        fi
    done
    if [ "$passed" == "yes" ]   
    then
        pass=$((pass + 1))
        echo -e "Passed "
    else
        echo -e "FAILED "
        fail=$((fail+1))
        if [ "$testcase_line" = "HT" ]
        then
            echo -e "    Test Case is Hidden."
            if [ -n "$HINT" ]
                then
                echo -e "HINT: $HINT"
            fi
        else
            if [ -n "$HINT" ]
                then
                echo -e "HINT: $HINT"
            fi
            echo -e "    Command ran: $test_args"
            for file in ./evaluationLogs/*
            do
               cat $file
            done 
        fi
        exit 2
    fi
    cmps=()
    test_args=""
    expected_exit_code=-1
    rm -rf ./evaluationLogs
    mkdir ./evaluationLogs 
    rm -rf fileinput expectedoutput expectederror
    touch fileinput expectedoutput expectederror
}
rm -rf ./evaluationLogs
mkdir ./evaluationLogs
rm -rf fileinput expectedoutput expectederror
touch fileinput expectedoutput expectederror


while read -r line args; do
if [ "$line" = "C" ]
   then
   if [ "$testcase_count" -ne 0 ]
   then
       check_test
   fi
   $args &> compilelog
   if [ $? -ne 0 ]
   then
       head -10 compilelog
   exit
   fi
elif [ "$line" = "T" ] || [ "$line" = "HT" ]
    then
    check_test
    unset HINT
    test_args=$args
    testcase_count=$((testcase_count + 1))
    testcase_line=$line
elif [ "$line" = "I" ]
    then
    echo $args >> fileinput
elif [ "$line" = "IF" ]
    then
    cat "$args" >> fileinput
elif [ "$line" = "O" ]
    then
    echo $args >> expectedoutput
elif [ "$line" = "OF" ]
    then
    cat "$args" >> expectedoutput
elif [ "$line" = "E" ]
    then
    echo $args >> expectederror
elif [ "$line" = "CMD" ]
    then
    check_test
    eval $args
elif [ "$line" = "TCMD" ]
    then
    check_test
    testcase_count=$((testcase_count + 1))
    echo -ne "\nTest Case $testcase_count of $testcase_total: "
    if ! eval $args
    then
        echo FAILED
        for file in ./evaluationLogs/*
        do
           cat $file
        done 
        exit
    else
        echo PASSED
    fi
elif [ "$line" = "CMP" ]
    then
    cmps+=("$args")
elif [ "$line" = "CF" ]
    then
    check_test
    argarray=($args)
    func="${argarray[0]}"
    filelist="${argarray[*]:1}"
    grep "[^[:alpha:]]$func[[:space:]]*(" $filelist &> /dev/null && echo "used $func PASSED" || echo "not using $func FAILED"
elif [ "$line" = "NCF" ]
    then
    check_test
    argarray=($args)
    func="${argarray[0]}"
    filelist="${argarray[*]:1}"
    grep "[^[:alpha:]]$func[[:space:]]*(" $filelist &> /dev/null && echo "used $func FAILED" || echo "not using $func PASSED"
elif [ "$line" = "X" ]
    then
    expected_exit_code=$args
elif [ "$line" = "HINT" ]
    then
    HINT="$args"
elif [ "$line" = "TO" ]
    then
    timeout_val=$args
fi
done < testcases.txt

## Last test case to be executed.
check_test
echo took $SECONDS seconds
