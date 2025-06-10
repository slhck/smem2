import argparse
import errno
import json
import os
import re
import sys
from typing import Callable

from . import __version__
from .smem2 import (
    MemData,
    Proc,
    ProcessData,
    SmemConfig,
    get_cmd_data,
    get_map_data,
    get_process_data,
    get_system_data,
    get_user_data,
    setdatasources,
    totalmem,
    units,
)


def showamount(a, total, config: SmemConfig):
    """Formats a memory amount for display.

    Depending on the configuration, it can show the value as a percentage
    of a total, with abbreviated units (K, M, G), or as a raw number.

    Args:
        a (int or float): The amount to format (in kilobytes).
        total (int or float): The total amount for percentage calculations.
        config (SmemConfig): The smem2 configuration.

    Returns:
        str: The formatted memory amount as a string.
    """
    if config.percent:
        if total == 0:
            return "0"
        return "%.2f%%" % (100.0 * a / total)
    elif config.abbreviate:
        return units(a * 1024)
    return a


def widthstr(field, width, default, config: SmemConfig):
    """Creates a format string for a fixed-width column.

    If the width is 0, it returns a dynamic width format string ("%s").
    Otherwise, it creates a left-aligned format string of the specified width.

    Args:
        field (str): The name of the field.
        width (int): The desired width. If negative, the default is used.
        default (int): The default width if width is negative.
        config (SmemConfig): The smem2 configuration.

    Returns:
        str: The format string for the column.
    """
    if width == 0:
        return "%s"
    if width < 0:
        size = default
    else:
        size = width
        config.ignore_autosize.add(field)
    return "%-{size}.{size}s".format(size=size)


def getcolumns(columns, fields, config: SmemConfig):
    """Determines the final list of columns to display.

    It can add columns from the config, use all available columns,
    or use a default set.

    Args:
        columns (str): The default set of columns.
        fields (dict): A dictionary of all available fields.
        config (SmemConfig): The smem2 configuration.

    Returns:
        str: A space-separated string of column names to display.
    """
    if "+" in config.columns:
        columns = columns + " " + config.columns.strip("+")
        return columns
    if "all" in config.columns:
        return " ".join(fields.keys())
    return config.columns or columns


def show_fields_error_and_exit(fields, f):
    """
    Prints an error about unknown fields and exits.

    It lists the unknown fields provided and then lists all known fields
    before exiting the program.

    Args:
        fields (dict): A dictionary containing the known fields and their descriptions.
        f (str or list or set): The unknown field(s) that caused the error.
    """
    if type(f) in (list, set):
        print("unknown fields: " + " ".join(f), file=sys.stderr)
    else:
        print("unknown field %s" % f, file=sys.stderr)
    print("known fields:", file=sys.stderr)
    for l in sorted(fields):
        print("%-8s %s" % (l, fields[l][-1]), file=sys.stderr)

    sys.exit(-1)


def autosize(columns, fields, rows, config: SmemConfig):
    """Calculates the optimal column sizes for the output table.

    It determines the width of each column based on the header and data content.
    It also handles a special "overflow" column (like 'command') to fit the
    table within the terminal width.

    Args:
        columns (list[str]): The columns to be displayed.
        fields (dict): A dictionary describing the available fields.
        rows (list): The list of data rows to be displayed.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary mapping column names to their calculated optimal width.
    """
    colsizes = {}
    for c in columns:
        if c in config.ignore_autosize:
            continue
        sizes = [1]

        if not config.no_header:
            sizes.append(len(fields[c][0]))

        if (config.abbreviate or config.percent) and "a" in fields[c][2]:
            sizes.append(7)
        else:
            for r in rows:
                sizes.append(len(str(fields[c][1](r))))

        colsizes[c] = max(sizes)

    overflowcols = (
        set(["command", "map", "comm"]) & set(columns)
    ) - config.ignore_autosize
    if len(overflowcols) > 0:
        overflowcol = overflowcols.pop()
        totnoflow: int = sum(colsizes.values()) - colsizes[overflowcol]
        try:
            _, ttycolumns = [int(i) for i in os.popen("stty size", "r").read().split()]
        except Exception:
            _, ttycolumns = (24, 80)
        maxflowcol = ttycolumns - totnoflow - len(columns)
        maxflowcol = max(maxflowcol, 10)
        colsizes[overflowcol] = min(colsizes[overflowcol], maxflowcol)

    return colsizes


def showtable(rows: list, fields: dict, columns: list, sort: str, config: SmemConfig):
    """Formats and prints the data in a table.

    It handles sorting, formatting columns, calculating totals, and printing
    the final output in either raw text or JSON format.

    Args:
        rows (list): The list of data rows (e.g., list of PIDs, users, or maps).
        fields (dict): A dictionary describing the available fields (columns).
        columns (list[str]): The names of the columns to display.
        sort (str): The column name to sort by.
        config (SmemConfig): The smem2 configuration.
    """
    header = ""
    table_format = ""
    formatter: list[Callable] = []

    if sort not in fields:
        show_fields_error_and_exit(fields, sort)

    mt = totalmem(config)
    memdata = MemData()
    st = memdata("swaptotal")

    missing = set(columns) - set(fields)
    if len(missing) > 0:
        show_fields_error_and_exit(fields, missing)

    if config.autosize:
        colsizes = autosize(columns, fields, rows, config)
    else:
        colsizes = {}

    for n in columns:
        f = fields[n][2]
        if "a" in f:
            if n == "swap":
                formatter.append(lambda x: showamount(x, st, config))
            else:
                formatter.append(lambda x: showamount(x, mt, config))
            f = f.replace("a", "s")
        else:
            formatter.append(lambda x: x)
        if n in colsizes:
            f = re.sub(r"[0-9]+", str(colsizes[n]), f)
        table_format += f + " "
        header += f % fields[n][0] + " "

    l = []
    for n in rows:
        r = [fields[c][1](n) for c in columns]
        l.append((fields[sort][1](n), r))

    if sort in ("command", "comm"):
        l.sort(reverse=bool(config.reverse), key=lambda v: v[0].lower())
    else:
        l.sort(reverse=bool(config.reverse))

    if config.format == "raw":
        if not config.no_header:
            print(header)
            print("-" * len(header))

        if not config.totalsonly:
            for k, r in l:
                print(table_format % tuple([f(v) for f, v in zip(formatter, r)]))

        if config.totals:
            # totals
            t = []
            for c in columns:
                f = fields[c][3]
                if f:
                    t.append(f([fields[c][1](n) for n in rows]))
                else:
                    t.append("")

            if not config.totalsonly:
                print("-" * len(header))
            print(table_format % tuple([f(v) for f, v in zip(formatter, t)]))
    elif config.format == "json":
        ret: dict
        if not config.totals:
            data = []
            for _k, row in l:
                row_data = {}
                for i, col in enumerate(columns):
                    # row_data[col] = row[i] --> raw
                    row_data[col] = formatter[i](row[i])

                data.append(row_data)
            ret = {"processes": data}
        else:
            t = []
            for c in columns:
                f = fields[c][3]
                if f:
                    t.append(f([fields[c][1](n) for n in rows]))
                else:
                    t.append("")

            row_data = {}
            for i, col in enumerate(columns):
                row_data[col] = t[i]

            ret = {"totals": row_data}

        print(json.dumps(ret))
    else:
        sys.stderr.write("Unknown format '%s'\n" % config.format)
        sys.exit(-1)


def showpids(config: SmemConfig, proc: ProcessData):
    """Displays memory usage by process.

    This is the default view. It gathers process data and displays it in a table.

    Args:
        config (SmemConfig): The smem2 configuration.
        proc (ProcessData): The ProcessData instance for accessing /proc data.
    """
    pt = get_process_data(proc, config)

    def showuser(p):
        if config.numeric:
            return proc.piduser(p)
        return proc.pidusername(p)

    fields = dict(
        pid=("PID", lambda n: n, "% 5s", lambda x: len(pt), "process ID"),
        user=(
            "User",
            showuser,
            widthstr("user", config.user_width, 8, config),
            lambda x: len(dict.fromkeys(x)),
            "owner of process",
        ),
        command=(
            "Command",
            proc.pidcmd,
            widthstr("command", config.cmd_width, 27, config),
            None,
            "process command line",
        ),
        name=(
            "Name",
            proc.pidname,
            widthstr("comm", config.cmd_width, 15, config),
            None,
            "process name",
        ),
        maps=("Maps", lambda n: pt[n]["maps"], "% 5s", sum, "total number of mappings"),
        pss=(
            "PSS",
            lambda n: pt[n]["pss"],
            "% 8a",
            sum,
            "proportional set size",
        ),
        rss=(
            "RSS",
            lambda n: pt[n]["rss"],
            "% 8a",
            sum,
            "resident set size",
        ),
        uss=(
            "USS",
            lambda n: pt[n]["uss"],
            "% 8a",
            sum,
            "unique set size",
        ),
        swap=(
            "Swap",
            lambda n: pt[n]["swap"],
            "% 8a",
            sum,
            "swapped-out memory",
        ),
        vss=(
            "VSS",
            lambda n: pt[n]["size"],
            "% 8a",
            sum,
            "virtual set size",
        ),
    )
    if config.swappss:
        fields["swappss"] = (
            "SwapPSS",
            lambda n: pt[n]["swappss"],
            "% 8a",
            sum,
            "proportional swapped-out memory",
        )
    if config.pssdetail:
        fields["pss_anon"] = (
            "PssAnon",
            lambda n: pt[n]["pss_anon"],
            "% 8a",
            sum,
            "proportional anonymous memory",
        )
        fields["pss_file"] = (
            "PssFile",
            lambda n: pt[n]["pss_file"],
            "% 8a",
            sum,
            "proportional file-backed memory",
        )
        fields["pss_shmem"] = (
            "PssShmem",
            lambda n: pt[n]["pss_shmem"],
            "% 8a",
            sum,
            "proportional shmem-backed memory",
        )
    if config.rssdetail:
        fields["rss_anon"] = (
            "RssAnon",
            lambda n: pt[n]["rss_anon"],
            "% 8a",
            sum,
            "anonymous memory",
        )
        fields["rss_file"] = (
            "RssFile",
            lambda n: pt[n]["rss_file"],
            "% 8a",
            sum,
            "file-backed memory",
        )
        fields["rss_shmem"] = (
            "RssShmem",
            lambda n: pt[n]["rss_shmem"],
            "% 8a",
            sum,
            "shmem-backed memory",
        )

    columns = getcolumns("pid user command swap uss pss rss", fields, config).split()

    sort = config.sort or "pss"
    showtable(list(pt.keys()), fields, columns, sort, config)


def showmaps(config: SmemConfig, proc: ProcessData):
    """Displays memory usage by mapping.

    It aggregates memory usage across all processes for each unique memory mapping
    and displays it in a table.

    Args:
        config (SmemConfig): The smem2 configuration.
        proc (ProcessData): The ProcessData instance for accessing /proc data.
    """
    pt = get_map_data(proc, config)
    fields = dict(
        map=(
            "Map",
            lambda n: n,
            widthstr("map", config.mapping_width, 40, config),
            len,
            "mapping name",
        ),
        count=(
            "Count",
            lambda n: pt[n]["count"],
            "% 5s",
            sum,
            "number of mappings found",
        ),
        pids=(
            "PIDs",
            lambda n: pt[n]["pids"],
            "% 5s",
            sum,
            "number of PIDs using mapping",
        ),
        pss=(
            "PSS",
            lambda n: pt[n]["pss"],
            "% 8a",
            sum,
            "proportional set size",
        ),
        rss=(
            "RSS",
            lambda n: pt[n]["rss"],
            "% 8a",
            sum,
            "resident set size",
        ),
        uss=(
            "USS",
            lambda n: pt[n]["private_clean"] + pt[n]["private_dirty"],
            "% 8a",
            sum,
            "unique set size",
        ),
        swap=(
            "Swap",
            lambda n: pt[n]["swap"],
            "% 8a",
            sum,
            "swapped-out memory",
        ),
        vss=(
            "VSS",
            lambda n: pt[n]["size"],
            "% 8a",
            sum,
            "virtual set size",
        ),
        avgpss=(
            "AVGPSS",
            lambda n: int(1.0 * pt[n]["pss"] / pt[n]["pids"])
            if pt[n]["pids"] > 0
            else 0,
            "% 8a",
            sum,
            "average PSS per PID",
        ),
        avguss=(
            "AVGUSS",
            lambda n: int(
                1.0 * (pt[n]["private_clean"] + pt[n]["private_dirty"]) / pt[n]["pids"]
            )
            if pt[n]["pids"] > 0
            else 0,
            "% 8a",
            sum,
            "average USS per PID",
        ),
        avgrss=(
            "AVGRSS",
            lambda n: int(1.0 * pt[n]["rss"] / pt[n]["pids"])
            if pt[n]["pids"] > 0
            else 0,
            "% 8a",
            sum,
            "average RSS per PID",
        ),
        avgvss=(
            "AVGVSS",
            lambda n: int(1.0 * pt[n]["size"] / pt[n]["pids"])
            if pt[n]["pids"] > 0
            else 0,
            "% 8a",
            sum,
            "average VSS per PID",
        ),
    )
    if config.swappss:
        fields["swappss"] = (
            "SwapPSS",
            lambda n: pt[n]["swappss"],
            "% 8a",
            sum,
            "proportional swapped-out memory",
        )

    columns = getcolumns("map pids avgpss pss", fields, config).split()

    sort = config.sort or "pss"
    showtable(list(pt.keys()), fields, columns, sort, config)


def showusers(config: SmemConfig, proc: ProcessData):
    """Displays memory usage by user.

    It aggregates memory usage for each user and displays it in a table.

    Args:
        config (SmemConfig): The smem2 configuration.
        proc (ProcessData): The ProcessData instance for accessing /proc data.
    """
    ut = get_user_data(proc, config)

    def showuser(u):
        if config.numeric:
            return u
        return ut[u]["name"]

    fields = dict(
        user=(
            "User",
            showuser,
            widthstr("user", config.user_width, 8, config),
            lambda x: len(ut),
            "owner of process",
        ),
        pids=(
            "Count",
            lambda n: len(ut[n]["pids"]),
            "% 5s",
            sum,
            "number of processes",
        ),
        pss=(
            "PSS",
            lambda n: ut[n]["totals"]["pss"],
            "% 8a",
            sum,
            "proportional set size",
        ),
        rss=(
            "RSS",
            lambda n: ut[n]["totals"]["rss"],
            "% 8a",
            sum,
            "resident set size",
        ),
        uss=(
            "USS",
            lambda n: ut[n]["totals"]["uss"],
            "% 8a",
            sum,
            "unique set size",
        ),
        swap=(
            "Swap",
            lambda n: ut[n]["totals"]["swap"],
            "% 8a",
            sum,
            "swapped-out memory",
        ),
        vss=(
            "VSS",
            lambda n: ut[n]["totals"]["size"],
            "% 8a",
            sum,
            "virtual set size",
        ),
    )
    if config.swappss:
        fields["swappss"] = (
            "SwapPSS",
            lambda n: ut[n]["totals"]["swappss"],
            "% 8a",
            sum,
            "proportional swapped-out memory",
        )

    columns = getcolumns("user pids swap uss pss rss", fields, config).split()

    sort = config.sort or "pss"
    showtable(list(ut.keys()), fields, columns, sort, config)


def showcmds(config: SmemConfig, proc: ProcessData):
    """Displays memory usage by command.

    It aggregates memory usage for each unique command and displays it in a table.

    Args:
        config (SmemConfig): The smem2 configuration.
        proc (ProcessData): The ProcessData instance for accessing /proc data.
    """
    ct = get_cmd_data(proc, config)

    fields = dict(
        command=(
            "Command",
            lambda n: ct[n]["name"],
            widthstr("command", config.cmd_width, 27, config),
            lambda x: len(ct),
            "process command line",
        ),
        pids=(
            "PIDs",
            lambda n: len(ct[n]["pids"]),
            "% 5s",
            sum,
            "number of processes",
        ),
        pss=(
            "PSS",
            lambda n: ct[n]["totals"]["pss"],
            "% 8a",
            sum,
            "proportional set size",
        ),
        rss=(
            "RSS",
            lambda n: ct[n]["totals"]["rss"],
            "% 8a",
            sum,
            "resident set size",
        ),
        uss=(
            "USS",
            lambda n: ct[n]["totals"]["uss"],
            "% 8a",
            sum,
            "unique set size",
        ),
        swap=(
            "Swap",
            lambda n: ct[n]["totals"]["swap"],
            "% 8a",
            sum,
            "swapped-out memory",
        ),
        vss=(
            "VSS",
            lambda n: ct[n]["totals"]["size"],
            "% 8a",
            sum,
            "virtual set size",
        ),
    )
    if config.swappss:
        fields["swappss"] = (
            "SwapPSS",
            lambda n: ct[n]["totals"]["swappss"],
            "% 8a",
            sum,
            "proportional swapped-out memory",
        )

    columns = getcolumns("command pids swap uss pss rss", fields, config).split()

    sort = config.sort or "pss"
    showtable(list(ct.keys()), fields, columns, sort, config)


def showsystem(config: SmemConfig, proc: ProcessData):
    """Displays system-wide memory usage.

    It shows a breakdown of memory used by the kernel, userspace, etc.

    Args:
        config (SmemConfig): The smem2 configuration.
        proc (ProcessData): The ProcessData instance for accessing /proc data.
    """
    lines = get_system_data(proc, config)
    fields = dict(
        order=("Order", lambda n: n, "% 2s", lambda x: "", "hierarchical order"),
        area=("Area", lambda n: lines[n][0], "%-24s", None, "memory area"),
        used=("Used", lambda n: lines[n][1], "%10a", sum, "area in use"),
        cache=("Cache", lambda n: lines[n][2], "%10a", sum, "area used as cache"),
        noncache=(
            "Noncache",
            lambda n: lines[n][1] - lines[n][2],
            "%10a",
            sum,
            "area not reclaimable",
        ),
    )

    if config.sysdetail and len(lines) > 0 and len(lines[0]) > 3:
        fields["details"] = (
            "Details",
            lambda n: lines[n][3],
            "%10a",
            sum,
            "Additional metrics",
        )

    columns = getcolumns("area used cache noncache", fields, config).split()
    sort = config.sort or "order"
    showtable(list(range(len(lines))), fields, columns, sort, config)


def parse_arguments(argv=None) -> SmemConfig:
    """Parse command line arguments.

    Args:
        argv (list[str], optional): The list of arguments to parse.
            If None, `sys.argv[1:]` is used. Defaults to None.

    Returns:
        SmemConfig: A configuration object populated with the parsed arguments.
    """

    config = SmemConfig()

    parser = argparse.ArgumentParser(
        prog="smem2",
        description="""
                    smem2 is a tool that can give numerous reports on memory usage on Linux systems.
                    Unlike existing tools, smem2 can report proportional set size (PSS), which is a
                    more meaningful representation of the amount of memory used by libraries and
                    applications in a virtual memory system.
                    """,
        epilog=f"""
               Version: {__version__} -
               for more information please visit:
               https://github.com/slhck/smem2
               """,
    )

    parser.add_argument(
        "-H", "--no-header", action="store_true", help="Disable header line"
    )

    parser.add_argument(
        "-c",
        "--columns",
        default="",
        type=str,
        help="Columns to show, use 'all' to show all columns",
    )

    parser.add_argument(
        "-a",
        "--autosize",
        action="store_true",
        help="Size columns to fit terminal size",
    )

    parser.add_argument(
        "-R", "--realmem", default=None, type=str, help="Amount of physical RAM"
    )

    parser.add_argument(
        "-K", "--kernel", default=None, type=str, help="Path to kernel image"
    )

    parser.add_argument(
        "-b",
        "--basename",
        action="store_true",
        help="Name of executable instead of full command",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress warnings")

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )

    filter_group = parser.add_argument_group("Filter")
    filter_group.add_argument(
        "-P", "--processfilter", default=None, type=str, help="Process filter regex"
    )

    filter_group.add_argument(
        "-M", "--mapfilter", default=None, type=str, help="Process map regex"
    )

    filter_group.add_argument(
        "-U", "--userfilter", default=None, type=str, help="Process users regex"
    )

    filter_group.add_argument(
        "--pid",
        default=None,
        type=int,
        help="Show just process memory based on one pid",
    )

    filter_group.add_argument(
        "-i", "--ignorecase", action="store_true", help="Case insensitive filter"
    )

    show_group = parser.add_argument_group("Show")
    show_group.add_argument(
        "-m", "--mappings", action="store_true", help="Show mappings"
    )

    show_group.add_argument("-u", "--users", action="store_true", help="Show users")

    show_group.add_argument(
        "-w", "--system", action="store_true", help="Show whole system"
    )

    show_group.add_argument(
        "-W", "--sysdetail", action="store_true", help="Show whole system in detail"
    )

    show_group.add_argument(
        "-g",
        "--groupcmd",
        action="store_true",
        help="Show processes grouped by executables",
    )

    show_group.add_argument(
        "-p", "--percent", action="store_true", help="Show percentage"
    )

    show_group.add_argument(
        "-k", "--abbreviate", action="store_true", help="Show unit suffixes"
    )

    show_group.add_argument("-t", "--totals", action="store_true", help="Show totals")
    show_group.add_argument(
        "-T", "--totalsonly", action="store_true", help="Show totals only"
    )

    show_group.add_argument(
        "-F",
        "--format",
        default="raw",
        type=str,
        help="Output format (raw, json)",
    )

    sort_group = parser.add_argument_group("Sort")
    sort_group.add_argument("-n", "--numeric", action="store_true", help="Numeric sort")

    sort_group.add_argument(
        "-s", "--sort", default=None, type=str, help="Field to sort on"
    )

    sort_group.add_argument("-r", "--reverse", action="store_true", help="Reverse sort")

    width_group = parser.add_argument_group("Width")
    width_group.add_argument(
        "--cmd-width",
        default=-1,
        type=int,
        help="Text width for commands (0=as needed)",
    )

    width_group.add_argument(
        "--name-width",
        default=-1,
        type=int,
        help="Text width for command names (0=as needed)",
    )

    width_group.add_argument(
        "--user-width",
        default=-1,
        type=int,
        help="Text width for user names (0=as needed)",
    )

    width_group.add_argument(
        "--mapping-width",
        default=-1,
        type=int,
        help="Text width for mapping names (0=as needed)",
    )

    args = parser.parse_args(argv)
    config.no_header = args.no_header
    config.columns = args.columns or ""
    config.autosize = args.autosize
    config.mappings = args.mappings
    config.users = args.users
    config.system = args.system or args.sysdetail
    config.sysdetail = args.sysdetail
    config.groupcmd = args.groupcmd
    config.percent = args.percent
    config.abbreviate = args.abbreviate
    config.totals = args.totals or args.totalsonly
    config.totalsonly = args.totalsonly
    config.format = args.format
    config.numeric = args.numeric
    config.sort = args.sort
    config.reverse = args.reverse
    config.cmd_width = args.cmd_width
    config.name_width = args.name_width
    config.user_width = args.user_width
    config.mapping_width = args.mapping_width
    config.processfilter = args.processfilter
    config.mapfilter = args.mapfilter
    config.userfilter = args.userfilter
    config.pid = args.pid
    config.ignorecase = args.ignorecase
    config.basename = args.basename
    config.realmem = args.realmem
    config.kernel = args.kernel
    config.quiet = args.quiet

    return config


def main():
    """Main function."""
    try:
        config = parse_arguments()
        proc = Proc()
        process_data = ProcessData(config)
        setdatasources(config, process_data)

        if config.mappings:
            showmaps(config, process_data)
        elif config.users:
            showusers(config, process_data)
        elif config.system:
            showsystem(config, process_data)
        elif config.groupcmd:
            showcmds(config, process_data)
        else:
            showpids(config, process_data)
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
    except IOError as e:
        if e.errno == errno.EPIPE:
            sys.exit(1)
        else:
            raise


if __name__ == "__main__":
    main()
