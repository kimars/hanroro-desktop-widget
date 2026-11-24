"""Desktop announcement and an opt-in, cancellable update countdown."""
from PySide6.QtCore import QObject,Signal,QTimer
from update_worker import version_tuple
from release_info import VERSION

class UpdatePrompt(QObject):
    changed=Signal()
    def __init__(self,updater,store,can_install=lambda:True,parent=None):
        super().__init__(parent);self.updater=updater;self.store=store;self.can_install=can_install
        self.dismissed=set();self.demo=False;self.data={'visible':False,'version':'','phase':'available','progress':0,'seconds':0,'waiting':False,'demo':False}
        self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.tick)
        updater.available.connect(self.available);updater.changed.connect(self.sync)
    def show(self,version,demo=False):
        self.demo=demo;self.timer.stop()
        self.data.update(visible=True,version=version,phase='available',progress=0,seconds=0,waiting=False,demo=demo)
        if not demo and self.store.data['updatesAutoInstall']:
            self.data['seconds']=15;self.timer.start()
        self.changed.emit()
    def preview(self):self.show(VERSION,True)
    def available(self,version):
        try:
            if version_tuple(version)<=version_tuple(VERSION):return
        except ValueError:return
        if version in self.dismissed:return
        if self.data['visible'] and self.data['version']==version and not self.demo:return
        self.show(version)
    def dismiss(self):
        self.timer.stop()
        if not self.demo:self.dismissed.add(self.data['version'])
        self.data.update(visible=False,seconds=0,waiting=False);self.changed.emit()
    def configure(self):
        self.timer.stop();self.data.update(seconds=0,waiting=False)
        if self.data['visible'] and not self.demo and self.data['phase']=='available' and self.store.data['updatesAutoInstall']:
            self.data['seconds']=15;self.timer.start()
        self.changed.emit()
    def tick(self):
        if not self.store.data['updatesAutoInstall'] or not self.data['visible'] or self.demo:
            self.timer.stop();return
        if not self.can_install():self.data['waiting']=True;self.changed.emit();return
        self.data['waiting']=False;self.data['seconds']=max(0,self.data['seconds']-1);self.changed.emit()
        if self.data['seconds']==0:self.act()
    def act(self):
        if self.demo:return False
        if not self.can_install():self.data['waiting']=True;self.changed.emit();return False
        self.timer.stop();self.data.update(seconds=0,waiting=False)
        status=self.updater.data['status']
        if status in ('checking','downloading','installing'):return False
        if status=='ready':return self.updater.install()
        if status in ('available','error'):
            self.updater.download();return True
        return False
    def sync(self):
        if not self.data['visible'] or self.demo:return
        status=self.updater.data['status']
        if status in ('downloading','ready','installing','error'):
            self.timer.stop();self.data.update(phase=status,progress=self.updater.data.get('progress',0),seconds=0,waiting=False);self.changed.emit()
        elif status in ('idle','current'):
            self.timer.stop();self.data.update(visible=False,seconds=0,waiting=False);self.changed.emit()
    def close(self):self.timer.stop()
