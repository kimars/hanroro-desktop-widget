"""One bounded latest-write queue, keeping disk flushes away from mouse input."""
import threading,time
from PySide6.QtCore import QObject,Signal
class SettingsWriter(QObject):
    failed=Signal(str)
    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self.condition=threading.Condition();self.pending=None;self.sequence=0;self.completed=0;self.closed=False;self.error=None
        self.thread=threading.Thread(target=self.run,name='settings-writer',daemon=True);self.thread.start()
    def submit(self,snapshot):
        with self.condition:
            if self.closed:raise OSError('설정 저장기가 종료되었습니다.')
            self.sequence+=1;self.pending=(self.sequence,snapshot);self.condition.notify();return self.sequence
    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.pending is not None or self.closed)
                if self.pending is None and self.closed:return
                sequence,snapshot=self.pending;self.pending=None
            error=None
            try:self.store.save(snapshot)
            except Exception as problem:error=str(problem);self.failed.emit('설정 저장 실패: '+error)
            with self.condition:self.completed=sequence;self.error=error;self.condition.notify_all()
    def flush(self,snapshot):
        sequence=self.submit(snapshot)
        with self.condition:
            if not self.condition.wait_for(lambda:self.completed>=sequence,timeout=5):raise OSError('설정 저장 응답 시간 초과')
            if self.error:raise OSError(self.error)
    def close(self):
        with self.condition:self.closed=True;self.condition.notify_all()
        self.thread.join(timeout=5)
