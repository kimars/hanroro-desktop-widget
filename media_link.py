"""Qt-side media state and killable worker transport; never calls WinRT on the UI thread."""
import base64,json,logging,sys,time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QProcess,QTimer,QUrl,Qt,QBuffer,QByteArray,QIODevice
from PySide6.QtGui import QImage,QImageReader

EMPTY={'connected':False,'sessions':[],'source':'','sourceName':'','title':'','artist':'','album':'','cover':'','playing':False,'position':0,'duration':0,'start':0,'canPlayPause':False,'canNext':False,'canPrevious':False,'canSeek':False,'error':''}

class MediaLink(QObject):
    changed=Signal();notice=Signal(str)
    def __init__(self,directory,entry,parent=None):
        super().__init__(parent);self.directory=Path(directory);self.entry=str(entry);self.data=dict(EMPTY);self.preferred='';self.process=None;self.buffer=b'';self.last_message=0;self.last_cover='';self.cover_url='';self.closed=False
        self.watch=QTimer(self);self.watch.setInterval(2000);self.watch.timeout.connect(self.watchdog)
        if sys.platform=='win32':QTimer.singleShot(0,self.start)
        else:self.data['error']='음악 앱 연결은 Windows에서 지원합니다.'
    def start(self):
        if self.closed or sys.platform!='win32':return
        self.stop_worker();self.buffer=b'';self.last_message=time.monotonic()
        # Deferred process deletion owns its lifetime; no QObject parent teardown
        # may destroy it a second time while finished/read signals are unwinding.
        p=QProcess();self.process=p
        p.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        p.readyReadStandardOutput.connect(self.read_output);p.readyReadStandardError.connect(lambda:logging.debug('media worker: %s',bytes(p.readAllStandardError()).decode('utf-8','replace')[-500:]))
        p.started.connect(lambda:self.send({'action':'select','source':self.preferred}))
        p.finished.connect(lambda *_:self.failed(p));p.errorOccurred.connect(lambda *_:self.failed(p) if p.error()==QProcess.ProcessError.FailedToStart else None)
        if getattr(sys,'frozen',False):args=['--media-worker']
        else:args=[self.entry,'--media-worker']
        p.start(sys.executable,args);self.watch.start()
    def failed(self,p):
        if self.process is not p:return
        self.watch.stop();self.apply({'error':self.data.get('error') or '음악 앱 연결이 종료됐습니다. 새로고침하세요.'})
    def read_output(self):
        if not self.process:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        if len(self.buffer)>4*1024*1024:self.buffer=b'';self.apply({'error':'앨범 정보가 너무 큽니다.'});return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:message=json.loads(line)
            except (ValueError,UnicodeError):continue
            self.last_message=time.monotonic()
            if message.get('type')=='snapshot':self.apply(message)
            elif message.get('type')=='notice':self.notice.emit(str(message.get('message','')))
    def apply(self,snapshot):
        data={**EMPTY,**{k:v for k,v in snapshot.items() if k in EMPTY}}
        if not data['connected']:
            # Never leave the previous provider's song, artwork or enabled controls behind.
            data={**EMPTY,'sessions':data['sessions'],'error':data['error']}
        cover=data['cover'];data['cover']=''
        if cover:
            if cover=='@same' or cover==self.last_cover:data['cover']=self.cover_url
            else:
                self.cover_url=''
                try:
                    blob=base64.b64decode(cover,validate=True)
                    if len(blob)>2*1024*1024:raise ValueError('oversized cover')
                    buffer=QBuffer();buffer.setData(QByteArray(blob));buffer.open(QIODevice.OpenModeFlag.ReadOnly);reader=QImageReader(buffer);size=reader.size()
                    if size.isValid():reader.setScaledSize(size.scaled(600,600,Qt.AspectRatioMode.KeepAspectRatio))
                    image=reader.read()
                    if not image.isNull():
                        self.directory.mkdir(parents=True,exist_ok=True)
                        # Content-based URLs prevent stale artwork in Qt's image cache.
                        import hashlib
                        path=self.directory/('media-cover-'+hashlib.sha256(blob).hexdigest()[:16]+'.png');image.save(str(path));data['cover']=QUrl.fromLocalFile(str(path)).toString();self.cover_url=data['cover']
                        for old in self.directory.glob('media-cover-*.png'):
                            if old!=path:
                                try:old.unlink()
                                except OSError:pass
                except (OSError,ValueError):pass
            if cover!='@same':self.last_cover=cover
        else:self.last_cover=''
        if data!=self.data:self.data=data;self.changed.emit()
    def send(self,request):
        if not self.process or self.process.state()!=QProcess.ProcessState.Running:return False
        if self.process.bytesToWrite()>8192:return False
        self.process.write((json.dumps(request)+'\n').encode('utf-8'));return True
    def command(self,action,**kwargs):
        capability={'toggle':'canPlayPause','next':'canNext','previous':'canPrevious','seek':'canSeek'}.get(action)
        if capability and not self.data[capability]:return False
        return self.send({'action':action,'source':self.data['source'],**kwargs})
    def select(self,source):
        self.preferred=source
        # Clear outgoing controls until the worker confirms this provider.
        self.apply({'sessions':self.data['sessions']});self.send({'action':'select','source':source})
    def refresh(self):
        if self.process and self.process.state()==QProcess.ProcessState.Running and not self.data['error']:self.send({'action':'refresh'})
        else:self.start()
    def watchdog(self):
        if self.process and time.monotonic()-self.last_message>12:
            self.stop_worker();self.apply({'error':'음악 앱 응답 시간이 초과됐습니다. 새로고침하세요.'})
    def stop_worker(self):
        self.watch.stop();p=self.process;self.process=None
        if p:
            p.kill();p.waitForFinished(300);p.deleteLater()
    def close(self):self.closed=True;self.stop_worker()
