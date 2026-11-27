"""Copy and hash originals off the GUI thread. One bounded import at a time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import QObject,Signal
class MediaImporter(QObject):
    finished=Signal(object,bool,str)
    def __init__(self,store,parent=None):super().__init__(parent);self.store=store;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='media-import');self.busy=False;self.closed=False
    def submit(self,paths,video):
        if self.busy or self.closed:return False
        self.busy=True;rows=list(paths)[:1 if video else 200];store=self.store
        def work():
            saved=[];error=''
            try:
                from PySide6.QtGui import QImageReader
                for path in rows:
                    if not video and not QImageReader(str(path)).canRead():raise ValueError('읽을 수 없는 사진: '+Path(path).name)
                    saved.append(store.ingest(path))
            except (OSError,ValueError) as e:error=str(e)
            try:
                if not self.closed:self.finished.emit(saved,video,error)
            except RuntimeError:pass
        self.pool.submit(work);return True
    def close(self):self.closed=True;self.pool.shutdown(wait=False,cancel_futures=True)
