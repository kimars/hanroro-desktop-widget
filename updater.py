import hashlib,json,subprocess,sys,time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QProcess,QTimer
from release_info import VERSION,UPDATE_REPOSITORY

class Updater(QObject):
    changed=Signal();available=Signal(str);notice=Signal(str)
    def __init__(self,directory,entry,parent=None):
        super().__init__(parent);self.directory=Path(directory)/'updates';self.entry=str(entry);self.process=None;self.buffer=b'';self.closed=False;self.last_message=0;self.install_after=False
        self.probing=False;self.probe_failures=0;self.probe_after=0
        self.handoff_timer=QTimer(self);self.handoff_timer.setInterval(1500);self.handoff_timer.timeout.connect(self.handoff_result)
        self.data={'status':'idle','version':VERSION,'current':VERSION,'progress':0,'message':'','notes':''}
        self.watch=QTimer(self);self.watch.setInterval(3000);self.watch.timeout.connect(self.watchdog)
    def publish(self,data):
        if data.get('status')=='unchanged':self.probe_failures=0;self.probe_after=0;return
        if self.probing and data.get('status')=='error':
            self.probe_failures+=1;self.probe_after=time.monotonic()+min(900,60*2**min(self.probe_failures-1,4));return
        if data.get('status')=='available':self.probe_failures=0;self.probe_after=0
        self.data={**self.data,**data,'current':VERSION};self.changed.emit()
        if data.get('status')=='available':self.available.emit(data['version'])
        if data.get('status')=='ready' and self.install_after and not self.process:self.install_after=False;QTimer.singleShot(0,self.install)
    def check(self):self.start('check')
    def probe(self):
        if self.closed or self.process or time.monotonic()<self.probe_after:return
        if self.data['status'] in ('ready','downloading','installing'):return
        self.start('probe')
    def download(self):self.install_after=True;self.start('download')
    def cancel(self):
        self.install_after=False;self.stop()
        for part in self.directory.glob('HanroroWidget-*.part'):
            try:part.unlink()
            except OSError:pass
        self.publish({'status':'idle','message':'업데이트를 취소했습니다.','progress':0})
    def start(self,action):
        if self.closed or self.process:return
        self.probing=action=='probe'
        if not self.probing:self.publish({'status':'checking' if action=='check' else 'downloading','progress':0,'message':''})
        self.buffer=b''
        p=QProcess();self.process=p;self.last_message=time.monotonic()
        current=self.data['version'] if self.probing and self.data['status']=='available' else VERSION
        request={'action':action,'repository':UPDATE_REPOSITORY,'current':current,'directory':str(self.directory)}
        def send():p.write((json.dumps(request)+'\n').encode());p.closeWriteChannel()
        p.started.connect(send);p.readyReadStandardOutput.connect(self.read);p.readyReadStandardError.connect(lambda:p.readAllStandardError())
        p.finished.connect(lambda code,status:self.finished(p));p.errorOccurred.connect(lambda error:self.failed(p,'업데이트 확인을 시작하지 못했습니다.') if error==QProcess.ProcessError.FailedToStart else None)
        p.start(sys.executable,['--update-worker'] if getattr(sys,'frozen',False) else [self.entry,'--update-worker']);self.watch.start()
    def read(self):
        if not self.process:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        if len(self.buffer)>1024**2:self.failed(self.process,'업데이트 응답이 너무 큽니다.');return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:data=json.loads(line)
            except ValueError:continue
            if not isinstance(data,dict):continue
            self.last_message=time.monotonic();self.publish(data)
    def finished(self,p):
        if self.process is not p:return
        self.read();self.process=None;self.watch.stop();p.deleteLater()
        if self.data['status']=='ready' and self.install_after:self.install_after=False;QTimer.singleShot(0,self.install)
        if self.probing:self.probing=False;return
        if self.data['status'] in ('checking','downloading'):self.publish({'status':'error','message':'업데이트 연결이 끊겼습니다. 다시 확인해주세요.'})
    def failed(self,p,message):
        if self.process is p:self.stop();self.publish({'status':'error','message':message});self.probing=False
    def watchdog(self):
        if self.process and time.monotonic()-self.last_message>90:self.failed(self.process,'업데이트 연결 시간이 초과됐습니다.')
    def install(self):
        if sys.platform!='win32':self.notice.emit('업데이트 설치는 Windows에서 지원합니다.');return False
        if self.data['status']!='ready':return False
        target=Path(self.data.get('path',''))
        try:
            if target.parent.resolve()!=self.directory.resolve() or not target.is_file():raise ValueError('업데이트 파일을 찾을 수 없습니다.')
            # Check again just before launch to catch replacement of a cached download.
            # Hashing 100 MB here would block input: the installer is launched only after
            # this verification in the dedicated handoff process.
            request=self.directory/'install-request.json';request.with_suffix('.result.json').unlink(missing_ok=True);request.write_text(json.dumps({'path':str(target),'sha256':self.data['sha256'],'size':self.data['size']}),encoding='utf-8')
            command=[sys.executable,'--install-update',str(request)] if getattr(sys,'frozen',False) else [sys.executable,self.entry,'--install-update',str(request)]
            subprocess.Popen(command,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
            self.handoff_started=time.monotonic();self.handoff_timer.start();self.publish({'status':'installing','message':'앱을 닫고 업데이트를 설치합니다.'});return True
        except (OSError,ValueError) as error:self.publish({'status':'error','message':str(error)});return False
    def handoff_result(self):
        if time.monotonic()-getattr(self,'handoff_started',time.monotonic())>90:
            self.handoff_timer.stop();self.publish({'status':'error','message':'설치가 시작되지 않았습니다. Windows 설치 확인창을 확인하고 다시 시도해주세요.'});return
        result=self.directory/'install-request.result.json'
        if result.exists():
            self.handoff_timer.stop()
            try:data=json.loads(result.read_text('utf-8'))
            except (OSError,ValueError):return
            self.publish({'status':'error','message':data.get('error','업데이트 설치를 시작하지 못했습니다.')})
    def stop(self):
        self.watch.stop();p=self.process;self.process=None
        if p:p.kill();p.waitForFinished(300);p.deleteLater()
    def close(self):self.closed=True;self.handoff_timer.stop();self.stop()

def install_update(request_path):
    """Verify in a detached process. NSIS closes the old app and restarts the new one."""
    import ctypes
    try:
        request=Path(request_path);data=json.loads(request.read_text('utf-8'));target=Path(data['path'])
        if target.parent.resolve()!=request.parent.resolve() or target.suffix.lower()!='.exe':raise ValueError('업데이트 경로가 올바르지 않습니다.')
        digest=hashlib.sha256()
        with target.open('rb') as source:
            if source.read(2)!=b'MZ':raise ValueError('설치 파일이 올바르지 않습니다.')
            source.seek(0)
            for block in iter(lambda:source.read(1024**2),b''):digest.update(block)
        if target.stat().st_size!=data['size'] or digest.hexdigest()!=data['sha256']:raise ValueError('업데이트 파일 검증에 실패했습니다.')
        # Do not wait from a Python executable that the installer needs to replace.
        # The setup's own IPC closer waits for this app process, so exit immediately.
        import os
        os.startfile(str(target),'open','/S /AUTOUPDATE')
        return 0
    except Exception as error:
        try:Path(request_path).with_suffix('.result.json').write_text(json.dumps({'error':str(error)}),encoding='utf-8')
        except OSError:pass
        return 1
