"""Exercise the guardian's stop and parent-death paths without hiding the taskbar or hooking input."""
import ctypes,os,subprocess,sys,uuid,time
from ctypes import wintypes

def check(helper):
    u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
    u.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HWND,wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p];u.CreateWindowExW.restype=wintypes.HWND
    u.DestroyWindow.argtypes=[wintypes.HWND];k.CreateEventW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR];k.CreateEventW.restype=wintypes.HANDLE;k.SetEvent.argtypes=[wintypes.HANDLE];k.CloseHandle.argtypes=[wintypes.HANDLE]
    hwnd=u.CreateWindowExW(0,'STATIC','Hanroro guardian smoke',0,0,0,1,1,None,None,None,None)
    if not hwnd:raise ctypes.WinError(ctypes.get_last_error())
    try:
        for parent_dies in (False,True):
            name='Local\\HanroroShell-test-'+uuid.uuid4().hex;event=k.CreateEventW(None,True,False,name)
            parent=subprocess.Popen([sys.executable,'-c','import time;time.sleep(.8)']) if parent_dies else None
            process=None
            try:
                process=subprocess.Popen([helper,str(parent.pid if parent else os.getpid()),str(hwnd),'0','0',name],creationflags=0x08000000)
                if parent:parent.wait(timeout=4)
                else:time.sleep(.3);k.SetEvent(event)
                if process.wait(timeout=4)!=0:raise RuntimeError('Shell guardian failed')
            finally:
                if process and process.poll() is None:k.SetEvent(event);process.wait(timeout=4)
                if parent and parent.poll() is None:parent.terminate();parent.wait(timeout=4)
                k.CloseHandle(event)
    finally:u.DestroyWindow(hwnd)
    print('Shell guardian stop/parent-death checks passed; no taskbar or keyboard changes.',flush=True)
if __name__=='__main__':check(sys.argv[1])
