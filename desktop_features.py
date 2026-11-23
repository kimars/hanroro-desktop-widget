"""Focus timer, independent of wallpaper state."""
import math,time
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer,QUrl
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput

class TimerEngine:
    def __init__(self,state,clock=time.time):self.state=state;self.clock=clock
    def remaining(self):
        return max(0,math.ceil(self.state['deadline']-self.clock())) if self.state['deadline'] else max(0,int(self.state['remaining']))
    def start(self):
        if self.remaining()==0:self.state['remaining']=self.state['minutes']*60
        if not self.state['deadline']:self.state['deadline']=self.clock()+self.state['remaining']
        self.state['finished']=False
    def pause(self):self.state['remaining']=self.remaining();self.state['deadline']=0
    def reset(self):self.state.update(remaining=self.state['minutes']*60,deadline=0,finished=False)
    def tick(self):
        if self.state['deadline'] and self.remaining()==0:self.state.update(remaining=0,deadline=0,finished=True);return True
        return False

class DesktopFeatures(QObject):
    changed=Signal();persist=Signal();notice=Signal(str)
    def __init__(self,store,assets,parent=None):
        super().__init__(parent);self.store=store;self.engine=TimerEngine(store.data['focusTimer']);self.assets=Path(assets);self.ringing=False
        self.output=QAudioOutput(self);self.player=QMediaPlayer(self);self.player.setAudioOutput(self.output);self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.errorOccurred.connect(self.audio_error);self.stop_timer=QTimer(self);self.stop_timer.setSingleShot(True);self.stop_timer.timeout.connect(self.stop_alarm)
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.tick);self.timer.start();self._last_second=None
        # Do not play an old alarm merely because the app was reopened after its deadline.
        if self.engine.tick():self.persist.emit()
    def tick(self):
        completed=self.engine.tick()
        if completed:self.persist.emit();self.play_alarm();self.notice.emit('집중 타이머가 끝났어요.' if self.store.data['focusTimer']['phase']=='focus' else '휴식 시간이 끝났어요.')
        second=int(time.time())
        if completed or second!=self._last_second:self._last_second=second;self.changed.emit()
    def snapshot(self):
        state=self.store.data['focusTimer'];remaining=self.engine.remaining();total=max(1,state['minutes']*60)
        return {'remaining':remaining,'label':f'{remaining//60:02d}:{remaining%60:02d}','running':bool(state['deadline']),'finished':state['finished'],'phase':state['phase'],'minutes':state['minutes'],'progress':max(0.,min(1.,1-remaining/total)),'ringing':self.ringing}
    def toggle(self):
        if self.ringing:self.stop_alarm();return
        if self.store.data['focusTimer']['deadline']:self.engine.pause()
        else:self.engine.start()
        self.persist.emit();self.changed.emit()
    def reset(self):self.engine.reset();self.stop_alarm();self.persist.emit();self.changed.emit()
    def set_duration(self,minutes,phase=None):
        state=self.store.data['focusTimer'];state['minutes']=max(1,min(180,int(minutes)))
        if phase:state['phase']=phase
        self.reset()
    def play_alarm(self):
        self.stop_alarm();state=self.store.data['focusTimer'];path=state['alarmFile'] if state['alarmMode']=='file' else str(self.assets/'alarm/default.wav')
        if not path or not Path(path).is_file():path=str(self.assets/'alarm/default.wav')
        self.output.setVolume(state['alarmVolume']);self.player.setSource(QUrl.fromLocalFile(path));self.player.play();self.ringing=True;self.stop_timer.start(120000);self.changed.emit()
    def audio_error(self,error,message):
        if message:
            self.notice.emit('알람 파일을 재생하지 못했습니다. 다른 파일을 선택하세요.');self.stop_alarm()
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
    def stop_alarm(self):self.player.stop();self.stop_timer.stop();self.ringing=False;self.changed.emit()
    def reload(self):self.engine=TimerEngine(self.store.data['focusTimer']);self.changed.emit()
    def close(self):self.timer.stop();self.stop_alarm()
