"""Windows wallpaper API with an independent desktop widget layer."""
from __future__ import annotations
import ctypes
import sys
import json
import logging
from pathlib import Path

CLSCTX_LOCAL_SERVER = 0x4
from ctypes import wintypes

IS_WINDOWS=sys.platform=='win32'

class DesktopHost:
    def __init__(self):
        self.parent=0;self.background=0;self.overlay=0;self.desktop_root=0;self.input_active=False;self.allow_zorder=False
        if not IS_WINDOWS: return
        self.u=ctypes.WinDLL('user32',use_last_error=True)
        u=self.u
        for name,rest,args in [
            ('FindWindowW',wintypes.HWND,[wintypes.LPCWSTR,wintypes.LPCWSTR]),
            ('FindWindowExW',wintypes.HWND,[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]),
            ('SetParent',wintypes.HWND,[wintypes.HWND,wintypes.HWND]),
            ('SetWindowPos',wintypes.BOOL,[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]),
            ('IsWindow',wintypes.BOOL,[wintypes.HWND]),
            ('IsIconic',wintypes.BOOL,[wintypes.HWND]),
            ('IsWindowVisible',wintypes.BOOL,[wintypes.HWND]),
            ('ShowWindow',wintypes.BOOL,[wintypes.HWND,ctypes.c_int]),
            ('GetForegroundWindow',wintypes.HWND,[]),
            ('GetWindow',wintypes.HWND,[wintypes.HWND,wintypes.UINT]),
            ('GetAncestor',wintypes.HWND,[wintypes.HWND,wintypes.UINT]),
            ('SetForegroundWindow',wintypes.BOOL,[wintypes.HWND]),
            ('SetFocus',wintypes.HWND,[wintypes.HWND]),
            ('GetClassNameW',ctypes.c_int,[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]),
        ]:
            fn=getattr(u,name);fn.restype=rest;fn.argtypes=args
        # Pointer-sized HWND/LONG_PTR are mandatory on 64-bit Windows.
        self.getlong=getattr(u,'GetWindowLongPtrW',u.GetWindowLongW)
        self.setlong=getattr(u,'SetWindowLongPtrW',u.SetWindowLongW)
        self.getlong.restype=ctypes.c_ssize_t;self.getlong.argtypes=[wintypes.HWND,ctypes.c_int]
        self.setlong.restype=ctypes.c_ssize_t;self.setlong.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t]
        u.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,ctypes.c_size_t,ctypes.c_ssize_t,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
        u.SendMessageTimeoutW.restype=ctypes.c_ssize_t
        u.MapWindowPoints.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.POINTER(wintypes.POINT),wintypes.UINT]
        u.GetParent.restype=wintypes.HWND;u.GetParent.argtypes=[wintypes.HWND]
        self.progman=u.FindWindowW('Progman',None)
    def worker(self):
        u=self.u
        self.progman=u.FindWindowW('Progman',None)
        if not self.progman:return 0
        result=ctypes.c_size_t()
        u.SendMessageTimeoutW(self.progman,0x052C,0,0,2,1200,ctypes.byref(result))
        found=[]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        @callback_type
        def enum(hwnd,_):
            if u.FindWindowExW(hwnd,0,'SHELLDLL_DefView',None):
                worker=u.FindWindowExW(0,hwnd,'WorkerW',None)
                if worker:found.append(worker)
            return True
        u.EnumWindows.argtypes=[callback_type,wintypes.LPARAM];u.EnumWindows.restype=wintypes.BOOL
        u.EnumWindows(enum,0)
        if found:return found[0]
        # Windows 11 24H2+ keeps the wallpaper WorkerW under Progman.
        child=u.FindWindowExW(self.progman,0,'WorkerW',None)
        if not child:
            u.SendMessageTimeoutW(self.progman,0x052C,0xD,1,2,1200,ctypes.byref(result))
            child=u.FindWindowExW(self.progman,0,'WorkerW',None)
        return child or 0
    def attach(self, bg_hwnd, overlay_hwnd, screen):
        if not IS_WINDOWS: return False
        self.parent=self.worker()
        if not self.parent:return False
        self.background=int(bg_hwnd);self.overlay=int(overlay_hwnd)
        # Qt continues to render in the same native surface; no wallpaper registry edits.
        style=self.getlong(self.background,-16)
        self.setlong(self.background,-16,(style|0x40000000|0x04000000|0x02000000)&~0x80000000)
        self.setlong(self.parent,-16,self.getlong(self.parent,-16)|0x02000000)
        ctypes.set_last_error(0)
        self.u.SetParent(self.background,self.parent)
        if self.u.GetParent(self.background)!=self.parent:return False
        self.setlong(self.overlay,-20,self.getlong(self.overlay,-20)|0x00000080|0x08000000)
        self.setlong(self.overlay,-8,int(self.progman or 0)) # owned, non-topmost desktop tool
        self.position_background(screen)
        return True
    def position_background(self,screen):
        if not IS_WINDOWS or not self.parent:return
        # EnumDisplayMonitors yields physical coordinates, including mixed-DPI monitors.
        class MONITORINFOEX(ctypes.Structure):
            _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD),('szDevice',wintypes.WCHAR*32)]
        rects=[]
        cbtype=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
        @cbtype
        def collect(mon,hdc,r,param):
            info=MONITORINFOEX();info.cbSize=ctypes.sizeof(info)
            if self.u.GetMonitorInfoW(mon,ctypes.byref(info)) and info.szDevice==screen.name():rects.append(info.rcMonitor)
            return True
        self.u.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFOEX)]
        self.u.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.c_void_p,cbtype,wintypes.LPARAM]
        self.u.EnumDisplayMonitors(None,None,collect,0)
        if rects:r=rects[0];x,y,w,h=r.left,r.top,r.right-r.left,r.bottom-r.top
        else:
            g=screen.geometry();d=screen.devicePixelRatio();x,y,w,h=[round(v*d) for v in (g.x(),g.y(),g.width(),g.height())]
        pt=wintypes.POINT(x,y);self.u.MapWindowPoints(0,self.parent,ctypes.byref(pt),1)
        self.u.SetWindowPos(self.background,0,pt.x,pt.y,w,h,0x0010|0x0040|0x0004)
    def alive(self):
        if IS_WINDOWS and getattr(self,'desktop_root',0) and not self.u.IsWindow(self.desktop_root):return False
        return not IS_WINDOWS or bool((self.parent and self.u.IsWindow(self.parent)) or (self.progman and self.u.IsWindow(self.progman) and self.overlay and self.u.IsWindow(self.overlay)))
    def sync_overlay(self):
        if not IS_WINDOWS or not self.overlay:return
        root=getattr(self,'desktop_root',0) or self.progman
        if not root or not self.u.IsWindow(root):return
        # Insert immediately above the desktop surface, below ordinary windows.
        # Never use HWND_TOP/SetForegroundWindow just to keep widgets visible.
        previous=self.u.GetWindow(root,3) # GW_HWNDPREV
        if previous==self.overlay:return
        if not previous:return # No safe anchor above the desktop yet.
        if self.u.IsIconic(self.overlay) or not self.u.IsWindowVisible(self.overlay):self.u.ShowWindow(self.overlay,4)
        self.allow_zorder=True
        try:self.u.SetWindowPos(self.overlay,previous,0,0,0,0,0x0001|0x0002|0x0010|0x0040|0x0200)
        finally:self.allow_zorder=False
    def attach_auxiliary(self,hwnd):
        if not IS_WINDOWS or not self.overlay:return False
        hwnd=int(hwnd)
        if not hasattr(self,'auxiliary'):self.auxiliary=set()
        if hwnd in self.auxiliary:return True
        self.auxiliary.add(hwnd);ex=self.getlong(hwnd,-20);self.setlong(hwnd,-20,(ex|0x80|0x08000000)&~0x40008);self.setlong(hwnd,-8,int(self.progman));self.sync_auxiliary();return True
    def set_auxiliary_revealed(self,hwnd,revealed):
        if not IS_WINDOWS:return
        if not hasattr(self,'auxiliary_revealed'):self.auxiliary_revealed=set()
        if revealed:self.auxiliary_revealed.add(hwnd)
        else:self.auxiliary_revealed.discard(hwnd)
        self.allow_zorder=True
        try:self.u.SetWindowPos(hwnd,-1 if revealed else -2,0,0,0,0,0x0001|0x0002|0x0010)
        finally:self.allow_zorder=False
        if not revealed:self.sync_auxiliary()
    def sync_auxiliary(self):
        if not IS_WINDOWS or not self.overlay:return
        for hwnd in list(getattr(self,'auxiliary',set())):
            if not self.u.IsWindow(hwnd):self.auxiliary.discard(hwnd);continue
            if hwnd in getattr(self,'auxiliary_revealed',set()):continue
            previous=self.u.GetWindow(self.overlay,3)
            if not previous or previous==hwnd:continue
            self.allow_zorder=True
            try:self.u.SetWindowPos(hwnd,previous,0,0,0,0,0x0001|0x0002|0x0010|0x0200)
            finally:self.allow_zorder=False
    def detach(self):
        if IS_WINDOWS:
            if self.background and self.u.IsWindow(self.background):self.u.SetParent(self.background,0)
            if self.overlay and self.u.IsWindow(self.overlay):self.setlong(self.overlay,-8,0)
        if IS_WINDOWS:
            for hwnd in getattr(self,'auxiliary',set()):
                if self.u.IsWindow(hwnd):
                    self.set_auxiliary_revealed(hwnd,False);self.setlong(hwnd,-8,0)
            self.auxiliary=set();self.auxiliary_revealed=set()
        self.parent=self.background=self.overlay=self.desktop_root=0;self.input_active=False
    def fullscreen_app(self,screen):
        if not IS_WINDOWS:return False
        hwnd=self.u.GetForegroundWindow()
        if not hwnd or int(hwnd) in (self.overlay,self.background,int(self.progman or 0)):return False
        buf=ctypes.create_unicode_buffer(128);self.u.GetClassNameW(hwnd,buf,128)
        if buf.value in ('Progman','WorkerW'):return False
        rect=wintypes.RECT()
        self.u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        if not self.u.GetWindowRect(hwnd,ctypes.byref(rect)):return False
        # Compare against the actual monitor that contains the foreground window.
        self.u.MonitorFromWindow.restype=wintypes.HANDLE;self.u.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
        mon=self.u.MonitorFromWindow(hwnd,2)
        class INFO(ctypes.Structure):_fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]
        info=INFO();info.cbSize=ctypes.sizeof(info)
        # Use an untyped pointer here because GetMonitorInfo also accepts MONITORINFOEX.
        self.u.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
        if not self.u.GetMonitorInfoW(mon,ctypes.byref(info)):return False
        r=info.rcMonitor
        return rect.left<=r.left and rect.top<=r.top and rect.right>=r.right and rect.bottom>=r.bottom

    def attach_widgets(self,overlay_hwnd):
        """Static wallpapers use an ordinary desktop-owned tool, independent of WorkerW."""
        if not IS_WINDOWS:return False
        self.progman=self.u.FindWindowW('Progman',None)
        if not self.progman:return False
        self.overlay=int(overlay_hwnd)
        ex=self.getlong(self.overlay,-20)
        self.setlong(self.overlay,-20,(ex|0x80|0x08000000)&~0x40000) # TOOLWINDOW, NOACTIVATE; no APPWINDOW
        self.setlong(self.overlay,-8,int(self.progman))
        icons=self.desktop_icon_views()
        self.desktop_root=self.u.GetAncestor(icons[0],2) if icons else self.progman
        self.sync_overlay()
        return bool(self.u.IsWindow(self.overlay))

    def apply_static_wallpaper(self,path,screen,data_directory):
        if not IS_WINDOWS:return False
        try:return NativeWallpaper().apply(path,screen,data_directory)
        except OSError as error:
            self.u.GetSystemMetrics.argtypes=[ctypes.c_int];self.u.GetSystemMetrics.restype=ctypes.c_int
            if self.u.GetSystemMetrics(80)!=1:raise
            result=LegacyWallpaper(self.u).apply(path,data_directory)
            logging.warning('COM wallpaper unavailable; single-monitor SPI fallback used: %s',error)
            return result

    def set_input_active(self,active):
        if not IS_WINDOWS or not self.overlay:return
        ex=self.getlong(self.overlay,-20)
        self.input_active=bool(active)
        if active:
            self._previous_focus=self.u.GetForegroundWindow()
            self.setlong(self.overlay,-20,ex & ~0x08000000)
            self.u.SetForegroundWindow(self.overlay);self.u.SetFocus(self.overlay)
        else:
            self.setlong(self.overlay,-20,ex | 0x08000000)
            previous=getattr(self,'_previous_focus',0)
            if self.u.GetForegroundWindow()==self.overlay and previous and self.u.IsWindow(previous):self.u.SetForegroundWindow(previous)
    def desktop_icon_views(self):
        if not IS_WINDOWS:return []
        found=set();u=self.u
        def inspect(parent):
            view=u.FindWindowExW(parent,0,'SHELLDLL_DefView',None)
            if view:
                icons=u.FindWindowExW(view,0,'SysListView32',None)
                if icons:found.add(int(icons))
        inspect(u.FindWindowW('Progman',None))
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        @callback
        def walk(hwnd,_):
            inspect(hwnd)
            name=ctypes.create_unicode_buffer(128);u.GetClassNameW(hwnd,name,128)
            if name.value=='SHELLDLL_DefView':
                icons=u.FindWindowExW(hwnd,0,'SysListView32',None)
                if icons:found.add(int(icons))
            return True
        u.EnumWindows.argtypes=[callback,wintypes.LPARAM];u.EnumWindows(walk,0)
        u.EnumChildWindows.argtypes=[wintypes.HWND,callback,wintypes.LPARAM]
        progman=u.FindWindowW('Progman',None)
        if progman:u.EnumChildWindows(progman,walk,0)
        return sorted(found)
    def restore_static_wallpaper(self,directory):
        try:return NativeWallpaper().restore(directory)
        except OSError:
            if (Path(directory)/'previous-wallpaper-spi.json').exists():return LegacyWallpaper(self.u).restore(directory)
            raise
    def show_desktop(self):
        if IS_WINDOWS:
            shell=ctypes.WinDLL('user32');shell.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
            taskbar=self.u.FindWindowW('Shell_TrayWnd',None)
            if taskbar:shell.PostMessageW(taskbar,0x0111,419,0)


class GUID(ctypes.Structure):
    _fields_=[('Data1',ctypes.c_uint32),('Data2',ctypes.c_uint16),('Data3',ctypes.c_uint16),('Data4',ctypes.c_ubyte*8)]
    @classmethod
    def parse(cls,value):
        import uuid
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)

class NativeWallpaper:
    """Documented Windows IDesktopWallpaper COM interface, not shell embedding."""
    def __init__(self):
        self.ptr=ctypes.c_void_p();self.ole=None
        if not IS_WINDOWS:return
        self.ole=ctypes.WinDLL('ole32')
        self.ole.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_uint32];self.ole.CoInitializeEx.restype=ctypes.c_long
        result=self.ole.CoInitializeEx(None,2);self._com_initialized=result>=0
        if result<0 and (result & 0xffffffff)!=0x80010106:raise OSError('COM 초기화 실패')
        self.ole.CoUninitialize.argtypes=[];self.ole.CoUninitialize.restype=None
        clsid=GUID.parse('C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD');iid=GUID.parse('B92B56A9-8B55-4E14-9A89-0199BBB6F93B')
        self.ole.CoCreateInstance.argtypes=[ctypes.POINTER(GUID),ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)]
        self.ole.CoCreateInstance.restype=ctypes.c_long
        result=self.ole.CoCreateInstance(ctypes.byref(clsid),None,CLSCTX_LOCAL_SERVER,ctypes.byref(iid),ctypes.byref(self.ptr))
        if result<0:
            if self._com_initialized:self.ole.CoUninitialize();self._com_initialized=False
            raise OSError(f'Windows 배경 인터페이스 초기화 실패 0x{result & 0xffffffff:08X}')
        self.ole.CoTaskMemFree.argtypes=[ctypes.c_void_p];self.ole.CoTaskMemFree.restype=None
    def call(self,index,types,*values):
        vtable=ctypes.cast(self.ptr,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        fn=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,*types)(vtable[index])
        result=fn(self.ptr,*values)
        if result<0:raise OSError(f'Windows 배경 설정 오류 0x{result & 0xffffffff:08X}')
        return result
    def read_string(self,index,*values):
        raw=ctypes.c_void_p()
        types=[ctypes.c_uint] if index==5 else [ctypes.c_wchar_p]
        self.call(index,types+[ctypes.POINTER(ctypes.c_void_p)],*values,ctypes.byref(raw))
        try:return ctypes.wstring_at(raw) if raw.value else ''
        finally:
            if raw.value:self.ole.CoTaskMemFree(raw)
    def apply(self,path,screen,directory):
        import json
        from pathlib import Path
        try:
            count=ctypes.c_uint();self.call(6,[ctypes.POINTER(ctypes.c_uint)],ctypes.byref(count))
            monitors=[]
            for index in range(count.value):
                ident=self.read_string(5,index);rect=wintypes.RECT()
                try:self.call(7,[ctypes.c_wchar_p,ctypes.POINTER(wintypes.RECT)],ident,ctypes.byref(rect))
                except OSError:continue
                monitors.append((ident,rect))
            if not monitors:raise OSError('모니터를 찾지 못했습니다.')
            # Match screen order spatially. Device paths cannot be compared to Qt display names.
            rect=physical_screen_rect(screen);cx=(rect[0]+rect[2])/2;cy=(rect[1]+rect[3])/2
            chosen=min(monitors,key=lambda r:abs((r[1].left+r[1].right)/2-cx)+abs((r[1].top+r[1].bottom)/2-cy))[0]
            backup=Path(directory)/'previous-wallpaper.json'
            if backup.exists():records=json.loads(backup.read_text('utf-8'))
            else:
                position=ctypes.c_uint();self.call(11,[ctypes.POINTER(ctypes.c_uint)],ctypes.byref(position))
                records={'wallpapers':{},'position':position.value}
            if 'wallpapers' not in records:records={'wallpapers':records,'position':4}
            if chosen not in records['wallpapers']:
                records['wallpapers'][chosen]=self.read_string(4,chosen);backup.write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
            self.call(10,[ctypes.c_uint],4)
            self.call(3,[ctypes.c_wchar_p,ctypes.c_wchar_p],chosen,str(path))
            return True
        finally:self.close()
    def close(self):
        if self.ptr.value:
            self.call(2,[]);self.ptr=ctypes.c_void_p()
        if self.ole and getattr(self,'_com_initialized',False):self.ole.CoUninitialize();self._com_initialized=False

    def restore(self,directory):
        import json
        from pathlib import Path
        try:
            path=Path(directory)/'previous-wallpaper.json'
            if not path.is_file():raise OSError('저장된 이전 배경이 없습니다.')
            data=json.loads(path.read_text('utf-8'));rows=data.get('wallpapers',data)
            restored=0
            for monitor,image in rows.items():
                if isinstance(image,str):
                    try:self.call(3,[ctypes.c_wchar_p,ctypes.c_wchar_p],monitor,image);restored+=1
                    except OSError:pass
            if 'position' in data:self.call(10,[ctypes.c_uint],int(data['position']))
            if not restored:raise OSError('이전 배경을 복원하지 못했습니다.')
            return True
        finally:self.close()


def physical_screen_rect(screen):
    if not IS_WINDOWS:
        r=screen.geometry();return (r.x(),r.y(),r.x()+r.width(),r.y()+r.height())
    user=ctypes.WinDLL('user32')
    class INFO(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD),('device',wintypes.WCHAR*32)]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    found=[]
    user.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(INFO)]
    @callback_type
    def collect(monitor,dc,rect,param):
        info=INFO();info.size=ctypes.sizeof(info)
        if user.GetMonitorInfoW(monitor,ctypes.byref(info)) and info.device==screen.name():
            r=info.monitor;found.append((r.left,r.top,r.right,r.bottom))
        return True
    user.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.c_void_p,callback_type,wintypes.LPARAM]
    user.EnumDisplayMonitors(None,None,collect,0)
    if not found:raise OSError('선택한 모니터의 좌표를 찾지 못했습니다.')
    return found[0]


class LegacyWallpaper:
    """A documented, single-monitor fallback; never silently changes all monitors."""
    def __init__(self,user):
        self.user=user
        user.SystemParametersInfoW.argtypes=[wintypes.UINT,wintypes.UINT,ctypes.c_void_p,wintypes.UINT]
        user.SystemParametersInfoW.restype=wintypes.BOOL
    def apply(self,path,directory):
        from PySide6.QtGui import QImage
        backup=Path(directory)/'previous-wallpaper-spi.json'
        if not backup.exists():
            value=ctypes.create_unicode_buffer(32768)
            if not self.user.SystemParametersInfoW(0x0073,len(value),value,0):raise OSError('기존 배경 경로를 읽지 못했습니다.')
            backup.write_text(json.dumps({'path':value.value},ensure_ascii=False),encoding='utf-8')
        bmp=Path(path).with_suffix('.bmp')
        if not QImage(str(path)).save(str(bmp),'BMP'):raise OSError('호환 배경 파일을 만들지 못했습니다.')
        value=ctypes.c_wchar_p(str(bmp))
        if not self.user.SystemParametersInfoW(0x0014,0,value,3):raise OSError('Windows 배경 적용 실패')
        return True
    def restore(self,directory):
        data=json.loads((Path(directory)/'previous-wallpaper-spi.json').read_text('utf-8'))
        if not self.user.SystemParametersInfoW(0x0014,0,ctypes.c_wchar_p(data['path']),3):raise OSError('이전 배경 복원 실패')
        return True


class DesktopIcons:
    """Temporarily hide the icon list, retaining a recovery record across crashes."""
    def __init__(self,host,directory):
        self.host=host;self.path=Path(directory)/'desktop-icons-session.json';self.original={}
        if self.path.exists():
            try:self.original=json.loads(self.path.read_text('utf-8'))
            except (OSError,ValueError):self.original={}
        if not isinstance(self.original,dict):self.original={}
    def hide(self):
        handles=self.host.desktop_icon_views()
        if not handles:return
        user=self.host.u;changed=False
        recovering=bool(self.original) and not any(str(h) in self.original for h in handles) and any(self.original.values())
        for hwnd in handles:
            key=str(hwnd)
            if key not in self.original:
                # A crash may leave the current list hidden. Retain the earlier visible state.
                was_visible=bool(user.IsWindowVisible(hwnd)) or recovering
                self.original[key]=was_visible;changed=True
        if changed:self.path.write_text(json.dumps(self.original),encoding='utf-8')
        for hwnd in handles:
            if user.IsWindowVisible(hwnd):user.ShowWindow(hwnd,0)
    def restore(self,force=False):
        handles=self.host.desktop_icon_views()
        if not hasattr(self.host,'u'):return
        for hwnd in handles:
            if force or self.original.get(str(hwnd),any(self.original.values())):self.host.u.ShowWindow(hwnd,5)
        self.original={};self.path.unlink(missing_ok=True)
