"""Own only this app's optional shell integration process; never edit Explorer settings."""
import os,sys,subprocess,secrets,ctypes
from pathlib import Path
class ShellNative:
    def __init__(self,directory):self.directory=Path(directory);self.process=None;self.event=None;self.configuration=None
    def configure(self,hwnd,hide_taskbar,win_key):
        config=(int(hwnd),bool(hide_taskbar),bool(win_key))
        if config==self.configuration and self.process and self.process.poll() is None:return True
        self.close()
        if sys.platform!='win32' or not (hide_taskbar or win_key):return True
        helper=Path(__file__).resolve().parent/'HanroroShell.exe'
        if not helper.is_file():return False
        name='Local\\HanroroShell-'+str(os.getpid())+'-'+secrets.token_hex(12)
        k=ctypes.WinDLL('kernel32',use_last_error=True);k.CreateEventW.restype=ctypes.c_void_p;k.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_wchar_p]
        self.event=k.CreateEventW(None,True,False,name)
        if not self.event:return False
        try:self.process=subprocess.Popen([str(helper),str(os.getpid()),str(hwnd),'1' if hide_taskbar else '0','1' if win_key else '0',name],creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True);self.configuration=config;return True
        except OSError:self.close();return False
    def focus(self,hwnd):
        if sys.platform!='win32':return
        from ctypes import wintypes
        u=ctypes.WinDLL('user32');k=ctypes.WinDLL('kernel32');u.GetForegroundWindow.restype=wintypes.HWND;u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.c_void_p];u.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL];u.SetForegroundWindow.argtypes=[wintypes.HWND];u.SetFocus.argtypes=[wintypes.HWND]
        foreground=u.GetForegroundWindow();thread=u.GetWindowThreadProcessId(foreground,None) if foreground else 0;current=k.GetCurrentThreadId();attached=bool(thread and thread!=current and u.AttachThreadInput(current,thread,True))
        try:u.SetForegroundWindow(hwnd);u.SetFocus(hwnd)
        finally:
            if attached:u.AttachThreadInput(current,thread,False)
    def close(self):
        if self.event:
            k=ctypes.WinDLL('kernel32',use_last_error=True);k.SetEvent.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p];k.SetEvent(self.event)
            if self.process:
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:pass # Guardian still owns taskbar recovery; never kill it here.
            k.CloseHandle(self.event)
        self.event=None;self.process=None;self.configuration=None
