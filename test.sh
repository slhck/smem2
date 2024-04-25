#!/usr/bin/env bash

set -e

SMEM2_SCRIPT=$(which smem2)

function run_test() {
    echo "Running: $1"
    eval $1
    if [ $? -eq 0 ]; then
        echo "Success: Test passed!"
    else
        echo "Error: Test failed!"
        exit 1
    fi
    echo
}

run_test "python3 $SMEM2_SCRIPT"

run_test "python3 $SMEM2_SCRIPT --no-header"

run_test "python3 $SMEM2_SCRIPT --mappings"

run_test "python3 $SMEM2_SCRIPT --users"

run_test "python3 $SMEM2_SCRIPT --system"

run_test "python3 $SMEM2_SCRIPT --sysdetail"

run_test "python3 $SMEM2_SCRIPT --groupcmd"

run_test "python3 $SMEM2_SCRIPT --totalsonly"

run_test "python3 $SMEM2_SCRIPT --reverse"

run_test "python3 $SMEM2_SCRIPT --columns all"

run_test "python3 $SMEM2_SCRIPT --pid 1"

echo "All tests complete."
