"""A killable process and deadline for Windows COM/SPI wallpaper operations."""
import json,logging,sys,uuid
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QProcess,QTimer

class NativeJobs(QObject):
    completed=Signal(dict,bool,str)
    def __init__(self,directory,entry,parent=None,timeout_ms=10000):
        super().__init__(parent);self.directory=Path(directory);self.entry=str(entry);self.timeout_ms=timeout_ms;self.process=None
    @property
    def busy(self):return self.process is not None
    def start(self,request):
        if self.busy:return False
        self.directory.mkdir(parents=True,exist_ok=True)
        path=self.directory/('native-job-'+uuid.uuid4().hex+'.json');path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
        process=QProcess(self);timer=QTimer(process);timer.setSingleShot(True)
        self.process=process;state={'done':False,'timed_out':False,'cancelled':False}
        def finish(*_):
            if state['done']:return
            state['done']=True;timer.stop();ok=False;detail=''
            try:
                if state['cancelled']:detail='cancelled'
                elif state['timed_out']:detail='Windows 배경 설정 응답 시간 초과 (10초)'
                elif process.error()==QProcess.ProcessError.FailedToStart:detail=process.errorString()
                else:
                    answer=json.loads(path.with_suffix('.result.json').read_text('utf-8'))
                    ok=bool(answer.get('ok')) and process.exitCode()==0;detail=str(answer.get('detail',''))
            except (OSError,ValueError):detail='배경 설정 작업이 결과 없이 종료됐습니다. '+bytes(process.readAllStandardError()).decode('utf-8','replace')[-1000:]
            finally:
                path.unlink(missing_ok=True);path.with_suffix('.result.json').unlink(missing_ok=True)
                if self.process is process:self.process=None
                process.deleteLater()
            self.completed.emit(request,ok,detail)
        def expired():
            state['timed_out']=True;process.kill()
        process.finished.connect(finish)
        process.errorOccurred.connect(lambda error:finish() if error==QProcess.ProcessError.FailedToStart else None)
        timer.timeout.connect(expired)
        process._cancel_state=state
        if getattr(sys,'frozen',False):args=['--native-job',str(path)]
        else:args=[self.entry,'--native-job',str(path)]
        process.start(sys.executable,args);timer.start(self.timeout_ms)
        return True
    def cancel(self):
        process=self.process
        if process is not None:
            process._cancel_state['cancelled']=True;process.kill();process.waitForFinished(300)
