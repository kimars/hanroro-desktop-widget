"""Packaged Qt dock on a real Windows desktop: grouped DWM previews and recovery."""
import ctypes,os,sys,time
from pathlib import Path
from types import SimpleNamespace
core=Path(sys.argv[1]).resolve();sys.path.insert(0,str(core))
from font_config import configure_windows_fonts
configure_windows_fonts()
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication,QWidget
from state import validate
from desktop_shell import DesktopShell
from windows_desktop import DesktopHost
app=QApplication([])
class Bridge(QObject):
    stateChanged=Signal();toast=Signal(str)
    def __init__(self):super().__init__();self.desktop=False;self.store=SimpleNamespace(directory=core/'dock-fixture',data=validate({}))
b=Bridge();host=DesktopHost();overlay=QWidget();host.overlay=int(overlay.winId());host.progman=host.u.FindWindowW('Progman',None)
p=SimpleNamespace(app=app,bridge=b,host=host,pick_screen=app.primaryScreen)
shell=DesktopShell(p);shell.service.enabled=False;windows=[]
def pump(seconds=.2):
    until=time.monotonic()+seconds
    while time.monotonic()<until:app.processEvents();time.sleep(.01)
try:
    for title in ('Dock fixture A','Dock fixture B'):
        window=QWidget();window.setWindowTitle(title);window.resize(300,200);window.show();windows.append(window)
    pump();row={'name':'Fixture','target':'app:fixture'};shell.taskbar_rows=[row];shell.running_rows=[dict(row,hwnd=int(widget.winId()),pid=os.getpid(),name=widget.windowTitle()) for widget in windows];shell.active=True;shell.taskbar_loaded=True;shell.bar_active=True;host.attach_auxiliary(int(shell.dock.winId()));shell.dock.refresh();shell.dock.check_edge();pump()
    u=host.u;hwnd=int(shell.dock.winId());assert u.IsWindowVisible(hwnd)
    for state in (0,6): # Hiding and minimizing must not permanently lose the dock.
        u.ShowWindow(hwnd,state);shell.dock._last_health=0;shell.dock.check_edge();pump();assert u.IsWindowVisible(hwnd) and not u.IsIconic(hwnd)
    assert not host.getlong(hwnd,-8),'Dock must not be owned by Progman'
    shell.chooser.show_windows(row,shell.running_rows);pump();assert len(shell.chooser.previews.handles)==2
    assert len(shell.dock.all_rows)==3 # search + one app group + settings
    shell.chooser.hide();assert not shell.chooser.previews.handles
    print('Packaged Qt dock: one app/two DWM previews, hide/minimize recovery and independent ownership passed.',flush=True)
finally:
    shell.close();host.detach()
    for window in windows:window.close()
    overlay.close();app.processEvents()
