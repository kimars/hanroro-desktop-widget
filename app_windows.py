"""Bring an already-running Windows app forward, or minimize it when toggled again."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import ntpath
import threading
import uuid
from ctypes import wintypes
from pathlib import Path

SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
APPMODEL_ERROR_NO_APPLICATION = 15703
_shortcut_cache: dict[str, str] = {}
_app_shortcuts: dict[str,str] = {}
_launch_times: dict[str,float] = {}
_warm_started=False

def register_app_shortcuts(rows):
    for row in rows:
        if row.get('target','').startswith('app:') and row.get('path','').lower().endswith('.lnk'):
            _app_shortcuts[row['target'][4:].casefold()]=row['path']

def warm_app_shortcuts():
    global _warm_started
    if _warm_started or sys.platform!='win32':return
    _warm_started=True
    def work():
        try:
            from app_catalog import collect_apps
            register_app_shortcuts(collect_apps())
        except Exception:pass
    threading.Thread(target=work,daemon=True).start()


def _resolve_shortcut(path: str) -> str:
    path = str(Path(path).resolve())
    if path in _shortcut_cache:
        return _shortcut_cache[path]
    # Base64 keeps the path out of PowerShell syntax; it is data, never executable input.
    import base64
    encoded = base64.b64encode(path.encode("utf-8")).decode("ascii")
    script = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "'));"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
        "[PSCustomObject]@{path=$s.TargetPath;arguments=$s.Arguments}|ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=5, check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        resolved = result.stdout.lstrip("\ufeff").strip()
        if resolved.startswith('{'):
            import json,re
            details=json.loads(resolved);resolved=str(details.get('path',''))
            argument=str(details.get('arguments',''));child=re.search(r'--processStart(?:=|\s+)["\']?([^"\'\s]+\.exe)',argument,re.I)
            if child:_launcher_children[ntpath.normcase(ntpath.normpath(resolved))]=ntpath.basename(child.group(1))
    except (OSError,ValueError,subprocess.SubprocessError):
        resolved = ""
    if resolved:_shortcut_cache[path] = resolved
    return resolved


def _window_app_id(kernel32, process) -> str:
    fn = getattr(kernel32, "GetApplicationUserModelId", None)
    if fn is None:
        return ""
    length = wintypes.UINT(0)
    result = fn(process, ctypes.byref(length), None)
    if result == APPMODEL_ERROR_NO_APPLICATION or length.value == 0:
        return ""
    if length.value > 2048:
        return ""
    buffer = ctypes.create_unicode_buffer(length.value)
    result = fn(process, ctypes.byref(length), buffer)
    return buffer.value if result == 0 else ""


def _process_path(kernel32, process) -> str:
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
        return os.path.normcase(os.path.abspath(buffer.value))
    return ""


class GUID(ctypes.Structure):
    _fields_=[('data',ctypes.c_ubyte*16)]
    @classmethod
    def parse(cls,value):return cls((ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le))

class PROPERTYKEY(ctypes.Structure):
    _fields_=[('fmtid',GUID),('pid',ctypes.c_uint32)]

class VariantValue(ctypes.Union):
    _fields_=[('text',ctypes.c_wchar_p),('raw',ctypes.c_ubyte*16)]

class PROPVARIANT(ctypes.Structure):
    _fields_=[('vt',ctypes.c_uint16),('reserved',ctypes.c_uint16*3),('value',VariantValue)]

def _window_property_id(hwnd):
    """Read the taskbar identity set by classic desktop apps, not only Store apps."""
    shell=ctypes.WinDLL('shell32',use_last_error=True);ole=ctypes.WinDLL('ole32',use_last_error=True)
    ole.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_uint32];ole.CoInitializeEx.restype=ctypes.c_int32
    ole.CoUninitialize.argtypes=[];ole.CoUninitialize.restype=None
    initialized=ole.CoInitializeEx(None,2)>=0;store=ctypes.c_void_p();value=PROPVARIANT()
    try:
        fn=shell.SHGetPropertyStoreForWindow;fn.argtypes=[wintypes.HWND,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];fn.restype=ctypes.c_int32
        iid=GUID.parse('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
        if fn(hwnd,ctypes.byref(iid),ctypes.byref(store))<0 or not store.value:return ''
        table=ctypes.cast(store,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        get_value=ctypes.WINFUNCTYPE(ctypes.c_int32,ctypes.c_void_p,ctypes.POINTER(PROPERTYKEY),ctypes.POINTER(PROPVARIANT))(table[5])
        key=PROPERTYKEY(GUID.parse('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'),5)
        if get_value(store,ctypes.byref(key),ctypes.byref(value))>=0 and value.vt==31:return value.value.text or ''
        return ''
    finally:
        ole.PropVariantClear.argtypes=[ctypes.POINTER(PROPVARIANT)];ole.PropVariantClear.restype=ctypes.c_int32;ole.PropVariantClear(ctypes.byref(value))
        if store.value:
            table=ctypes.cast(store,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            ctypes.WINFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p)(table[2])(store)
        if initialized:ole.CoUninitialize()

def target_executables(target):
    app_id=target[4:] if target.startswith('app:') else ''
    candidate=_app_shortcuts.get(app_id.casefold(),'') if app_id else target
    if candidate.lower().endswith('.lnk'):candidate=_resolve_shortcut(candidate)
    return {ntpath.normcase(ntpath.normpath(candidate))} if candidate.lower().endswith('.exe') else set()

def identity_matches(app_id,paths,window_id,process_id,process_path):
    if app_id and app_id.casefold() in (window_id.casefold(),process_id.casefold()):return True
    path=ntpath.normcase(ntpath.normpath(process_path)) if process_path else ''
    if path in paths:return True
    # Squirrel-based apps start via Update.exe; their window lives in app-*/App.exe.
    for launcher in paths:
        if ntpath.basename(launcher).lower()=='update.exe' and path.startswith(ntpath.dirname(launcher)+'\\app-'):
            # Only match its known application executable from the shortcut inventory.
            child=_launcher_children.get(launcher,'')
            if child and ntpath.basename(path).casefold()==child.casefold():return True
    return False

_launcher_children={}

def _matching_windows(target: str, media_source=False) -> list[int]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    if hasattr(kernel32, "GetApplicationUserModelId"):
        kernel32.GetApplicationUserModelId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
        kernel32.GetApplicationUserModelId.restype = wintypes.DWORD
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    app_id = target[4:] if target.startswith("app:") else ""
    expected_paths=target_executables(target)

    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length <= 0:
            return True
        window_id=''
        if app_id:
            try:window_id=_window_property_id(hwnd)
            except (OSError,ValueError):pass
            if window_id.casefold()==app_id.casefold():matches.append(int(hwnd));return True
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return True
        process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not process:
            return True
        try:
            current_id=_window_app_id(kernel32,process) if app_id else ''
            current_path=_process_path(kernel32,process)
            matched=identity_matches(app_id,expected_paths,window_id,current_id,current_path)
            if media_source and app_id.lower().endswith('.exe') and ntpath.basename(current_path).casefold()==ntpath.basename(app_id).casefold():matched=True
            if not matched and app_id and ntpath.basename(current_path).casefold()=='applicationframehost.exe':
                children=[]
                child_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
                def visit_child(child,_):
                    child_pid=wintypes.DWORD();user32.GetWindowThreadProcessId(child,ctypes.byref(child_pid))
                    child_process=kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,child_pid.value)
                    if child_process:
                        try:children.append(identity_matches(app_id,expected_paths,'',_window_app_id(kernel32,child_process),_process_path(kernel32,child_process)))
                        finally:kernel32.CloseHandle(child_process)
                    return True
                callback_child=child_type(visit_child);user32.EnumChildWindows.argtypes=[wintypes.HWND,child_type,wintypes.LPARAM];user32.EnumChildWindows.restype=wintypes.BOOL;user32.EnumChildWindows(hwnd,callback_child,0);matched=any(children)
            if matched:matches.append(int(hwnd))
        finally:
            kernel32.CloseHandle(process)
        return True

    callback = callback_type(visit)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(callback, 0)
    return matches


def toggle_or_launch(target: str) -> str:
    """Return 'minimized', 'activated', or 'launched'."""
    if sys.platform != "win32":
        raise OSError("앱 창 전환은 Windows에서만 지원합니다.")
    if target.startswith("app:"):
        app_id = target[4:]
        if not app_id or any(ch in app_id for ch in "\r\n\0"):
            raise ValueError("앱 식별자가 올바르지 않습니다.")
        launch_target = "shell:AppsFolder\\" + app_id
    else:
        path = Path(target)
        if path.suffix.lower() not in (".exe", ".lnk") or not path.exists():
            raise ValueError("앱 실행 경로를 찾을 수 없습니다.")
        launch_target = str(path)

    windows = _matching_windows(target)
    if windows:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.IsIconic.argtypes = [wintypes.HWND]; user32.IsIconic.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]; user32.ShowWindow.restype = wintypes.BOOL
        user32.BringWindowToTop.argtypes = [wintypes.HWND]; user32.BringWindowToTop.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]; user32.SetForegroundWindow.restype = wintypes.BOOL
        foreground = int(user32.GetForegroundWindow() or 0)
        user32.GetAncestor.argtypes=[wintypes.HWND,ctypes.c_uint];user32.GetAncestor.restype=wintypes.HWND
        foreground=int(user32.GetAncestor(foreground,2) or foreground)
        hwnd = foreground if foreground in windows else windows[0]
        if hwnd == foreground and not user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            return "minimized"
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return "activated"

    now=time.monotonic()
    if now-_launch_times.get(target,0)<4:return 'starting'
    _launch_times[target]=now
    try:os.startfile(launch_target)  # type: ignore[attr-defined]
    except OSError:
        _launch_times.pop(target,None);raise
    return "launched"


def media_app_command(source,play):
    """Ask an existing provider window to resume; never launch or foreground it."""
    if sys.platform!='win32' or not source:return False
    windows=_matching_windows('app:'+source,media_source=True)
    if not windows:return False
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    user.SendMessageTimeoutW.restype=wintypes.LPARAM
    result=ctypes.c_size_t()
    # WM_APPCOMMAND, APPCOMMAND_MEDIA_PLAY / PAUSE. No broadcast or global key.
    return bool(user.SendMessageTimeoutW(windows[0],0x0319,windows[0],(46 if play else 47)<<16,2,500,ctypes.byref(result)))
