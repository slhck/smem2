# smem

`smem` is a tool that can give numerous reports on memory usage on Linux systems. Unlike existing tools, smem can report proportional set size (PSS), which is a more meaningful representation of the amount of memory used by libraries and applications in a virtual memory system.

Because large portions of physical memory are typically shared among multiple applications, the standard measure of memory usage known as resident set size (RSS) will significantly overestimate memory usage. PSS instead measures each application's "fair share" of each shared area to give a realistic measure.

smem has many features:

 * system overview listing
 * listings by process, mapping, user
 * filtering by process, mapping, or user
 * configurable columns from multiple data sources
 * configurable output units and percentages
 * configurable headers and totals
 * reading live data from /proc
 * lightweight capture tool for embedded systems

Contents:

- [Requirements](#requirements)
- [Usage](#usage)
- [History](#history)
- [License](#license)

## Requirements

* Python 3.6 or higher
* Linux (with procfs) with a reasonably modern kernel (> 2.6.27 or so)

## Usage

```
usage: smem [-h] [-H] [-c COLUMNS] [-a] [-R REALMEM] [-K KERNEL] [-b] [-q]
            [-P PROCESSFILTER] [-M MAPFILTER] [-U USERFILTER] [--pid PID] [-i]
            [-m] [-u] [-w] [-W] [-g] [-p] [-k] [-t] [-T] [-n] [-s SORT] [-r]
            [--cmd-width CMD_WIDTH] [--name-width NAME_WIDTH]
            [--user-width USER_WIDTH] [--mapping-width MAPPING_WIDTH]

smem is a tool that can give numerous reports on memory usage on Linux
systems. Unlike existing tools, smem can report proportional set size (PSS),
which is a more meaningful representation of the amount of memory used by
libraries and applications in a virtual memory system.

options:
  -h, --help            show this help message and exit
  -H, --no-header       Disable header line
  -c COLUMNS, --columns COLUMNS
                        Columns to show, use 'all' to show all columns
  -a, --autosize        Size columns to fit terminal size
  -R REALMEM, --realmem REALMEM
                        Amount of physical RAM
  -K KERNEL, --kernel KERNEL
                        Path to kernel image
  -b, --basename        Name of executable instead of full command
  -q, --quiet           Suppress warnings

Filter:
  -P PROCESSFILTER, --processfilter PROCESSFILTER
                        Process filter regex
  -M MAPFILTER, --mapfilter MAPFILTER
                        Process map regex
  -U USERFILTER, --userfilter USERFILTER
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

Sort:
  -n, --numeric         Numeric sort
  -s SORT, --sort SORT  Field to sort on
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

For more information please visit: https://github.com/slhck/smem
```

## History

Changes compared to the [original `smem` version](https://www.selenic.com/smem/) were primarily made in the [fork from GdH](https://github.com/G-dH/smem):

 * bugfix for "list index out of range" and getcolumns() call
 * added support for *proc/pid/smaps_rollup* (big speed boost for nonmapping part)
 * added *SwapPss, RssAnon, RssFile, RssShmem, PssAnon, PssFile, PssShmem, AvgVss* columns when supported by kernel
 * added *TPss* column = *Pss* + *SwapPss*
 * added *Name* column (process name *comm*) to process view
 * added *-g*/*--groupcmd* group by command view - same executables grouped together
 * added *-b*/*--basename* option: show only name of executables instead of path / full command with aeguments
 * added physical RAM size detection via *dmidecode* in system overview
 * added *-P* process filter can filter by *PID* and name (comm)
 * added *-T/--totalsonly* print totals only
 * added *-i/--ignorecase* option for case insensitive search
 * added *-W/--sysdetail* option with more detailed view on system memory
 * added */dev/zero* mapping summary - memory initialized from /dev/zero can be (wrongly) included as backed by file to *Mapped* measurement in /proc/meminfo. That should be treated as anonymous memory and therefore it is now subtracted from the *Mapped* measurement in smem system view as *Mapped* is used to interpret cached part of the memory consumed by the processes.
 * added warnings about missing kernel features
 * added *-q/--quiet* option to mute warnings
 * added *-c/--columns* option accept "all" string to use all available columns and *+column_name ...* to add columns to default set
 * added *--pid* option to show process memory based on one pid
 * excluded own process from *-P* filtered output
 * fixed -M filter
 * fixed -R option not accepting argument
 * fixed -K option - kernel compression detection
 * fixed AVGUSS - KeyError: 'uss'

## License

smem is licensed under the GPL version 2.0. See the COPYING file for more information.
