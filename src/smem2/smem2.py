import os
import pwd
import re
import sys
from dataclasses import dataclass, field
from typing import Set


@dataclass
class SmemConfig:
    """Stores the configuration for smem2.

    This dataclass holds all the configuration options for smem2,
    mostly populated from command-line arguments.
    """

    # from parse_arguments
    no_header: bool = False
    columns: str = ""
    autosize: bool = False
    realmem: str | None = None
    kernel: str | None = None
    basename: bool = False
    quiet: bool = False
    processfilter: str | None = None
    mapfilter: str | None = None
    userfilter: str | None = None
    pid: int | None = None
    ignorecase: bool = False
    mappings: bool = False
    users: bool = False
    system: bool = False
    sysdetail: bool = False
    groupcmd: bool = False
    percent: bool = False
    abbreviate: bool = False
    totals: bool = False
    totalsonly: bool = False
    format: str = "raw"
    numeric: bool = False
    sort: str | None = None
    reverse: bool = False
    cmd_width: int = -1
    name_width: int = -1
    user_width: int = -1
    mapping_width: int = -1

    # from setdatasources and other globals
    # these are not set by user but determined at runtime
    rssdetail: bool = False
    pssdetail: bool = True
    rollup: bool = True
    swappss: bool = False
    ownpid: int = 0
    ignore_autosize: Set[str] = field(default_factory=set)


class UIDCache(object):
    """A cache for user ID to username mappings.

    This class avoids repeated lookups of UIDs by caching the results.
    """

    def __init__(self):
        """Initializes the UIDCache."""
        self._cache = {}

    def __call__(self, uid):
        """Retrieves the username for a given UID, populating the cache if necessary.

        Args:
            uid (int): The user ID to look up.

        Returns:
            str: The username associated with the UID.
        """
        return self._cache.setdefault(uid, self._getpwuid(uid))

    @staticmethod
    def _getpwuid(uid):
        """Gets the username for a UID.

        Args:
            uid (int): The user ID.

        Returns:
            str: The username, or the UID as a string if the lookup fails.
        """
        try:
            return pwd.getpwuid(uid)[0]
        except KeyError:
            return str(uid)


class Proc(object):
    """Helper class to handle /proc/ filesystem data"""

    def __init__(self):
        """Initializes the Proc helper."""
        pass

    @staticmethod
    def listdir():
        """Lists the contents of /proc.

        Returns:
            list[str]: A list of filenames in /proc.
        """
        return os.listdir("/proc")

    @staticmethod
    def read(filename):
        """Reads a file from the /proc filesystem.

        Args:
            filename (str): The name of the file in /proc to read.

        Returns:
            str: The content of the file.

        Raises:
            RuntimeError: If the file does not exist.
        """
        if not os.path.exists("/proc/" + filename):
            raise RuntimeError(
                f"File /proc/{filename} does not exist, are you sure you are running on a Linux system?"
            )
        return open("/proc/" + filename).read()

    def readlines(self, filename):
        """Reads a file from /proc and splits it into lines.

        Args:
            filename (str): The name of the file in /proc to read.

        Returns:
            list[str]: A list of lines from the file.
        """
        return self.read(filename).splitlines(True)

    def version(self):
        """Gets the Linux kernel version string.

        Returns:
            str: The first line of /proc/version.
        """
        return self.readlines("version")[0]


class MemData(Proc):
    """Class accessing and storing /proc/meminfo data"""

    def __init__(self):
        """Initializes MemData and parses /proc/meminfo."""
        self._memdata = {}

        regex = re.compile("(?P<name>\\S+):\\s+(?P<amount>\\d+) kB")
        for line in self.readlines("meminfo"):
            match = regex.match(line)
            if match:
                self._memdata[match.group("name").lower()] = int(match.group("amount"))

    def __call__(self, entry):
        """Retrieves a value from the stored meminfo data.

        Args:
            entry (str): The key for the meminfo data to retrieve (e.g., 'memtotal').

        Returns:
            int: The value from /proc/meminfo in kilobytes.
        """
        return self._memdata[entry]


class ProcessData(Proc):
    """Helper class to handle /proc/<pid> filesystem data"""

    def __init__(self, config: SmemConfig):
        """Initializes ProcessData.

        Args:
            config (SmemConfig): The smem2 configuration.
        """
        self._uidcache = UIDCache()
        self.config = config

    def _iskernel(self, pid):
        """Checks if a process ID belongs to a kernel thread.

        Kernel threads have an empty command line.

        Args:
            pid (str): The process ID.

        Returns:
            bool: True if the PID is a kernel thread, False otherwise.
        """
        return self.pidcmd(pid) == ""

    @staticmethod
    def _stat(pid):
        """Gets the stat result for a process.

        Args:
            pid (str): The process ID.

        Returns:
            os.stat_result: The result of os.stat() on /proc/<pid>.
        """
        return os.stat("/proc/" + pid)

    def pids(self):
        """Gets a list of process IDs.

        Filters the list based on the configuration (e.g., specific PID).
        Excludes kernel threads and the smem2 process itself if a filter is active.

        Returns:
            list[int]: A list of process IDs.
        """
        return [
            int(e)
            for e in self.listdir()
            if e.isdigit()
            and not self._iskernel(e)
            and ((self.config.pid and self.config.pid == int(e)) or not self.config.pid)
            and not ((int(e) == self.config.ownpid) and self.config.processfilter)
        ]
        # exclude own process when processfilter

    def mapdata(self, pid):
        """Gets the smaps data for a process.

        It prefers using smaps_rollup for performance if available and configured.

        Args:
            pid (str): The process ID.

        Returns:
            list[str]: The lines from the smaps or smaps_rollup file, or an empty list on error.
        """
        if self.config.rollup:
            try:
                return self.readlines(
                    "%s/smaps_rollup" % pid
                )  # smaps_rollup new from kernel 4.14, at least 7x faster for non maping listing
            except Exception:
                pass
        try:
            return self.readlines("%s/smaps" % pid)
        except (RuntimeError, PermissionError):
            return []

    def pidcmd(self, pid):
        """Gets the command line for a process.

        Args:
            pid (str): The process ID.

        Returns:
            str: The command line of the process, or '?' on error.
        """
        try:
            c = self.read("%s/cmdline" % pid)[:-1]
            c = c.replace("\0", " ")
            if self.config.basename and not c == "":
                c = os.path.basename(c.split()[0])
            return c
        except Exception:
            return "?"

    def piduser(self, pid):
        """Gets the UID of the process owner.

        Args:
            pid (str): The process ID.

        Returns:
            int: The user ID of the process owner, or -1 on error.
        """
        try:
            return self._stat("%d" % pid).st_uid
        except Exception:
            return -1

    def username(self, uid):
        """Gets the username for a UID.

        Args:
            uid (int): The user ID.

        Returns:
            str: The username, or '?' if the UID is -1.
        """
        return "?" if uid == -1 else self._uidcache(uid)

    def pidusername(self, pid):
        """Gets the username of the process owner.

        Args:
            pid (int or str): The process ID.

        Returns:
            str: The username of the process owner.
        """
        return self.username(self.piduser(pid))

    def pidtostr(self, pid):
        """Converts a PID to a string.

        Args:
            pid (int): The process ID.

        Returns:
            str: The process ID as a string.
        """
        return str(pid)

    def pidname(self, pid):
        """Gets the process name (from /proc/<pid>/comm).

        Args:
            pid (str): The process ID.

        Returns:
            str: The name of the process, or '?' on error.
        """
        try:
            return self.read("%s/comm" % pid)[:-1]
        except Exception:
            return "?"


def totalmem(config: SmemConfig):
    """Calculates the total memory to be used as a reference for percentages.

    It can be based on real memory from dmidecode, a user-provided value,
    or the 'MemTotal' value from /proc/meminfo.

    Args:
        config (SmemConfig): The smem2 configuration.

    Returns:
        int: The total memory in kilobytes.
    """
    if config.realmem:
        return fromunits(config.realmem) / 1024
    else:
        if config.system or config.sysdetail:
            try:
                # only for systems running directly on HW
                ram = (
                    os.popen(
                        "dmidecode --type memory 2> /dev/null|awk '/Size: [0-9]+ MB/{sum+=$2};END{print sum}'",
                    )
                    .read()
                    .strip()
                )
                if ram.isdigit():
                    return fromunits(str(int(ram)) + "M") / 1024
            except Exception:
                pass

        return MemData()("memtotal")


def pidmaps(pid, proc: ProcessData, config: SmemConfig, nomaps=False):
    """Parses the memory maps for a given process.

    It reads /proc/<pid>/smaps or /proc/<pid>/smaps_rollup to get memory
    usage information for each mapping.

    Args:
        pid (int or str): The process ID.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.
        nomaps (bool, optional): If True, only read the first mapping entry,
            used for feature detection. Defaults to False.

    Returns:
        dict: A dictionary of memory mappings, where keys are start addresses.
    """
    maps: dict = {}
    start = None
    status = None
    if config.rollup or config.pssdetail or config.rssdetail:
        try:
            status = proc.readlines("%s/status" % pid)
        except (RuntimeError, PermissionError):
            status = None

    for l in proc.mapdata(pid):
        f = l.split()
        if f[-1] == "kB":
            maps[start][f[0][:-1].lower()] = int(f[1])
        elif "-" in f[0] and ":" not in f[0]:  # looks like a mapping range
            start, end = f[0].split("-")
            start = int(start, 16)
            name = "<anonymous>"
            if len(f) > 5:
                name = f[5]
                if config.basename:
                    name = os.path.basename(name)
            maps[start] = dict(
                end=int(end, 16),
                perm=f[1],
                offset=int(f[2], 16),
                major=int(f[3].split(":")[0], 16),
                minor=int(f[3].split(":")[1], 16),
                inode=int(f[4]),
                name=name,
                pss=0,
                rss=0,
                uss=0,
                swap=0,
                swappss=0,
                pcent=0,
                size=0,
            )
            if config.pssdetail:
                (
                    maps[start]["pss_anon"],
                    maps[start]["pss_file"],
                    maps[start]["pss_shmem"],
                ) = (0, 0, 0)

            # for nomaps mode: stop reading mappings
            if nomaps:
                break

    # add pss, rss, uss if available from smaps
    if not config.rollup:
        if not config.pssdetail:
            for m in maps:
                maps[m]["uss"] = maps[m].get("private_clean", 0) + maps[m].get(
                    "private_dirty", 0
                )
                maps[m]["pss"] = maps[m]["uss"] + maps[m].get("shared_clean", 0) / 2
                maps[m]["rss"] = maps[m].get("shared_clean", 0) + maps[m].get(
                    "shared_dirty", 0
                )
        if config.rssdetail and status:
            # from /proc/pid/status
            for s in status:
                if "RssAnon" in s:
                    maps[start]["rss_anon"] = int(s.split()[1])
                elif "RssFile" in s:
                    maps[start]["rss_file"] = int(s.split()[1])
                elif "RssShmem" in s:
                    maps[start]["rss_shmem"] = int(s.split()[1])

        # Parse VmSize for VSS calculation
        if status:
            for s in status:
                if "VmSize:" in s:
                    # Set size for the last mapping (rollup case) or all mappings
                    if config.rollup and start:
                        maps[start]["size"] = int(s.split()[1])
                    else:
                        # For non-rollup, distribute VmSize across all mappings
                        total_size = int(s.split()[1])
                        if maps:
                            size_per_map = (
                                total_size // len(maps) if len(maps) > 0 else 0
                            )
                            for m in maps:
                                maps[m]["size"] = size_per_map
                    break

    # Apply mapfilter if specified
    if config.mapfilter and not nomaps:
        f = {}
        for m in maps:
            if not filters(config.mapfilter, m, config, lambda x: maps[x]["name"]):
                f[m] = maps[m]
        return f
    return maps


def maptotals(pids, proc: ProcessData, config: SmemConfig):
    """Aggregates memory usage data for a list of pids, including map details.

    For each process, it gets memory totals (PSS, RSS, USS, etc.) and
    detailed mapping information. It applies process and user filters.

    Args:
        pids (list[int]): A list of process IDs.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary where keys are process IDs and values are dictionaries
              containing memory totals and mapping details for each process.
    """
    pt: dict = {}
    for p in pids:
        if filters(
            config.processfilter, p, config, proc.pidcmd, proc.pidtostr, proc.pidname
        ) or filters(config.userfilter, p, config, proc.pidusername):
            continue
        maps = pidmaps(p, proc, config)
        if maps:
            pt[p] = {}
            pt[p]["maps"] = maps
            totals = pidtotals(p, proc, config)
            # Flatten the totals into the main dict for compatibility with display code
            pt[p].update(totals)
    return pt


def pidtotals(pid, proc: ProcessData, config: SmemConfig):
    """Calculates the total memory usage (PSS, RSS, USS, etc.) for a single process.

    It sums up the values from all memory mappings of the process.

    Args:
        pid (int or str): The process ID.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary with total PSS, RSS, USS, Swap, etc., for the process.
    """
    totals: dict = {}
    maps = pidmaps(pid, proc, config)
    if maps:
        maplist = maps.values()
        totals["pss"] = sum([m.get("pss", 0) for m in maplist])
        totals["rss"] = sum([m.get("rss", 0) for m in maplist])
        private_clean = sum(m.get("private_clean", 0) for m in maplist)
        private_dirty = sum(m.get("private_dirty", 0) for m in maplist)
        totals["uss"] = private_clean + private_dirty
        totals["swap"] = sum([m.get("swap", 0) for m in maplist])
        totals["size"] = sum([m.get("size", 0) for m in maplist])
        totals["maps"] = len(maps)
        if config.swappss:
            totals["swappss"] = sum([m.get("swappss", 0) for m in maplist])
        if config.pssdetail:
            totals["pss_anon"] = sum([m.get("pss_anon", 0) for m in maplist])
            totals["pss_file"] = sum([m.get("pss_file", 0) for m in maplist])
            totals["pss_shmem"] = sum([m.get("pss_shmem", 0) for m in maplist])
        if config.rssdetail:
            totals["rss_anon"] = sum([m.get("rss_anon", 0) for m in maplist])
            totals["rss_file"] = sum([m.get("rss_file", 0) for m in maplist])
            totals["rss_shmem"] = sum([m.get("rss_shmem", 0) for m in maplist])
    return totals


def usertotals(pids, proc: ProcessData, config: SmemConfig):
    """Aggregates memory usage by user.

    It groups processes by user and calculates the total memory usage for each user.

    Args:
        pids (list[int]): A list of process IDs to analyze.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary where keys are user IDs and values are dictionaries
              containing process lists and memory totals for each user.
    """
    ut: dict = {}
    for p in pids:
        if filters(
            config.processfilter, p, config, proc.pidcmd, proc.pidtostr, proc.pidname
        ) or filters(config.userfilter, p, config, proc.pidusername):
            continue
        u = proc.piduser(p)
        if u not in ut:
            ut[u] = {"pids": [], "name": "?"}
            ut[u]["name"] = proc.username(u)
        ut[u]["pids"].append(p)

    # get totals per user
    for u in ut:
        ut[u]["totals"] = processtotals(ut[u]["pids"], proc, config)
    return ut


def cmdtotals(pids, proc: ProcessData, config: SmemConfig):
    """Aggregates memory usage by command line.

    It groups processes by their command line and calculates the total memory
    usage for each command.

    Args:
        pids (list[int]): A list of process IDs to analyze.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary where keys are command lines and values are
              dictionaries containing process lists and memory totals.
    """
    # totals per command
    ct: dict = {}

    for p in pids:
        if filters(
            config.processfilter, p, config, proc.pidcmd, proc.pidtostr, proc.pidname
        ) or filters(config.userfilter, p, config, proc.pidusername):
            continue
        cmdline = proc.pidcmd(p)
        if not cmdline:
            continue

        parts = cmdline.split()
        if not parts:
            continue
        c = parts[0]

        # if multiple processes per command, then a list of pids
        if c in ct:
            ct[c]["pids"].append(p)
        else:
            # first pid for this command
            ct[c] = {"pids": [p]}

    # get totals per command
    for c in ct:
        ct[c]["totals"] = processtotals(ct[c]["pids"], proc, config)
        if "totals" in ct[c] and ct[c]["totals"]:
            ct[c]["name"] = c
            ct[c]["user"] = proc.pidusername(ct[c]["pids"][0])

    # remove commands with empty totals
    for c in list(ct.keys()):
        if "totals" not in ct[c] or not ct[c]["totals"]:
            del ct[c]
    return ct


def sortmaps(totals, key):
    """Sorts a dictionary of totals by a given key.

    Args:
        totals (dict): A dictionary where values are another dictionary
                       containing a 'totals' key.
        key (str): The key within the nested 'totals' dictionary to sort by.

    Returns:
        list: A sorted list of the input dictionary's values.
    """
    # sort by key
    return sorted(totals.values(), key=lambda x: x["totals"][key], reverse=True)


def units(x):
    """Converts a value in bytes to a human-readable string with units (K, M, G).

    Args:
        x (int or float): The value in bytes.

    Returns:
        str: A human-readable string representation of the value.
    """
    if x > 1024 * 1024 * 1024:
        return "%.1fG" % (x / (1024.0 * 1024 * 1024))
    if x > 1024 * 1024:
        return "%.1fM" % (x / (1024.0 * 1024))
    if x > 1024:
        return "%.1fK" % (x / 1024.0)
    return str(x)


def fromunits(x):
    """Converts a human-readable string with units (K, M, G, etc.) to bytes.

    Args:
        x (str): The string with a value and unit (e.g., "1024M").

    Returns:
        int: The value in bytes.

    Raises:
        SystemExit: If the unit is not recognized.
    """
    s = dict(
        k=2**10,
        K=2**10,
        kB=2**10,
        KB=2**10,
        M=2**20,
        MB=2**20,
        G=2**30,
        GB=2**30,
        T=2**40,
        TB=2**40,
    )
    for k, v in list(s.items()):
        if x.endswith(k):
            return int(float(x[: -len(k)]) * v)
    sys.stderr.write("Memory size should be written with units, for example 1024M\n")
    sys.exit(-1)


def processtotals(pids, proc: ProcessData, config: SmemConfig):
    """Sums up memory usage totals for a list of processes.

    Args:
        pids (list[int]): The list of process IDs.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary with the summed PSS, RSS, USS, etc., for the
              given processes.
    """
    # Sums up totals of a pid list
    t = {"uss": 0, "pss": 0, "rss": 0, "swap": 0, "size": 0}
    if config.swappss:
        t["swappss"] = 0
    for p in pids:
        pt = pidtotals(p, proc, config)
        if pt:
            for k in t:
                if k in pt:
                    t[k] += pt[k]
    return t


def get_process_data(proc: ProcessData, config: SmemConfig):
    """Collects and returns memory usage data for each process.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary containing memory data for each process,
              as returned by maptotals.
    """
    # Collect process data
    pids = proc.pids()
    data = maptotals(pids, proc, config)
    return data


def get_map_data(proc: ProcessData, config: SmemConfig):
    """Collects and returns memory usage data aggregated by mapping name.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary containing memory data aggregated by mapping name.
    """
    # Collect map data - aggregate by mapping name
    pids = proc.pids()
    data = mapnametotals(pids, proc, config)
    return data


def mapnametotals(pids, proc: ProcessData, config: SmemConfig):
    """Aggregates memory usage by mapping name across a list of processes.

    It iterates through processes and their memory maps, summing up memory
    statistics for each unique mapping name.

    Args:
        pids (list[int]): A list of process IDs.
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary where keys are mapping names and values are
              dictionaries of aggregated memory statistics.
    """
    totals: dict = {}
    for pid in pids:
        # Apply filters like the original version
        if filters(
            config.processfilter, pid, config, proc.pidcmd, proc.pidtostr, proc.pidname
        ) or filters(config.userfilter, pid, config, proc.pidusername):
            continue
        try:
            maps = pidmaps(pid, proc, config)
            seen = {}
            for m in list(maps.keys()):
                name = maps[m]["name"]
                if name not in totals:
                    t = dict(
                        size=0,
                        rss=0,
                        pss=0,
                        shared_clean=0,
                        shared_dirty=0,
                        private_clean=0,
                        count=0,
                        private_dirty=0,
                        referenced=0,
                        swap=0,
                        pids=0,
                    )
                    if config.swappss:
                        t["swappss"] = 0
                else:
                    t = totals[name]
                for k in t:
                    t[k] += maps[m].get(k, 0)
                t["count"] += 1
                if name not in seen:
                    t["pids"] += 1
                    seen[name] = 1
                totals[name] = t
        except (OSError, IOError):
            continue
    return totals


def get_user_data(proc: ProcessData, config: SmemConfig):
    """Collects and returns memory usage data aggregated by user.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary containing memory data aggregated by user.
    """
    # Collect user data
    pids = proc.pids()
    data = usertotals(pids, proc, config)
    return data


def get_cmd_data(proc: ProcessData, config: SmemConfig):
    """Collects and returns memory usage data aggregated by command.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        dict: A dictionary containing memory data aggregated by command.
    """
    # Collect cmd data
    pids = proc.pids()
    data = cmdtotals(pids, proc, config)
    return data


def get_system_data(proc: ProcessData, config: SmemConfig):
    """Collects and returns system-wide memory usage data.

    This provides a breakdown of memory usage by different system components
    like kernel, firmware, userspace, etc.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        list[tuple]: A list of tuples, where each tuple represents a memory
                     area and its usage in PSS and RSS.
    """
    t = totalmem(config)
    m = MemData()
    mt = m("memtotal")
    f = m("memfree")
    kernel = kernelsize(config)

    # total amount mapped into userspace (ie mapped an unmapped pages) /dev/zero mappings
    u = m("anonpages") + m("mapped")

    # total amount used by hardware
    fh = int(max(t - mt - kernel, 0))

    # total amount allocated by kernel not for userspace
    kd = mt - f - u

    # total amount in kernel caches
    kdc = m("buffers") + m("sreclaimable") + m("cached") - m("mapped")

    if config.sysdetail:
        shmp = mapshared(proc, config)  # shared memory mapped by processes
        mapzero = mapdevzero(
            proc, config
        )  # dev/zero mapped as files should be subtracted from files Mapped from userspace
        mapped = m("mapped") - mapzero
        modules = kernelmodsize(proc, config)
        shm = m("shmem") - shmp

        mounts = proc.readlines("mounts")
        ramfs = 0
        for r in mounts:
            if "ramfs" in r:
                try:
                    ramfs += int(
                        (os.popen("du -sk %s" % r.split()[1]).read()).split()[0]
                    )
                except Exception:
                    pass
        filecache = m("cached") - mapped - shm - ramfs
        unknown = (
            mt
            - f
            - u
            - (
                modules
                + m("pagetables")
                + m("kernelstack")
                + m("slab")
                + m("buffers")
                + filecache
                + shm
                + ramfs
            )
        )
        if unknown < 0:
            unknown = 0

    lines: list[tuple]
    if config.sysdetail:
        lines = [
            ("firmware/hardware", fh, 0, 0),
            ("kernel image", kernel, 0, 0),
            ("kernel modules", modules, 0, 0),
            ("page tables", m("pagetables"), 0, 0),
            ("kernel stack", m("kernelstack"), 0, 0),
            ("slab (all/SReclaimable)", m("slab"), m("sreclaimable"), 0),
            ("buffers", m("buffers"), m("buffers"), 0),
            ("cached (w/o mapped,tmpfs,ramfs)", filecache, filecache, 0),
            ("shared (non process tmpfs)", shm, 0, 0),
            ("ramfs", ramfs, 0, 0),
            ("unknown", unknown, 0, 0),
            ("processes (all/mapped files)", u, mapped, 0),
            ("free memory", f, f, 0),
        ]
        if "all" in config.columns or "details" in config.columns:
            line_all: list[tuple] = [
                ("-------------------------------", 0, 0, 0),
                ("/dev/zero mapped", 0, 0, mapzero),
                ("shared by processes", 0, 0, shmp),
                ("unevictable", 0, 0, m("unevictable")),
                ("dirty (unwritten to file)", 0, 0, m("dirty")),
                ("swapped", 0, 0, m("swaptotal") - m("swapfree")),
                ("available (estimated)", 0, 0, m("memavailable")),
            ]
            lines = lines + line_all
    else:
        lines = [
            ("firmware/hardware", fh, 0),
            ("kernel image", kernel, 0),
            ("kernel dynamic memory", kd, kdc),
            ("userspace memory", u, m("mapped")),
            ("free memory", f, f),
        ]
    return lines


def mapdevzero(proc: ProcessData, config: SmemConfig):
    """Calculates memory mapped to /dev/zero.

    Some Linux versions count memory mapped to /dev/zero as 'Mapped' instead
    of 'AnonPages'. This function calculates that amount.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        int: Total PSS of memory mapped to /dev/zero, in kilobytes.
    """
    ps = proc.pids()
    config.mapfilter = "^/dev/zero$"
    pt = maptotals(ps, proc, config)
    t = 0.0
    for r in pt:
        t += pt[r]["pss"]
    return int(t)


def mapshared(proc: ProcessData, config: SmemConfig):
    """Calculates memory shared by multiple processes (via SYSV IPC).

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        int: Total PSS of memory from SYSV shared segments, in kilobytes.
    """
    ps = proc.pids()
    config.mapfilter = "^/SYSV*"
    pt = maptotals(ps, proc, config)
    t = 0.0
    for r in pt:
        t += pt[r]["pss"]
    return int(t)


def kernelsize(config: SmemConfig):
    """Determines the size of the kernel image from the file specified.

    Args:
        config (SmemConfig): The smem2 configuration.

    Returns:
        int: The kernel image size in kilobytes.
    """
    kernelsize_val = 0
    if config.kernel:
        try:
            d = os.popen("size %s" % config.kernel).readlines()[1].split()
            if int(d[1]) == 0:  # data part missing, seems like packed file
                # try some heuristic to find gzipped part in kernel image
                with open(config.kernel, "rb") as f:
                    packedkernel = f.read()
                pos = packedkernel.find(b"\x1f\x8b")
                if pos >= 0 and pos < 25000:
                    if not config.quiet:
                        sys.stderr.write(
                            "Parameter '%s' should be an original uncompressed compiled kernel file.\n"
                            % config.kernel
                        )
                        sys.stderr.write(
                            "Maybe uncompressed kernel can be extracted by the command:\n"
                            "  dd if=%s bs=1 skip=%d | gzip -d >%s.unpacked\n\n"
                            % (config.kernel, pos, config.kernel)
                        )
            else:
                kernelsize_val = int(int(d[3]) / 1024 + 0.5)
        except Exception:
            pass  # Fail silently if size command fails or kernel file is not found
    return kernelsize_val


def kernelmodsize(proc: ProcessData, config: SmemConfig):
    """Calculates the total size of loaded kernel modules.

    It reads /proc/modules to get the size of each module.

    Args:
        proc (ProcessData): The ProcessData instance.
        config (SmemConfig): The smem2 configuration.

    Returns:
        int: The total size of kernel modules in kilobytes.
    """
    ms = 0.0
    try:
        md = proc.readlines("modules")
        for m in md:
            ms += int(m.split()[1])
        ms /= 1024
    except Exception:
        if not config.quiet:
            sys.stderr.write("Detection of kernel modules size failed\n")
    return int(ms)


def setdatasources(config: SmemConfig, proc: ProcessData):
    """Detects kernel features and updates the configuration accordingly.

    It checks for support of PSS, SwapPSS, and detailed PSS/RSS reporting
    by inspecting the smaps of the current process. It also determines if
    the faster smaps_rollup can be used.

    Args:
        config (SmemConfig): The smem2 configuration object to update.
        proc (ProcessData): The ProcessData instance.

    Returns:
        SmemConfig: The updated configuration object.
    """
    """New kernel features detection"""
    config.ownpid = os.getpid()

    config.rssdetail = False
    config.pssdetail = True
    config.rollup = True
    rd = proc.readlines("%s/status" % config.ownpid)
    for r in rd:
        if "RssAnon:" in r:
            config.rssdetail = True
            break

    map_data = pidmaps(config.ownpid, proc, config, nomaps=True)
    map_data = map_data[list(map_data.keys())[0]]

    if "pss" not in map_data and not config.quiet:
        sys.stderr.write("Warning: Kernel does not appear to support PSS measurement\n")

    if "swappss" in map_data:
        config.swappss = True
    else:
        config.swappss = False
        if not config.quiet:
            sys.stderr.write(
                "Warning: Kernel does not appear to support SwapPSS measurement\n"
            )

    if "pss_anon" in map_data:
        config.pssdetail = True
    else:
        config.pssdetail = False
        if not config.quiet:
            sys.stderr.write(
                "Warning: Kernel does not appear to support Pss Anon/File/Shmem measurement\n"
            )

    """ some smem2 features need full smaps"""
    if (
        config.mapfilter
        or config.mappings
        or "maps" in config.columns
        or ("all" in config.columns and not config.groupcmd)
    ):
        config.rollup = False
    return config


def filters(opt, arg, config: SmemConfig, *sources):
    """A generic filter function based on regular expressions.

    It checks if a given argument should be filtered out by matching a regex
    against one or more source strings.

    Args:
        opt (str or None): The regex pattern to search for. If None or empty,
            the function returns False.
        arg: The argument to pass to the source functions (e.g., a PID).
        config (SmemConfig): The smem2 configuration (for ignorecase flag).
        *sources (callable): Variable length list of functions that take `arg`
            and return a string to be searched.

    Returns:
        bool: True if the item should be filtered out (no match found),
              False otherwise (a match was found or no filter is active).
    """
    if not opt:
        return False
    for f in sources:
        if re.search(opt, f(arg), re.I if config.ignorecase else 0):
            return False
    return True
