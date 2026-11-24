from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject,Signal
from PySide6.QtTest import QTest
from update_prompt import UpdatePrompt
from state import Store,validate

class FakeUpdater(QObject):
    available=Signal(str);changed=Signal()
    def __init__(self):super().__init__();self.data={'status':'idle','progress':0};self.downloads=0;self.installs=0
    def offer(self,version='9.0.0'):self.data.update(status='available',version=version);self.changed.emit();self.available.emit(version)
    def download(self):self.downloads+=1;self.data['status']='downloading';self.changed.emit()
    def install(self):self.installs+=1;return True

def test_automatic_install_is_opt_in_and_persisted(tmp_path):
    s=Store(tmp_path);assert not s.data['updatesAutoInstall']
    s.data['updatesAutoInstall']=True;s.save();assert Store(tmp_path).data['updatesAutoInstall']
    assert not validate({'updatesAutoInstall':'yes'})['updatesAutoInstall']

def test_countdown_waits_for_editing_and_can_be_dismissed(tmp_path):
    s=Store(tmp_path);s.data['updatesAutoInstall']=True;u=FakeUpdater();editing=[True];p=UpdatePrompt(u,s,lambda:not editing[0])
    try:
        u.offer();assert p.data['visible'] and p.data['seconds']==15
        for i in range(20):p.tick()
        assert u.downloads==0 and p.data['waiting'] and p.data['seconds']==15
        editing[0]=False
        for i in range(14):p.tick()
        assert u.downloads==0 and p.data['seconds']==1
        p.tick();assert u.downloads==1 and p.data['phase']=='downloading'
        u.offer('9.1.0');p.dismiss();assert not p.data['visible'] and not p.timer.isActive()
        u.offer('9.1.0');assert not p.data['visible']
        u.offer('9.2.0');assert p.data['visible']
    finally:p.close()

def test_manual_update_preview_and_failures_do_not_auto_install(tmp_path):
    s=Store(tmp_path);u=FakeUpdater();p=UpdatePrompt(u,s)
    try:
        u.offer();assert not p.timer.isActive();assert p.act() and u.downloads==1
        u.data.update(status='error');u.changed.emit();assert p.data['phase']=='error' and not p.timer.isActive()
        assert p.act() and u.downloads==2
        s.data['updatesAutoInstall']=True;p.preview()
        for i in range(30):p.tick()
        assert not p.act() and u.downloads==2 and p.data['demo']
    finally:p.close()

def test_same_release_does_not_restart_countdown(tmp_path):
    s=Store(tmp_path);s.data['updatesAutoInstall']=True;u=FakeUpdater();p=UpdatePrompt(u,s)
    try:
        u.offer();p.tick();u.offer();assert p.data['seconds']==14
        s.data['updatesAutoInstall']=False;p.configure();assert not p.timer.isActive() and p.data['seconds']==0
    finally:p.close()

def test_installer_waits_for_download_worker_exit(tmp_path,monkeypatch):
    from updater import Updater
    u=Updater(tmp_path,'main.py');calls=[];monkeypatch.setattr(u,'install',lambda:calls.append(True))
    class Process:
        def readAllStandardOutput(self):return b''
        def deleteLater(self):pass
    process=Process();u.process=process;u.install_after=True
    u.publish({'status':'ready'});QTest.qWait(10);assert calls==[]
    u.finished(process);QTest.qWait(10);assert calls==[True];u.close()
