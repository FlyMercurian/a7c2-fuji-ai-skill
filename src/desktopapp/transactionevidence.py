"""Offline evidence predicates shared by the desktop and portable guide."""


def running_camera_processes():
    """List relevant Windows processes without enumerating USB or starting tools."""
    import ctypes
    from ctypes import wintypes
    import os
    if os.name != 'nt':
        raise ValueError('进程结束核对当前仅支持 Windows；不自动解除历史阻塞。')
    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('pid', wintypes.DWORD), ('heap', ctypes.c_size_t),
                    ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG),
                    ('flags', wintypes.DWORD), ('name', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), '无法核对后台进程，保留阻塞。')
    result, entry = [], Entry()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        found = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while found:
            if entry.pid != os.getpid() and entry.name.lower() in {
                    'a7c2guide.exe', 'a7c2tools.exe', 'wdi-simple.exe', 'zadig.exe'}:
                result.append(dict(pid=entry.pid, name=entry.name))
            found = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise OSError(ctypes.get_last_error(), '进程核对不完整，保留阻塞。')
    finally:
        kernel.CloseHandle(handle)
    return result


def read_only_failure(state):
    """Only retry a failure with evidence that persistent writing never began."""
    if state.get('phase') != 'NEEDS_REVIEW' or state.get('failed_during') not in ('READING', 'PLANNED', 'PREFLIGHT_VERIFIED'):
        return False
    events = state.get('journal', [])
    if any(e.get('event') == 'native_intent' and e.get('mode') in (1, 2, 3) for e in events):
        return False
    stages = [i for i, e in enumerate(events) if e.get('event') == 'native_stage_intent']
    for n, index in enumerate(stages):
        stop = stages[n + 1] if n + 1 < len(stages) else len(events)
        if not any(e.get('event') == 'native_cleanup_verified' for e in events[index + 1:stop]):
            return False
    return True
