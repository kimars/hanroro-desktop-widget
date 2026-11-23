import asyncio,copy,json,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PySide6.QtCore import QObject,QDate,QDateTime
from PySide6.QtQml import QJSValue
from PySide6.QtWidgets import QApplication,QTabWidget
from PySide6.QtTest import QTest
from desktop_features import TimerEngine
from state import DEFAULT,Store,validate,WIDGET_SIZES
from telemetry_worker import spectrum,Counters


def test_timer_pause_resume_and_completion_only_once():
    now=[1000.];s=copy.deepcopy(DEFAULT['focusTimer']);engine=TimerEngine(s,lambda:now[0])
    engine.start();now[0]+=12;assert engine.remaining()==1488
    engine.pause();now[0]+=300;assert engine.remaining()==1488
    engine.start();now[0]+=1488;assert engine.tick() and s['finished'] and not engine.tick()
    engine.start();assert engine.remaining()==1500
    engine.reset();assert engine.remaining()==1500 and not s['deadline']


def test_legacy_concert_settings_are_removed():
    state=validate({'concerts':[{'id':'old','title':'공연','start':'2027-01-01T18:00:00+09:00'}],'selectedConcert':'old','widgets':{'countdown':{'visible':True}}})
    assert 'concerts' not in state and 'selectedConcert' not in state and 'countdown' not in state['widgets']


def test_fft_real_sound_frequency_and_silence():
    rate=48000;signal=np.sin(2*np.pi*1000*np.arange(2048)/rate)*.4
    values=spectrum(signal,1,rate);assert len(values)==32 and max(values)>.7
    edges=np.geomspace(35,18000,33);peak=int(np.argmax(values));assert edges[peak]<1100 and edges[peak+1]>900
    assert spectrum(np.zeros(4096),2,rate)==[0.]*32
    assert spectrum(np.column_stack([signal,signal]).ravel(),2,rate)==values


def test_alarm_media_roundtrip_and_untrusted_values(tmp_path):
    store=Store(tmp_path/'data');media=tmp_path/'alarm.mp4';media.write_bytes(b'owned alarm fixture');store.data['focusTimer']['alarmFile']=store.ingest(media);store.data['focusTimer']['alarmMode']='file'
    archive=tmp_path/'scene.hanroom';store.export_scene(archive,'unused');other=Store(tmp_path/'other');other.import_scene(archive)
    assert Path(other.data['focusTimer']['alarmFile']).read_bytes()==media.read_bytes()
    d=validate({'focusTimer':{'minutes':999,'remaining':-2,'deadline':float('nan'),'alarmVolume':-1},'concerts':[{'title':'bad','start':'garbage'}]})
    assert d['focusTimer']['minutes']==180 and d['focusTimer']['remaining']==0 and d['focusTimer']['deadline']==0 and d['focusTimer']['alarmVolume']==0 and 'concerts' not in d
    for key,row in d['widgets'].items():assert row['x']+WIDGET_SIZES[key][0]*row['scale']<=1600 and row['y']+WIDGET_SIZES[key][1]*row['scale']<=900


def test_live_counters_are_numeric_and_unsupported_gpu_is_not_zero():
    c=Counters()
    try:
        s=c.sample();assert 0<=s['cpu']<=100 and 0<=s['ram']<=100 and s['ramTotal']>0
        if c.gpu is None:assert s['gpu'] is None
    finally:c.close()


def test_scene_new_cards_loro_clock_and_settings(tmp_path):
    from main import Program
    app=QApplication.instance();p=Program(app,SimpleNamespace(data_dir=str(tmp_path),render=None,smoke_run=False,preview=True))
    try:
        QTest.qWait(300);root=p.preview.rootObject();assert not p.errors
        for name in ['systemCard','focusCard']:assert root.findChild(QObject,name) is not None
        clock=root.findChild(QObject,'clockTime')
        from PySide6.QtCore import QTime
        for hour,minute,expected in [(11,11,'로로시'),(23,11,'로로시'),(11,12,'11:12'),(0,11,'00:11')]:
            root.setProperty('now',QDateTime(QDate(2026,11,22),QTime(hour,minute)));assert clock.property('text')==expected
        p.settings(7);panel=p.bridge._settings;tabs=panel.stack.widget(7).findChild(QTabWidget);assert tabs.count()==1
        panel.focus_minutes.setValue(35);assert p.bridge.features['remaining']==2100
        p.bridge.timerToggle();assert p.bridge.features['running'];p.bridge.timerToggle();assert not p.bridge.features['running']
        assert root.findChild(QObject,'countdownCard') is None and not hasattr(panel,'concert_list')
        assert not p.errors
    finally:
        p.shutdown()
        for v in p.bridge.views:v.hide();v.deleteLater()
        if p.bridge._settings:p.bridge._settings.close();p.bridge._settings.deleteLater()
        QTest.qWait(20)


def test_resume_preserves_paused_source_and_reacquires_fresh_session():
    from test_media_link import Session,Manager
    from media_worker import SessionAdapter,pick_session
    async def scenario():
        old=Session('Spotify.exe',False);unrelated=Session('msedge.exe',False);assert pick_session([unrelated,old],unrelated,previous='Spotify.exe') is old
        manager=Manager([old]);a=SessionAdapter(manager,None);await a.snapshot()
        fresh=Session('Spotify.exe',False);fresh.controls.is_play_enabled=False;fresh.controls.is_play_pause_toggle_enabled=True;manager.sessions=[fresh]
        assert await a.command({'action':'toggle','source':'Spotify.exe'}) and fresh.calls==['play'] and not old.calls
        assert (await a.snapshot())['canPlayPause'];a.unsubscribe()
    asyncio.run(scenario())


def test_resume_acknowledged_but_stalled_uses_targeted_wake(monkeypatch):
    from test_media_link import Session,Manager
    from media_worker import SessionAdapter
    import app_windows
    calls=[];monkeypatch.setattr(app_windows,'media_app_command',lambda source,play:calls.append((source,play)) or True)
    async def scenario():
        class Stalled(Session):
            async def try_play_async(self):return True
        s=Stalled(playing=False);a=SessionAdapter(Manager([s]),None);await a.snapshot()
        assert await a.command({'action':'toggle','source':'Spotify.exe'})
        assert calls==[('Spotify.exe',True)];a.unsubscribe()
    asyncio.run(scenario())
