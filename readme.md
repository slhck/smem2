# smem

**I did not make this software - just trying to improve it**
\<G-dH\>
 * added support for proc/pid/smaps_rollup (big speed boost for nonmapping part)
 * added SwapPss column
 * added TPss column - Pss + SwapPss
 * added group by command mode -g - same executables grouped together
 * added physical RAM size detection via dmidecode
 * added kernel modules size in system view
 * excluded own process from -P filtered output
 * fixed -M filter
 * fixed -R option not accepting argument
 * fixed -K option - kernel compression detection
 * fixed AVGUSS - KeyError: 'uss'
 * removed unneeded --source option

\</G-dH\>

[smem](http://www.selenic.com/smem/) is a tool that can give numerous reports on memory usage on Linux systems. Unlike existing tools, smem can report proportional set size (PSS), which is a more meaningful representation of the amount of memory used by libraries and applications in a virtual memory system.

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

smem has a few requirements:

 * a reasonably modern kernel (> 2.6.27 or so)
 * a reasonably recent version of Python (3.6 or so)
