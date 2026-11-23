import ctypes,sys
from pathlib import Path
from ctypes import wintypes
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_events import DesktopEventFilter,WINDOWPOS
import windows_desktop as native


def test_widget_activation_cannot_change_window_order():
    host=SimpleNamespace(overlay=100,allow_zorder=False,input_active=False)
    handler=DesktopEventFilter(lambda:host)
    position=WINDOWPOS();position.hwnd=100;position.hwndInsertAfter=0;position.flags=0x0003
    msg=wintypes.MSG();msg.hWnd=100;msg.message=0x0046;msg.lParam=ctypes.addressof(position)
    assert handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))==(False,0)
    assert position.flags&0x0004
    # Explicit desktop anchoring is allowed; ordinary application windows are unaffected.
    position.flags=0x3;host.allow_zorder=True
    handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg));assert position.flags==0x3
    host.allow_zorder=False;msg.hWnd=200
    handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg));assert position.flags==0x3


def test_clicks_do_not_activate_widget_except_while_typing():
    host=SimpleNamespace(overlay=100,input_active=False)
    handler=DesktopEventFilter(lambda:host);msg=wintypes.MSG();msg.hWnd=100;msg.message=0x0021
    assert handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))==(True,3)
    host.input_active=True
    assert handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))==(False,0)


def test_overlay_is_placed_below_app_and_above_desktop_without_top(monkeypatch):
    monkeypatch.setattr(native,'IS_WINDOWS',True)
    host=object.__new__(native.DesktopHost);host.overlay=100;host.progman=10;host.desktop_root=10
    previous=[200];calls=[]
    def place(hwnd,after,*args):
        calls.append((hwnd,after,args[-1]));assert host.allow_zorder;previous[0]=hwnd
    host.u=SimpleNamespace(IsWindow=lambda _:True,GetWindow=lambda *_:previous[0],IsIconic=lambda _:False,IsWindowVisible=lambda _:True,SetWindowPos=place)
    host.sync_overlay();host.sync_overlay()
    assert len(calls)==1 and calls[0][1]==200 and calls[0][2]&0x10
    assert not host.allow_zorder


def test_decorations_are_mouse_transparent_but_widget_controls_still_receive_clicks():
    from PySide6.QtCore import QPoint,QRect
    from PySide6.QtGui import QRegion
    host=SimpleNamespace(overlay=100,input_active=False)
    region=QRegion(QRect(200,0,100,100));cursor=[QPoint(20,20)]
    view=SimpleNamespace(mapFromGlobal=lambda point:cursor[0]);handler=DesktopEventFilter(lambda:host,lambda:(view,region))
    msg=wintypes.MSG();msg.hWnd=100;msg.message=0x84
    assert handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))==(True,-1)
    cursor[0]=QPoint(220,20)
    assert handler.nativeEventFilter(b'windows_generic_MSG',ctypes.addressof(msg))==(False,0)
