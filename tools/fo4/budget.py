"""How hard the import may work on this PC: workers sized to its cores and its free memory, and the whole import at
below-normal priority (the PC stays usable while it runs; on a quiet machine it's as fast as before). Players run
this on their own PC, low end included: nothing here assumes a dev box.
  workers(per_gb, most): processes for a step whose workers need about per_gb GB each
"""
import ctypes, os


def free_gb():
    """free physical memory, GB"""
    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 30


def workers(per_gb, most=8):
    """cores less one (one left for the PC), no more than free memory holds (a GB kept back), at least one"""
    cores = max(1, (os.cpu_count() or 2) - 1)
    mem = max(1, int((free_gb() - 1) / per_gb))
    return max(1, min(most, cores, mem))


def roomy():
    """room to run two steps at once (the game's own assets while Fallout's models convert: a WolvenKit process or
    two more, ~2 GB): six cores and 6 GB free at least - a low-end PC runs the steps one after another"""
    return (os.cpu_count() or 2) >= 6 and free_gb() >= 6


def gentle():
    """this process (and the workers it starts, which inherit it) below normal priority - unless HOMESTEAD_PRIORITY
    says normal (tools/import.py, started from the game: the player waits at the main menu for it, the game idling)"""
    if os.environ.get('HOMESTEAD_PRIORITY') != 'normal':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL
