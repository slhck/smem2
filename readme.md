# smem

**I did not make this software - just will try to improve it**

ToDo:
  *add support for proc/pid/smaps_rollup (big speed boost for nonmaping part)
  *add SwapPss
  *add group by command mode for grouped top lists
  *add TPss column - Pss + SwapPss to get all prportional sum
  *exclude own process from listing
  


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
