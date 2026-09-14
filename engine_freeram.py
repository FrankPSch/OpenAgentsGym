"""Print free physical memory, for the line between an unload and a load.

Why it is worth a line in every leg's output. On this machine the GPU is
integrated, so "VRAM" is system RAM: offload moves compute, not bytes. Free RAM
is therefore the single number that decides whether the next model loads, runs
from disk, or fails in the allocator -- and it is the number no row records.

What it has already explained, after the fact rather than before:
  - 18 GB of weights against ~8 GB free measured 0.76 tok/s. That figure is SSD
    paging, not inference, and nothing in the row said so.
  - a model left resident by a previous leg made the next one run 2.6x slower.
    The unload exists for that; this line is how you see it worked.

Printed before the load, so the reading is of memory as the next model finds it.

`wmic` is deliberately not used: it is deprecated and absent on current Windows
builds. GlobalMemoryStatusEx is the same figure the Task Manager shows.
"""

import ctypes
import sys


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_gb():
    """(free, total) physical memory in GB, or None where the figure cannot be read.

    Factored out of main() so run_master.py can record the same number in a column rather
    than parse this script's printed line. Never raises: a run must not fail for want of a
    diagnostic, and a blank cell says "not measured", which is the truth in that case.
    """
    if sys.platform != "win32":
        return None
    try:
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None
        gb = 1024.0 ** 3
        return st.ullAvailPhys / gb, st.ullTotalPhys / gb
    except Exception:
        return None


def main():
    reading = free_gb()
    if sys.platform != "win32":
        # Not fatal: the figure is an aid, and a leg must never fail for want of it.
        print("  memory: not available on this platform")
        return 0
    if reading is None:
        print("  memory: could not be read")
        return 0
    free, total = reading
    note = ""
    # 14 GB is devstral's footprint and the largest model that has ever loaded
    # here; 18 GB is the 30B, which has never loaded at 32k context.
    if free < 8:
        note = "  <- too little for any model above 7B; expect paging or an allocator failure"
    elif free < 15:
        note = "  <- enough for the 13-14 GB models, not for 18 GB of weights"
    print("  memory: %.1f GB free of %.1f GB%s" % (free, total, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
