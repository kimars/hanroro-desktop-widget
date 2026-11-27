"""Real Win32 fixture + packaged IPC and AppBar reservation/restoration checks."""
import ctypes,json,os,subprocess,sys,time,uuid,base64
from ctypes import wintypes as w
from pathlib import Path
core=Path(sys.argv[1]).resolve();sys.path.insert(0,str(core))
u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p];u.CreateWindowExW.restype=w.HWND
u.DestroyWindow.argtypes=[w.HWND];u.FindWindowW.argtypes=[w.LPCWSTR,w.LPCWSTR];u.FindWindowW.restype=w.HWND
u.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)];u.PeekMessageW.argtypes=[ctypes.POINTER(w.MSG),w.HWND,w.UINT,w.UINT,w.UINT];u.DispatchMessageW.argtypes=[ctypes.POINTER(w.MSG)]
k.CreateEventW.argtypes=[ctypes.c_void_p,w.BOOL,w.BOOL,w.LPCWSTR];k.CreateEventW.restype=w.HANDLE;k.SetEvent.argtypes=[w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
windows=[];worker=None;guardian=None;event=None

def pump(seconds=.1):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        msg=w.MSG()
        while u.PeekMessageW(ctypes.byref(msg),None,0,0,1):u.TranslateMessage(ctypes.byref(msg));u.DispatchMessageW(ctypes.byref(msg))
        time.sleep(.01)

def workarea():
    rect=w.RECT();assert u.SystemParametersInfoW(48,0,ctypes.byref(rect),0);return tuple((rect.left,rect.top,rect.right,rect.bottom))

def request(action,**data):
    worker.stdin.write(json.dumps({'id':1,'action':action,**data})+'\n');worker.stdin.flush()
    # Wait on a background reader while the owning thread keeps Win32 responsive.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        future=pool.submit(worker.stdout.readline);until=time.monotonic()+12
        while not future.done():
            if time.monotonic()>until:worker.kill();raise TimeoutError(action)
            pump(.02)
        result=json.loads(future.result())
    assert 'error' not in result,result
    return result['data']

try:
    for name in ('Hanroro fixture document A','Hanroro fixture document B'):
        hwnd=u.CreateWindowExW(0,'STATIC',name,0x10cf0000,10,10,360,220,None,None,None,None);assert hwnd;windows.append(hwnd)
    # Set a desktop AppUserModelID on both real windows, as browsers/Electron do.
    from app_windows import GUID,PROPERTYKEY,PROPVARIANT
    shell=ctypes.WinDLL('shell32');ole=ctypes.WinDLL('ole32');ole.CoInitializeEx(None,2)
    factory=shell.SHGetPropertyStoreForWindow;factory.argtypes=[w.HWND,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];factory.restype=ctypes.c_int32
    for hwnd in windows:
        store=ctypes.c_void_p();iid=GUID.parse('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99');assert factory(hwnd,ctypes.byref(iid),ctypes.byref(store))>=0
        table=ctypes.cast(store,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents;key=PROPERTYKEY(GUID.parse('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'),5);value=PROPVARIANT();value.vt=31;value.value.text='Hanroro.Shell.Fixture'
        try:
            assert ctypes.WINFUNCTYPE(ctypes.c_int32,ctypes.c_void_p,ctypes.POINTER(PROPERTYKEY),ctypes.POINTER(PROPVARIANT))(table[6])(store,ctypes.byref(key),ctypes.byref(value))>=0
            assert ctypes.WINFUNCTYPE(ctypes.c_int32,ctypes.c_void_p)(table[7])(store)>=0
        finally:ctypes.WINFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p)(table[2])(store)
    ole.CoUninitialize()
    pump()
    worker=subprocess.Popen([str(core/'python.exe'),str(core/'main.py'),'--shell-worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=0x08000000)
    rows=request('windows')['rows'];ours=[r for r in rows if r['hwnd'] in windows];assert len(ours)==2,ours
    from desktop_native import matching_windows
    row={'target':'app:fixture','path':'fixture.lnk','executables':[sys.executable]}
    assert len(matching_windows(row,ours))==2
    assert len(matching_windows({'target':'app:Hanroro.Shell.Fixture'},ours))==2
    assert {r['name'] for r in ours}=={'Hanroro fixture document A','Hanroro fixture document B'}
    icons=request('icons',rows=[dict(ours[0],key='fixture')]);png=base64.b64decode(icons[0]['png']);assert png.startswith(b'\x89PNG\r\n\x1a\n'),icons
    print('Packaged shell: two real windows, executable matching, titles and PNG app icon passed.',flush=True)
    worker.stdin.close();assert worker.wait(timeout=5)==0;worker=None
    if u.FindWindowW('Shell_TrayWnd',None):
        before=workarea();name='Local\\HanroroAppBar-check-'+uuid.uuid4().hex;event=k.CreateEventW(None,True,False,name);assert event
        # No keyboard hooks or Windows taskbar hiding during this fixture.
        guardian=subprocess.Popen([str(core/'HanroroShell.exe'),str(os.getpid()),str(windows[0]),'0','0',name,str(windows[1]),'0'],creationflags=0x08000000)
        until=time.monotonic()+5
        while workarea()==before and time.monotonic()<until and guardian.poll() is None:pump()
        during=workarea();assert guardian.poll() is None and during[3]<before[3],(before,during,guardian.poll())
        k.SetEvent(event)
        while guardian.poll() is None:pump()
        assert guardian.returncode==0
        pump(.3);assert workarea()==before,(before,workarea())
        print('Native AppBar: reserved work area and restored original work area on exit.',flush=True)
    else:print('AppBar fixture skipped: CI session has no Explorer taskbar.',flush=True)
finally:
    if worker and worker.poll() is None:worker.kill();worker.wait(timeout=4)
    if guardian and guardian.poll() is None:
        if event:k.SetEvent(event)
        guardian.wait(timeout=5)
    if event:k.CloseHandle(event)
    for hwnd in windows:u.DestroyWindow(hwnd)
