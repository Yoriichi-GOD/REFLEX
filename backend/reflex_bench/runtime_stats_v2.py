"""Read actual process working-set/RAM without extra binary dependencies."""
import ctypes
import os
from pathlib import Path


def memory_snapshot():
    if os.name=="nt":
        from ctypes import wintypes
        size=ctypes.c_size_t
        class Counters(ctypes.Structure):
            _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[(n,size) for n in
                ("PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage",
                 "QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage")]
        class Status(ctypes.Structure):
            _fields_=[("dwLength",wintypes.DWORD),("dwMemoryLoad",wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in
                ("ullTotalPhys","ullAvailPhys","ullTotalPageFile","ullAvailPageFile","ullTotalVirtual","ullAvailVirtual","ullAvailExtendedVirtual")]
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        psapi=ctypes.WinDLL("psapi",use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        status=Status();status.dwLength=ctypes.sizeof(status)
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):raise ctypes.WinError(ctypes.get_last_error())
        return {"rss_bytes":int(counters.WorkingSetSize),"peak_rss_bytes":int(counters.PeakWorkingSetSize),"ram_bytes":int(status.ullTotalPhys)}
    import resource
    status=Path("/proc/self/status").read_text()
    rss=int(next(line.split()[1] for line in status.splitlines() if line.startswith("VmRSS:")))*1024
    return {"rss_bytes":rss,"peak_rss_bytes":int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024,
            "ram_bytes":os.sysconf("SC_PAGE_SIZE")*os.sysconf("SC_PHYS_PAGES")}
