"""One renderer thread with a single replaceable pending request, never a render backlog."""
import threading
from pathlib import Path
from PySide6.QtCore import QObject,Signal
from wallpaper import render_wallpaper

def output_size(native,quality):
    w,h=max(1,int(native[0])),max(1,int(native[1]))
    if quality=='4k':
        ratio=w/h
        return (3840,max(1,round(3840/ratio))) if w>=h else (max(1,round(3840*ratio)),3840)
    return w,h

class WallpaperCache(QObject):
    ready=Signal(object,str);failed=Signal(object,str)
    def __init__(self,parent=None):
        super().__init__(parent);self.condition=threading.Condition();self.pending=None;self.closed=False;self.worker=None
    def submit(self,key,args):
        with self.condition:
            if self.closed:return
            self.pending=(key,args);self.condition.notify()
            if self.worker is None:self.worker=threading.Thread(target=self.run,daemon=True,name='wallpaper-render');self.worker.start()
    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.pending is not None or self.closed)
                if self.closed:return
                key,args=self.pending;self.pending=None
            try:
                path=render_wallpaper(*args)
                if not self.closed:self.ready.emit(key,str(path))
                # Bound the image cache, preserving the latest rendered file.
                files=sorted(Path(args[1]).glob('wallpaper-*.png'),key=lambda p:p.stat().st_mtime,reverse=True)
                for p in files[8:]:
                    if p!=path:
                        try:p.unlink()
                        except OSError:pass
            except Exception as error:
                if not self.closed:
                    try:self.failed.emit(key,str(error))
                    except RuntimeError:pass
    def close(self):
        with self.condition:self.closed=True;self.pending=None;self.condition.notify_all()
        if self.worker:self.worker.join(timeout=5)
