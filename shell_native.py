"""Native appbar/hotkey guardian lifecycle. Reconfiguration never waits in the GUI thread."""
import os,sys,subprocess,secrets,ctypes
from pathlib import Path
from PySide6.QtCore import QObject,QTimer,QRect
class ShellNative(QObject):
    def __init__(self,directory,parent=None):
        super().__init__(parent);self.directory=Path(directory);self.process=None;self.stop_event=None;self.configuration=None;self.desired=None;self.retiring=[];self.failed='';self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.poll)
    def configure(self,hwnd,hide_taskbar,win_key,dock=0,auto_hide=True):
        config=(int(hwnd),bool(hide_taskbar),bool(win_key),int(dock),bool(auto_hide));self.desired=config
        if config==self.configuration and self.process and self.process.poll() is None:return True
        self.retire();self.poll();return not bool(self.failed)
    def retire(self):
        if self.process or self.stop_event:
            if self.stop_event:
                k=ctypes.WinDLL('kernel32');k.SetEvent.argtypes=[ctypes.c_void_p];k.SetEvent(self.stop_event)
            self.retiring.append((self.process,self.stop_event));self.process=self.stop_event=None;self.configuration=None;self.timer.start()
    def poll(self):
        if sys.platform!='win32':self.timer.stop();return
        k=ctypes.WinDLL('kernel32');k.CloseHandle.argtypes=[ctypes.c_void_p]
        alive=[]
        for process,event in self.retiring:
            if process and process.poll() is None:alive.append((process,event))
            elif event:k.CloseHandle(event)
        self.retiring=alive
        if alive:return
        if self.desired and not self.process:
            hwnd,hide,win,dock,auto=self.desired;helper=Path(__file__).resolve().parent/'HanroroShell.exe'
            if not helper.is_file():self.failed='Windows 보조 실행 파일이 없습니다.';self.timer.stop();return
            if not (hide or win or dock):self.timer.stop();return
            name='Local\\HanroroShell-'+str(os.getpid())+'-'+secrets.token_hex(12)
            k.CreateEventW.restype=ctypes.c_void_p;k.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_wchar_p];event=k.CreateEventW(None,True,False,name)
            if not event:self.failed='Windows 중지 이벤트를 만들지 못했습니다.';self.timer.stop();return
            try:
                self.process=subprocess.Popen([str(helper),str(os.getpid()),str(hwnd),str(int(hide)),str(int(win)),name,str(dock),str(int(auto))],creationflags=0x08000000,close_fds=True);self.stop_event=event;self.configuration=self.desired;self.failed=''
            except OSError as e:k.CloseHandle(event);self.failed=str(e)
        self.timer.stop()
    def focus(self,hwnd):
        if sys.platform!='win32':return
        from ctypes import wintypes
        u=ctypes.WinDLL('user32');k=ctypes.WinDLL('kernel32');u.GetForegroundWindow.restype=wintypes.HWND;u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.c_void_p];u.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL];u.SetForegroundWindow.argtypes=[wintypes.HWND];u.SetFocus.argtypes=[wintypes.HWND]
        foreground=u.GetForegroundWindow();thread=u.GetWindowThreadProcessId(foreground,None) if foreground else 0;current=k.GetCurrentThreadId();attached=bool(thread and thread!=current and u.AttachThreadInput(current,thread,True))
        try:u.SetForegroundWindow(hwnd);u.SetFocus(hwnd)
        finally:
            if attached:u.AttachThreadInput(current,thread,False)
    def bar_rect(self,hwnd,screen):
        if sys.platform!='win32':return None
        from ctypes import wintypes
        class INFO(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
        u=ctypes.WinDLL('user32');u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];u.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];u.MonitorFromWindow.restype=wintypes.HANDLE;u.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
        rect=wintypes.RECT();info=INFO();info.size=ctypes.sizeof(info)
        if not u.GetWindowRect(hwnd,ctypes.byref(rect)) or not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd,2),ctypes.byref(info)):return None
        d=screen.devicePixelRatio();g=screen.geometry();return QRect(round(g.x()+(rect.left-info.monitor.left)/d),round(g.y()+(rect.top-info.monitor.top)/d),round((rect.right-rect.left)/d),round((rect.bottom-rect.top)/d))
    def close(self):self.desired=None;self.retire();self.poll()
