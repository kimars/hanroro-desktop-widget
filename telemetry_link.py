import json,sys,time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QProcess,QTimer

EMPTY={'cpu':None,'ram':None,'ramUsed':None,'ramTotal':None,'gpu':None,'gpuUsed':None,'gpuTotal':None,'gpuName':'','levels':[0.]*32,'audioStatus':'','device':'','error':''}
class TelemetryLink(QObject):
    changed=Signal();levelsChanged=Signal()
    def __init__(self,entry,parent=None):
        super().__init__(parent);self.entry=str(entry);self.data=dict(EMPTY);self.process=None;self.buffer=b'';self.config={'audio':False,'monitor':False};self.closed=False;self.last_message=0
        self.watch=QTimer(self);self.watch.setInterval(2000);self.watch.timeout.connect(self.check)
        if sys.platform=='win32':QTimer.singleShot(0,self.start)
        else:self.data['error']='Windows에서 지원합니다.'
    def start(self):
        if self.closed or sys.platform!='win32':return
        self.stop_worker();self.buffer=b'';p=QProcess();self.process=p;self.last_message=time.monotonic()
        p.readyReadStandardOutput.connect(self.read);p.readyReadStandardError.connect(lambda: p.readAllStandardError());p.started.connect(self.configure)
        p.finished.connect(lambda *_:self.failed(p));p.errorOccurred.connect(lambda *_:self.failed(p) if p.error()==QProcess.ProcessError.FailedToStart else None)
        p.start(sys.executable,['--telemetry-worker'] if getattr(sys,'frozen',False) else [self.entry,'--telemetry-worker']);self.watch.start()
    def configure(self,audio=None,monitor=None):
        if audio is not None:self.config['audio']=bool(audio)
        if monitor is not None:self.config['monitor']=bool(monitor)
        if self.process and self.process.state()==QProcess.ProcessState.Running:self.process.write((json.dumps({'action':'configure',**self.config})+'\n').encode())
    def read(self):
        if not self.process:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        if len(self.buffer)>1024*1024:self.buffer=b'';return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:message=json.loads(line)
            except ValueError:continue
            self.last_message=time.monotonic();data={**EMPTY,**message}
            # Bound and sanitize data before it reaches QML animations.
            data['levels']=[max(0.,min(1.,float(v))) for v in data.get('levels',[])[:32]]
            self.apply(data)
    def apply(self,data):
        old=self.data;self.data=data
        if data['levels']!=old['levels']:self.levelsChanged.emit()
        if {k:v for k,v in data.items() if k!='levels'}!={k:v for k,v in old.items() if k!='levels'}:self.changed.emit()
    def failed(self,p):
        if self.process is p:self.watch.stop();self.apply({**EMPTY,'error':'정보 연결이 끊겼습니다.'})
    def check(self):
        if self.process and time.monotonic()-self.last_message>7:self.stop_worker();self.apply({**EMPTY,'error':'시스템 정보 응답 시간 초과'})
    def stop_worker(self):
        self.watch.stop();p=self.process;self.process=None
        if p:p.kill();p.waitForFinished(300);p.deleteLater()
    def close(self):self.closed=True;self.stop_worker()
