import asyncio,base64,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from media_worker import SessionAdapter,pick_session,timeline_values

class Session:
    def __init__(self,source='Spotify.exe',playing=True):
        self.source_app_user_model_id=source;self.status=4 if playing else 5;self.calls=[];self.handlers=[];self.reads=0
        self.controls=NS(is_play_enabled=True,is_pause_enabled=True,is_play_pause_toggle_enabled=False,is_next_enabled=True,is_previous_enabled=True,is_playback_position_enabled=True)
        self.meta=NS(title='입춘',artist='한로로',album_artist='',album_title='입춘',thumbnail=None)
    def get_playback_info(self):return NS(playback_status=self.status,controls=self.controls)
    def get_timeline_properties(self):return NS(start_time=timedelta(seconds=2),end_time=timedelta(seconds=182),position=timedelta(seconds=32),last_updated_time=datetime.now(timezone.utc))
    async def try_get_media_properties_async(self):self.reads+=1;return self.meta
    def add_media_properties_changed(self,handler):self.handlers.append(handler);return handler
    def remove_media_properties_changed(self,token):self.handlers.remove(token)
    async def try_pause_async(self):self.calls.append('pause');self.status=5;return True
    async def try_play_async(self):self.calls.append('play');self.status=4;return True
    async def try_toggle_play_pause_async(self):self.calls.append('toggle');return True
    async def try_skip_next_async(self):self.calls.append('next');return True
    async def try_skip_previous_async(self):self.calls.append('previous');return True
    async def try_change_playback_position_async(self,ticks):self.calls.append(ticks);return True

class Manager:
    def __init__(self,sessions):self.sessions=sessions
    def get_sessions(self):return self.sessions
    def get_current_session(self):return self.sessions[0] if self.sessions else None


def test_selection_prefers_playing_but_pinned_app_never_falls_back():
    a=Session('Spotify',False);b=Session('msedge',True)
    assert pick_session([a,b],a) is b
    assert pick_session([a,b],b,'Spotify') is a
    assert pick_session([b],b,'Spotify') is None


def test_metadata_controls_seek_units_switch_and_disconnect():
    async def scenario():
        a=Session();b=Session('msedge.exe');manager=Manager([a,b]);adapter=SessionAdapter(manager,None)
        data=await adapter.snapshot();assert data['title']=='입춘' and data['playing'] and data['canSeek'] and data['position']>=30000
        await adapter.snapshot();assert a.reads==1
        assert await adapter.command({'action':'toggle','source':a.source_app_user_model_id});assert a.calls==['pause']
        assert await adapter.command({'action':'seek','source':a.source_app_user_model_id,'fraction':.5});assert a.calls[-1]==920000000
        assert not await adapter.command({'action':'next','source':'wrong app'})
        a.controls.is_next_enabled=False
        assert not await adapter.command({'action':'next','source':a.source_app_user_model_id})
        await adapter.command({'action':'select','source':'msedge.exe'});data=await adapter.snapshot()
        assert data['source']=='msedge.exe' and not a.handlers
        manager.sessions=[a];data=await adapter.snapshot();assert not data['connected'] and data['cover']=='' and not data['canNext']
        adapter.unsubscribe()
    asyncio.run(scenario())


def test_artwork_buffer_and_media_event_refresh():
    async def scenario():
        closed=[]
        class Stream:
            size=4
            def close(self):closed.append('stream')
        class Ref:
            async def open_read_async(self):return Stream()
        class Reader:
            def __init__(self,stream):pass
            async def load_async(self,count):return count
            def read_bytes(self,data):data[:]=b'abcd'
            def close(self):closed.append('reader')
        s=Session();s.meta.thumbnail=Ref();adapter=SessionAdapter(Manager([s]),Reader)
        data=await adapter.snapshot();assert base64.b64decode(data['cover'])==b'abcd' and set(closed)=={'reader','stream'}
        s.meta=NS(title='다음 곡',artist='가수',album_artist='',album_title='',thumbnail=None)
        s.handlers[0]();data=await adapter.snapshot();assert data['title']=='다음 곡' and data['cover']==''
        adapter.unsubscribe()
    asyncio.run(scenario())


def test_qt_bridge_artwork_and_control_capabilities(tmp_path):
    from PySide6.QtCore import QBuffer,QByteArray,QIODevice
    from PySide6.QtGui import QImage,QColor
    from PySide6.QtWidgets import QApplication
    from media_link import MediaLink
    app=QApplication.instance() or QApplication([])
    link=MediaLink(tmp_path,'unused');sent=[];link.send=lambda request:sent.append(request) or True
    image=QImage(100,70,QImage.Format_RGB32);image.fill(QColor('red'));blob=QByteArray();buffer=QBuffer(blob);buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
    cover=base64.b64encode(bytes(blob)).decode()
    link.apply({'connected':True,'source':'Spotify','title':'A','cover':cover,'canPlayPause':True})
    url=link.data['cover'];assert url.startswith('file:')
    link.apply({'connected':True,'source':'Spotify','title':'A','cover':'@same','canPlayPause':True})
    assert link.data['cover']==url
    assert not link.command('next') and not sent
    assert link.command('toggle') and sent[0]['source']=='Spotify'
    link.select('msedge');assert not link.data['connected'] and link.data['cover']=='' and not link.data['canPlayPause']
    assert sent[-1]=={'action':'select','source':'msedge'}
    link.close()


def test_media_worker_process_roundtrip_and_watchdog(tmp_path,monkeypatch):
    import media_link
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    app=QApplication.instance() or QApplication([])
    entry=tmp_path/'fake.py';entry.write_text('import json,sys,time\nfor line in sys.stdin:\n r=json.loads(line)\n print(json.dumps({"type":"snapshot","connected":True,"source":r.get("source"),"title":"Live","playing":True}),flush=True)\n')
    link=media_link.MediaLink(tmp_path,entry)
    monkeypatch.setattr(media_link.sys,'platform','win32');link.preferred='Spotify';link.start()
    for _ in range(40):
        QTest.qWait(25)
        if link.data['title']=='Live':break
    assert link.data['title']=='Live' and link.data['source']=='Spotify'
    link.last_message=time.monotonic()-20;link.watchdog()
    assert link.process is None and not link.data['connected'] and '초과' in link.data['error']
    link.close()


def test_windowed_worker_reopens_inherited_pipe_handles(monkeypatch):
    import ctypes,io,media_worker,os
    events=[]
    def get_handle(which):events.append(which);return 0x123456789
    kernel=NS(GetStdHandle=get_handle)
    monkeypatch.setattr(ctypes,'WinDLL',lambda *a,**k:kernel,raising=False)
    monkeypatch.setattr(os,'O_BINARY',0x8000,raising=False)
    monkeypatch.setitem(sys.modules,'msvcrt',NS(open_osfhandle=lambda raw,flags:events.append(raw) or 42))
    monkeypatch.setattr(os,'fdopen',lambda fd,mode,**kwargs:events.append((fd,mode)) or io.StringIO())
    monkeypatch.setattr(media_worker.sys,'stdout',None)
    output=media_worker.stdio('stdout',-11)
    assert output is not None and events==[0xfffffff5,0x123456789,(42,'w')]


def test_build_collects_winrt_and_outputs_folder_bundle():
    import build_release
    args=build_release.command()
    assert '--onedir' in args and '--windowed' in args
    for module in build_release.PROJECTIONS:
        assert any(args[i:i+2]==['--collect-all',module] for i in range(len(args)-1))
