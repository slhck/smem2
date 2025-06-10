# smem2

`smem2` is a tool that can give numerous reports on memory usage on Linux systems. Unlike existing tools, smem2 can report proportional set size (PSS), which is a more meaningful representation of the amount of memory used by libraries and applications in a virtual memory system.

Contents:

- [Requirements](#requirements)
- [Installation](#installation)
- [CLI Usage](#cli-usage)
  - [Full Usage](#full-usage)
- [Docker Usage](#docker-usage)
  - [Running smem2 with Docker](#running-smem2-with-docker)
  - [Testing with Docker](#testing-with-docker)
- [API Usage](#api-usage)
- [Detailed Description](#detailed-description)
- [License](#license)

## Requirements

* Python 3.9 or higher
* Linux (with procfs) with a reasonably modern kernel (> 2.6.27 or so)

## Installation

You can install the tool and library with `pip`:

```bash
pip3 install smem2
```

If you only need the tool, you should probably install it with `pipx`:

```bash
pipx install smem2
```

Or use `uvx` (from [`uv`](https://docs.astral.sh/uv/)) directly:

```bash
uvx smem2
```

## CLI Usage

Basic usage:

```bash
smem2
```

Example output:

```console
  PID User     Command                         Swap      USS      PSS      RSS
-------------------------------------------------------------------------------
    1 root     python3 /usr/local/bin/smem        0    11900    12319    13340
```

Print a system overview:

```bash
smem2 -w
```

Example output:

```console
Area                           Used      Cache   Noncache
----------------------------------------------------------
firmware/hardware                 0          0          0
kernel image                      0          0          0
kernel dynamic memory       2406196    2118576     287620
userspace memory            5544328     962032    4582296
free memory                  177376     177376          0
```

Group processes by command:

```bash
smem2 -g
```

Example output:

```console
Command                      PIDs     Swap      USS      PSS      RSS
----------------------------------------------------------------------
python3                         1        0    11888    12307    13328
```

Print totals only:

```bash
smem2 -T
```

Example output:

```console
  PID User     Command                         Swap      USS      PSS      RSS
-------------------------------------------------------------------------------
    1 1                                           0    11908    12327    13348

```

Print using human-readable numbers with unit suffixes:

```bash
smem2 -k
```

Example output:

```console
  PID User     Command                         Swap      USS      PSS      RSS
-------------------------------------------------------------------------------
    1 root     python3 /usr/local/bin/smem        0    11.6M    12.0M    13.0M
```

Print a system overview in detail:

```bash
smem2 -W
```

Example output:

```
Area                           Used      Cache   Noncache
----------------------------------------------------------
firmware/hardware                 0          0          0
kernel image                      0          0          0
kernel modules                  200          0        200
page tables                   37372          0      37372
kernel stack                  12464          0      12464
slab (all/SReclaimable)      602872     520096      82776
buffers                      406656     406656          0
cached (w/o mapped,tmpfs,ramfs)    1159252    1159252          0
shared (non process tmpfs)      33672          0      33672
ramfs                             0          0          0
unknown                      161848          0     161848
processes (all/mapped files)    5553188     960964    4592224
free memory                  160376     160376          0
```

Print as JSON:

```bash
smem2 -F json
```

Example output:

```json
{"processes": [{"pid": 1, "user": "root", "command": "python3 /usr/local/bin/smem2 -F json", "swap": 0, "uss": 11880, "pss": 12299, "rss": 13320}]}
```

### Full Usage

```
usage: smem2 [-h] [-H] [-c COLUMNS] [-a] [-R REALMEM] [-K KERNEL] [-b] [-q]
             [--version] [-P PROCESSFILTER] [-M MAPFILTER] [-U USERFILTER]
             [--pid PID] [-i] [-m] [-u] [-w] [-W] [-g] [-p] [-k] [-t] [-T]
             [-F FORMAT] [-n] [-s SORT] [-r] [--cmd-width CMD_WIDTH]
             [--name-width NAME_WIDTH] [--user-width USER_WIDTH]
             [--mapping-width MAPPING_WIDTH]

smem2 is a tool that can give numerous reports on memory usage on Linux
systems. Unlike existing tools, smem2 can report proportional set size (PSS),
which is a more meaningful representation of the amount of memory used by
libraries and applications in a virtual memory system.

options:
  -h, --help            show this help message and exit
  -H, --no-header       Disable header line
  -c, --columns COLUMNS
                        Columns to show, use 'all' to show all columns
  -a, --autosize        Size columns to fit terminal size
  -R, --realmem REALMEM
                        Amount of physical RAM
  -K, --kernel KERNEL   Path to kernel image
  -b, --basename        Name of executable instead of full command
  -q, --quiet           Suppress warnings
  --version             show program's version number and exit

Filter:
  -P, --processfilter PROCESSFILTER
                        Process filter regex
  -M, --mapfilter MAPFILTER
                        Process map regex
  -U, --userfilter USERFILTER
                        Process users regex
  --pid PID             Show just process memory based on one pid
  -i, --ignorecase      Case insensitive filter

Show:
  -m, --mappings        Show mappings
  -u, --users           Show users
  -w, --system          Show whole system
  -W, --sysdetail       Show whole system in detail
  -g, --groupcmd        Show processes grouped by executables
  -p, --percent         Show percentage
  -k, --abbreviate      Show unit suffixes
  -t, --totals          Show totals
  -T, --totalsonly      Show totals only
  -F, --format FORMAT   Output format (raw, json)

Sort:
  -n, --numeric         Numeric sort
  -s, --sort SORT       Field to sort on
  -r, --reverse         Reverse sort

Width:
  --cmd-width CMD_WIDTH
                        Text width for commands (0=as needed)
  --name-width NAME_WIDTH
                        Text width for command names (0=as needed)
  --user-width USER_WIDTH
                        Text width for user names (0=as needed)
  --mapping-width MAPPING_WIDTH
                        Text width for mapping names (0=as needed)

Version: 2.2.0 - for more information please visit:
https://github.com/slhck/smem
```

## Docker Usage

The project includes a multi-stage Dockerfile with separate stages for running the tool and testing.

### Running smem2 with Docker

To build and run smem2 using Docker:

```bash
# Build the production image
docker build -t smem2 --target production .

# Run smem2 (default process view)
docker run --rm smem2

# Run with specific options
docker run --rm smem2 --system
docker run --rm smem2 --users
docker run --rm smem2 --help
```

### Testing with Docker

To run the test suite using Docker:

```bash
# Build the test image
docker build -t smem2-test --target test .

# Run all tests
docker run --rm smem2-test

# Run specific tests
docker run --rm smem2-test test/test_smem2.py::test_basic_run
docker run --rm smem2-test -v  # verbose output
```

## API Usage

You can import `smem2` as a library and use it in your own Python code.

You can check the `__main__.py` file for an example of how to use the library.

## Detailed Description

Because large portions of physical memory are typically shared among multiple applications, the standard measure of memory usage known as resident set size (RSS) will significantly overestimate memory usage. PSS instead measures each application's "fair share" of each shared area to give a realistic measure.

smem2 is based the [original `smem` version](https://www.selenic.com/smem/) and its many forks, with adjustments primarily made in the [fork from GdH](https://github.com/G-dH/smem). This is just a cleaner version of the original `smem` with some additional features and bugfixes, and Python code improvements. The whole credit to the actual functionality goes to the original authors.

smem2 has many features:

 * system overview listing
 * listings by process, mapping, user
 * filtering by process, mapping, or user
 * configurable columns from multiple data sources
 * configurable output units and percentages
 * configurable headers and totals
 * reading live data from /proc
 * lightweight capture tool for embedded systems
 * JSON output support


## License

smem2 is licensed under the GPL version 2.0. See the COPYING file for more information.
