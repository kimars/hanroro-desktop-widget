"""Window snapshots keep every window, cache process identities and avoid repeated COM calls."""
import ctypes,os,sys,time
from pathlib import Path
_cache={};_appids={}

def visible_windows():
    if sys.platform!='win32':return {'paths':set(),'rows':[]}
    from ctypes import wintypes
    from app_windows import _process_path,_window_app_id,_window_property_id
    u=ctypes.WinDLL('user32');k=ctypes.WinDLL('kernel32');dwm=ctypes.WinDLL('dwmapi')
    u.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT];u.GetWindow.restype=wintypes.HWND;u.IsWindowVisible.argtypes=[wintypes.HWND];u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];u.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];u.IsIconic.argtypes=[wintypes.HWND]
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE];k.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];k.GetApplicationUserModelId.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.UINT),wintypes.LPWSTR];dwm.DwmGetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
    paths=set();rows=[];live_pids=set();live_hwnds=set();now=time.monotonic();callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback
    def visit(hwnd,_):
        ex=u.GetWindowLongW(hwnd,-20)
        if not u.IsWindowVisible(hwnd) or ex&0x80 or (u.GetWindow(hwnd,4) and not ex&0x40000):return True
        cloaked=wintypes.DWORD()
        if dwm.DwmGetWindowAttribute(hwnd,14,ctypes.byref(cloaked),4)==0 and cloaked.value:return True
        text=ctypes.create_unicode_buffer(256)
        if not u.GetWindowTextW(hwnd,text,256):return True
        pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if not pid.value or pid.value==os.getpid():return True
        live_pids.add(pid.value);live_hwnds.add((int(hwnd),pid.value));cached=_cache.get(pid.value)
        if not cached or now-cached[0]>60:
            process=k.OpenProcess(0x1000,False,pid.value)
            if not process:return True
            try:cached=(now,_process_path(k,process),_window_app_id(k,process));_cache[pid.value]=cached
            finally:k.CloseHandle(process)
        path,appid=cached[1:]
        if not path:return True
        identity=(int(hwnd),pid.value)
        if identity not in _appids:_appids[identity]=_window_property_id(hwnd) or appid
        appid=_appids[identity];target='app:'+appid if appid else path
        paths.add(path.casefold());paths.add(target.casefold());rows.append({'hwnd':int(hwnd),'pid':pid.value,'name':text.value,'path':path,'target':target,'kind':'running','minimized':bool(u.IsIconic(hwnd))});return True
    u.EnumWindows.argtypes=[callback,wintypes.LPARAM];u.EnumWindows(visit,0)
    for pid in list(_cache):
        if pid not in live_pids:del _cache[pid]
    for identity in list(_appids):
        if identity not in live_hwnds:del _appids[identity]
    return {'paths':paths,'rows':rows}

def select_window(row):
    if sys.platform!='win32':return False
    from ctypes import wintypes
    u=ctypes.WinDLL('user32');u.IsWindow.argtypes=[wintypes.HWND];u.IsIconic.argtypes=[wintypes.HWND];u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];u.GetForegroundWindow.restype=wintypes.HWND;u.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int];u.SetForegroundWindow.argtypes=[wintypes.HWND]
    hwnd=int(row['hwnd']);pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if not u.IsWindow(hwnd) or pid.value!=int(row['pid']):return False
    if int(u.GetForegroundWindow() or 0)==hwnd and not u.IsIconic(hwnd):u.ShowWindow(hwnd,6)
    else:u.ShowWindow(hwnd,9);u.SetForegroundWindow(hwnd)
    return True
