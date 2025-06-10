#!/usr/bin/env python3
import json
import os
import shutil
import subprocess

import pytest

# Find smem2 executable
SMEM2_EXECUTABLE = shutil.which("smem2")
SMEM2_SCRIPT = "./smem2"


def run_smem2(args):
    """Runs smem2 with given arguments and returns stdout."""
    if SMEM2_EXECUTABLE:
        cmd = [SMEM2_EXECUTABLE] + args
    elif os.path.exists(SMEM2_SCRIPT):
        cmd = ["python3", SMEM2_SCRIPT] + args
    else:
        pytest.fail("smem2 executable or script not found.")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            f"smem2 command failed with exit code {result.returncode}\n"
            f"Stderr: {result.stderr}\n"
            f"Stdout: {result.stdout}"
        )

    return result.stdout


def test_basic_run():
    output = run_smem2([])
    lines = output.strip().split("\n")
    assert len(lines) >= 2  # Header + at least one process
    header = lines[0]
    assert "PID" in header
    assert "User" in header
    assert "Command" in header
    assert "Swap" in header
    assert "USS" in header
    assert "PSS" in header
    assert "RSS" in header


def test_no_header():
    output = run_smem2(["--no-header"])
    assert "PID" not in output
    assert "Command" not in output


def test_mappings():
    output = run_smem2(["--mappings"])
    lines = output.strip().split("\n")
    assert len(lines) >= 2
    header = lines[0]
    assert "Map" in header
    assert "PIDs" in header
    assert "AVGPSS" in header
    assert "PSS" in header


def test_users():
    output = run_smem2(["--users"])
    lines = output.strip().split("\n")
    assert len(lines) >= 2
    header = lines[0]
    assert "User" in header
    assert "Count" in header
    assert "Swap" in header
    assert "USS" in header
    assert "PSS" in header
    assert "RSS" in header


def test_system():
    output = run_smem2(["--system"])
    lines = output.strip().split("\n")
    assert len(lines) >= 2
    header = lines[0]
    assert "Area" in header
    assert "Used" in header
    assert "Cache" in header
    assert "Noncache" in header


def test_sysdetail():
    output_detail = run_smem2(["--sysdetail"])
    lines_detail = output_detail.strip().split("\n")
    assert len(lines_detail) >= 2
    header = lines_detail[0]
    assert "Area" in header
    assert "Used" in header
    assert "Cache" in header
    assert "Noncache" in header

    output_system = run_smem2(["--system"])
    lines_system = output_system.strip().split("\n")
    assert len(lines_detail) > len(lines_system)


def test_groupcmd():
    output = run_smem2(["--groupcmd"])
    lines = output.strip().split("\n")
    assert len(lines) >= 2
    header = lines[0]
    assert "Command" in header
    assert "PIDs" in header
    assert "Swap" in header
    assert "USS" in header
    assert "PSS" in header
    assert "RSS" in header


def test_totalsonly():
    output = run_smem2(["--totalsonly"])
    lines = output.strip().split("\n")
    # Header, separator, one line of totals
    assert len(lines) == 3


def test_reverse_sort_pid():
    output_rev = run_smem2(["-s", "pid", "-r"])
    lines_rev = output_rev.strip().split("\n")

    if len(lines_rev) <= 3:  # Header, separator, one line
        pytest.skip("Not enough processes to test sorting")

    pids_rev = []
    for line in lines_rev[2:]:
        if line.strip():
            # PID is the first column
            pids_rev.append(int(line.split()[0]))

    assert pids_rev == sorted(pids_rev, reverse=True)


def test_columns_all():
    output = run_smem2(["--columns", "all"])
    lines = output.strip().split("\n")
    assert len(lines) >= 2
    header = lines[0]
    assert "Name" in header
    assert "Maps" in header
    assert "VSS" in header
    # These might not be available on all kernels, so we don't assert their presence
    # assert "TPSS" in header
    # assert "SwapPss" in header


def test_pid_filter():
    output = run_smem2(["--pid", "1"])
    lines = output.strip().split("\n")
    # It might be that pid 1 is not accessible or doesn't exist for some reason
    # In that case smem will print header and an empty list.
    if len(lines) <= 2:
        # this is ok, smem ran but found nothing.
        return

    assert len(lines) == 3  # Header, separator, one process line
    assert lines[2].strip().split()[0] == "1"


def test_json_output():
    output = run_smem2(["-F", "json"])
    data = json.loads(output)
    assert "processes" in data
    assert isinstance(data["processes"], list)
    if not data["processes"]:
        pytest.skip("No processes found to test JSON output")
    assert "pid" in data["processes"][0]


def test_json_totals_output():
    output = run_smem2(["-F", "json", "-t"])
    data = json.loads(output)
    # The output is totals only with -t and json format.
    assert "totals" in data
    assert isinstance(data["totals"], dict)
    assert "pss" in data["totals"]


def test_json_totalsonly_output():
    output = run_smem2(["-F", "json", "-T"])
    data = json.loads(output)
    assert "totals" in data
    assert isinstance(data["totals"], dict)
    assert "processes" not in data
    assert "pss" in data["totals"]


if __name__ == "__main__":
    pytest.main([__file__])
