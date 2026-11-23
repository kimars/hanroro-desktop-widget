"""Block automatic activation/raising of the desktop widget window only."""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter

class WINDOWPOS(ctypes.Structure):
    _fields_=[('hwnd',wintypes.HWND),('hwndInsertAfter',wintypes.HWND),('x',ctypes.c_int32),('y',ctypes.c_int32),('cx',ctypes.c_int32),('cy',ctypes.c_int32),('flags',ctypes.c_uint32)]

class DesktopEventFilter(QAbstractNativeEventFilter):
    def __init__(self,host_getter,interactive_getter=None):super().__init__();self.host_getter=host_getter;self.interactive_getter=interactive_getter
    def nativeEventFilter(self,event_type,message):
        if bytes(event_type) not in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):return False,0
        msg=ctypes.cast(int(message),ctypes.POINTER(wintypes.MSG)).contents
        host=self.host_getter()
        if not getattr(host,'overlay',0) or msg.hWnd!=host.overlay:return False,0
        if msg.message==0x0084 and self.interactive_getter:
            value=self.interactive_getter()
            if value:
                from PySide6.QtGui import QCursor
                view,region=value
                if view and not region.contains(view.mapFromGlobal(QCursor.pos())):return True,-1 # HTTRANSPARENT for decorative pixels.
        if msg.message==0x0021 and not getattr(host,'input_active',False):return True,3 # MA_NOACTIVATE, retain click
        if msg.message==0x0046 and msg.lParam and not getattr(host,'allow_zorder',False):
            position=ctypes.cast(msg.lParam,ctypes.POINTER(WINDOWPOS)).contents
            position.flags|=0x0004 # SWP_NOZORDER is editable in WM_WINDOWPOSCHANGING.
        return False,0
