"""One timed native worker and one timed inventory process; all queues are bounded."""
import json,sys,logging
from collections import OrderedDict
from PySide6.QtCore import QObject,Signal,QProcess,QTimer
log=logging.getLogger(__name__)
class ShellService(QObject):
    result=Signal(str,int,object);error=Signal(str,int,str);inventory=Signal(object);files=Signal(int,object)
    def __init__(self,entry,parent=None,enabled=None):
        super().__init__(parent);self.entry=str(entry);self.enabled=sys.platform=='win32' if enabled is None else enabled;self.process=None;self.inventory_process=None;self.pending=None;self.sequence=0;self.scan=None;self.launches=[];self.icons=OrderedDict();self.buffer=b'';self.inv_buffer=b'';self.closed=False;self.file_process=None;self.file_buffer=b''
        self.deadline=QTimer(self);self.deadline.setSingleShot(True);self.deadline.timeout.connect(self.timeout)
        self.file_deadline=QTimer(self);self.file_deadline.setSingleShot(True);self.file_deadline.setInterval(5000);self.file_deadline.timeout.connect(self.cancel_search)
        self.inv_deadline=QTimer(self);self.inv_deadline.setSingleShot(True);self.inv_deadline.setInterval(35000);self.inv_deadline.timeout.connect(self.inventory_timeout)
    def request(self,action,**data):
        self.sequence+=1;job={'id':self.sequence,'action':action,**data}
        if not self.enabled or self.closed:return self.sequence
        if action=='windows':self.scan=job
        elif action in ('launch','resolve'):self.launches=(self.launches+[job])[-8:]
        self.pump();return self.sequence
    def icon(self,row):
        if not self.enabled or self.closed:return
        key=row['key']
        if key not in self.icons:self.icons[key]=dict(row)
        while len(self.icons)>160:self.icons.popitem(last=False)
        self.pump()
    def start(self):
        p=QProcess(self);self.process=p;self.buffer=b'';p.started.connect(self.send_pending);p.readyReadStandardOutput.connect(self.read);p.readyReadStandardError.connect(lambda:p.readAllStandardError());p.finished.connect(lambda *_:self.worker_ended(p));p.errorOccurred.connect(lambda e:self.worker_failed(p) if e==QProcess.FailedToStart else None)
        p.start(sys.executable,['--shell-worker'] if getattr(sys,'frozen',False) else [self.entry,'--shell-worker'])
    def pump(self):
        if self.closed or self.pending:return
        if self.scan:self.pending=self.scan;self.scan=None
        elif self.launches:self.pending=self.launches.pop(0)
        elif self.icons:
            rows=[self.icons.popitem(last=False)[1] for _ in range(min(2,len(self.icons)))];self.sequence+=1;self.pending={'id':self.sequence,'action':'icons','rows':rows}
        else:return
        self.deadline.start(8000)
        if not self.process:self.start()
        elif self.process.state()==QProcess.Running:self.send_pending()
    def send_pending(self):
        if self.pending and self.process:self.process.write((json.dumps(self.pending)+'\n').encode())
    def read(self):
        if not self.process:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        if len(self.buffer)>2*1024*1024:self.timeout();return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:data=json.loads(line)
            except ValueError:continue
            job=self.pending
            if not job or data.get('id')!=job['id']:continue
            self.deadline.stop();self.pending=None
            if 'error' in data:self.error.emit(job['action'],job['id'],str(data['error']))
            else:self.result.emit(job['action'],job['id'],data['data'])
            QTimer.singleShot(0,self.pump)
    def worker_ended(self,p):
        if self.process is not p:p.deleteLater();return
        self.process=None;p.deleteLater()
        if self.pending:self.worker_failed(None)
    def worker_failed(self,p):
        if p and p is not self.process:return
        job=self.pending;self.pending=None;self.deadline.stop()
        if job:self.error.emit(job['action'],job['id'],'Windows shell worker stopped')
        if p and self.process is p:self.process=None;p.deleteLater()
        if not self.closed:QTimer.singleShot(0,self.pump)
    def timeout(self):
        p=self.process;self.process=None
        if p:p.kill()
        self.worker_failed(None)
    def load_inventory(self):
        if self.closed or not self.enabled or self.inventory_process:return
        p=QProcess(self);self.inventory_process=p;self.inv_buffer=b'';p.readyReadStandardOutput.connect(self.read_inventory);p.readyReadStandardError.connect(lambda:p.readAllStandardError());p.finished.connect(lambda *_:self.inventory_ended(p));p.finished.connect(p.deleteLater);p.errorOccurred.connect(lambda e:self.inventory_timeout() if e==QProcess.FailedToStart else None)
        p.start(sys.executable,['--shell-inventory'] if getattr(sys,'frozen',False) else [self.entry,'--shell-inventory']);p.closeWriteChannel();self.inv_deadline.start()
    def read_inventory(self):
        p=self.inventory_process
        if not p:return
        self.inv_buffer+=bytes(p.readAllStandardOutput())
        if len(self.inv_buffer)>2*1024*1024:self.inventory_timeout();return
        while b'\n' in self.inv_buffer:
            line,self.inv_buffer=self.inv_buffer.split(b'\n',1)
            try:self.inventory.emit(json.loads(line))
            except ValueError:continue
    def inventory_ended(self,p):
        if self.inventory_process is p:self.read_inventory();self.inventory_process=None;self.inv_deadline.stop();p.deleteLater()
    def inventory_timeout(self):
        p=self.inventory_process;self.inventory_process=None;self.inv_deadline.stop()
        if p:p.kill()
        self.inventory.emit({'phase':'taskbar','rows':[],'error':'작업 표시줄 조회 시간이 초과됐습니다.'})
    def cancel_search(self):
        self.file_deadline.stop();p=self.file_process;self.file_process=None
        if p:p.kill()
    def search(self,token,query,roots):
        self.cancel_search()
        if self.closed or not self.enabled:return
        p=QProcess(self);self.file_process=p;self.file_buffer=b''
        def started():p.write((json.dumps({'id':token,'query':query,'roots':roots})+'\n').encode());p.closeWriteChannel()
        def finished(*_):
            if self.file_process is p:
                raw=bytes(p.readAllStandardOutput())
                try:self.files.emit(token,json.loads(raw)['data'])
                except (ValueError,KeyError):self.files.emit(token,[])
                self.file_process=None;self.file_deadline.stop()
            p.deleteLater()
        p.started.connect(started);p.finished.connect(finished);p.readyReadStandardError.connect(lambda:p.readAllStandardError());p.start(sys.executable,['--shell-file-search'] if getattr(sys,'frozen',False) else [self.entry,'--shell-file-search']);self.file_deadline.start()
    def close(self):
        self.closed=True;self.cancel_search();self.deadline.stop();self.inv_deadline.stop();self.pending=None;self.icons.clear();self.scan=None;self.launches=[]
        processes=(self.process,self.inventory_process);self.process=self.inventory_process=None
        for p in processes:
            if p:
                p.readyReadStandardOutput.disconnect();p.readyReadStandardError.disconnect();p.finished.disconnect();p.errorOccurred.disconnect();p.kill();p.waitForFinished(200);p.deleteLater()
