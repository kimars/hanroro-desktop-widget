"""Isolated WinRT session adapter. No Qt objects or UI work in this process."""
import asyncio,base64,json,os,queue,sys,threading,time
from datetime import datetime,timezone

MAX_COVER=2*1024*1024

def app_name(source):
    low=source.lower()
    for key,name in [('spotify','Spotify'),('soundcloud','SoundCloud'),('msedge','Microsoft Edge'),('chrome','Google Chrome'),('firefox','Firefox'),('vlc','VLC'),('music','음악')]:
        if key in low:return name
    return source.split('!')[0].split('_')[0][-80:] or '미디어 앱'

def milliseconds(value):return max(0,int(value.total_seconds()*1000))

def timeline_values(timeline,playing):
    start=milliseconds(timeline.start_time);end=milliseconds(timeline.end_time);position=milliseconds(timeline.position)
    if playing:
        updated=timeline.last_updated_time
        if updated.tzinfo is None:updated=updated.replace(tzinfo=timezone.utc)
        position+=max(0,int((datetime.now(timezone.utc)-updated).total_seconds()*1000))
    duration=max(0,end-start)
    return {'start':start,'duration':duration,'position':min(duration,max(0,position-start)) if duration else 0}

def pick_session(sessions,current,preferred='',previous=''):
    if preferred:return next((s for s in sessions if s.source_app_user_model_id==preferred),None)
    def playing(s):
        try:return int(s.get_playback_info().playback_status)==4
        except Exception:return False
    if current and playing(current):return current
    old=next((s for s in sessions if s.source_app_user_model_id==previous),None)
    return next((s for s in sessions if playing(s)),None) or old or current or next(iter(sessions),None)

class SessionAdapter:
    def __init__(self,manager,reader_factory):
        self.manager=manager;self.reader_factory=reader_factory;self.preferred='';self.selected=None;self.source='';self.metadata={};self.cover='';self.dirty=threading.Event();self.dirty.set();self.tokens=[];self.last_metadata=0;self.cover_retry=0
    def unsubscribe(self):
        for session,name,token in self.tokens:
            try:getattr(session,'remove_'+name)(token)
            except Exception:pass
        self.tokens=[]
    async def read_cover(self,reference):
        if reference is None:return ''
        stream=None;reader=None
        try:
            stream=await reference.open_read_async()
            if not 0<int(stream.size)<=MAX_COVER:return ''
            reader=self.reader_factory(stream);loaded=int(await reader.load_async(int(stream.size)))
            if not 0<loaded<=MAX_COVER:return ''
            data=bytearray(loaded);reader.read_bytes(data)
            return base64.b64encode(data).decode('ascii')
        finally:
            if reader is not None:
                try:reader.close()
                except Exception:pass
            if stream is not None:
                try:stream.close()
                except Exception:pass
    async def snapshot(self):
        sessions=list(self.manager.get_sessions());current=self.manager.get_current_session()
        # A provider can register more than one session (e.g. multiple browser tabs).
        chosen=pick_session(sessions,current,self.preferred,self.source)
        apps=list({s.source_app_user_model_id: {'id':s.source_app_user_model_id,'name':app_name(s.source_app_user_model_id)} for s in sessions}.values())
        if chosen!=self.selected:
            self.unsubscribe();self.selected=chosen;self.source=chosen.source_app_user_model_id if chosen else '';self.metadata={};self.cover='';self.dirty.set()
            if chosen:
                for name in ['media_properties_changed']:
                    try:self.tokens.append((chosen,name,getattr(chosen,'add_'+name)(lambda *_:self.dirty.set())))
                    except Exception:pass
        base={'sessions':apps,'source':self.source,'sourceName':app_name(self.source) if self.source else '', 'connected':bool(chosen),'cover':self.cover,'title':'','artist':'','album':'','playing':False,'position':0,'duration':0,'start':0,'canPlayPause':False,'canNext':False,'canPrevious':False,'canSeek':False,'error':''}
        if chosen is None:return base
        now=time.monotonic()
        if self.dirty.is_set() or now-self.last_metadata>10:
            self.dirty.clear();self.last_metadata=now
            try:
                meta=await asyncio.wait_for(chosen.try_get_media_properties_async(),3)
                metadata={'title':meta.title or '', 'artist':meta.artist or meta.album_artist or '', 'album':meta.album_title or ''}
                changed=metadata!=self.metadata
                self.metadata=metadata
                if changed or not self.cover:
                    # Clear the preceding song's cover immediately, even if retrieval fails.
                    self.cover=''
                    try:self.cover=await asyncio.wait_for(self.read_cover(meta.thumbnail),3)
                    except Exception:pass
            except Exception:
                self.metadata={};self.cover='';self.dirty.set()
        info=chosen.get_playback_info();controls=info.controls;playing=int(info.playback_status)==4
        try:timeline=timeline_values(chosen.get_timeline_properties(),playing)
        except Exception:timeline={'position':0,'duration':0,'start':0}
        base.update(self.metadata);base.update(timeline);base.update(cover=self.cover,playing=playing,canPlayPause=bool(controls.is_play_pause_toggle_enabled or (controls.is_pause_enabled if playing else controls.is_play_enabled) or (not playing and self.metadata.get('title'))),canNext=bool(controls.is_next_enabled),canPrevious=bool(controls.is_previous_enabled),canSeek=bool(controls.is_playback_position_enabled and timeline['duration']>0))
        return base
    async def accepted_transport(self,session,was_playing):
        self.dirty.set()
        if not was_playing:
            await asyncio.sleep(.2)
            try:resumed=int(session.get_playback_info().playback_status)==4
            except Exception:resumed=False
            if not resumed:
                from app_windows import media_app_command
                media_app_command(self.source,True)
        return True
    async def command(self,request):
        action=request.get('action')
        if action=='select':self.preferred=str(request.get('source',''))[:512];return True
        if action=='refresh':self.dirty.set();return True
        if not self.selected or request.get('source')!=self.source:return False
        # Providers can replace their session object while their window is minimized.
        # Fetch a current handle by identity rather than sending commands to a stale COM object.
        fresh=next((s for s in self.manager.get_sessions() if s.source_app_user_model_id==self.source),None)
        if fresh is None:return False
        session=fresh;info=session.get_playback_info();c=info.controls
        if action=='toggle':
            playing=int(info.playback_status)==4
            # An explicit play is reliable when a provider advertises a stale toggle state.
            method=session.try_pause_async if playing else session.try_play_async
            try:
                if await asyncio.wait_for(method(),1):return await self.accepted_transport(session,playing)
            except Exception:pass
            if c.is_play_pause_toggle_enabled:
                try:
                    if await asyncio.wait_for(session.try_toggle_play_pause_async(),1):return await self.accepted_transport(session,playing)
                except Exception:pass
            # Target only this application's existing window, without changing focus.
            from app_windows import media_app_command
            return media_app_command(self.source,not playing)
        if action=='next':return bool(await session.try_skip_next_async()) if c.is_next_enabled else False
        if action=='previous':return bool(await session.try_skip_previous_async()) if c.is_previous_enabled else False
        if action=='seek' and c.is_playback_position_enabled:
            timeline=session.get_timeline_properties();start=milliseconds(timeline.start_time);end=milliseconds(timeline.end_time)
            fraction=max(0.,min(1.,float(request.get('fraction',0))))
            return bool(await session.try_change_playback_position_async(round((start+(end-start)*fraction)*10000))) if end>start else False
        return False

def stdio(name,handle):
    stream=getattr(sys,name)
    if stream is not None:return stream
    # PyInstaller --windowed / pythonw sets sys.std* to None. QProcess still supplies pipes.
    import ctypes,msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetStdHandle.argtypes=[ctypes.c_uint32];kernel.GetStdHandle.restype=ctypes.c_void_p
    raw=kernel.GetStdHandle(handle & 0xffffffff)
    if raw in (None,ctypes.c_void_p(-1).value):raise OSError('미디어 연결 파이프를 열지 못했습니다.')
    fd=msvcrt.open_osfhandle(raw,os.O_BINARY)
    return os.fdopen(fd,'r' if name=='stdin' else 'w',encoding='utf-8',buffering=1)

async def serve(input_stream,output_stream):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    from winrt.windows.storage.streams import DataReader
    manager=await GlobalSystemMediaTransportControlsSessionManager.request_async();adapter=SessionAdapter(manager,DataReader);commands=queue.Queue(maxsize=64)
    def read():
        try:
            for line in input_stream:
                if len(line)>8192:continue
                try:request=json.loads(line)
                except ValueError:continue
                if isinstance(request,dict):
                    try:commands.put_nowait(request)
                    except queue.Full:pass
        finally:
            try:commands.put_nowait({'action':'stop'})
            except queue.Full:pass
    threading.Thread(target=read,daemon=True).start()
    last_cover=None
    def write(value):
        nonlocal last_cover
        if value.get('type')=='snapshot':
            cover=value.get('cover','')
            if cover and cover==last_cover:value={**value,'cover':'@same'}
            else:last_cover=cover
        output_stream.write(json.dumps(value,ensure_ascii=True)+'\n');output_stream.flush()
    try:
        while True:
            while not commands.empty():
                request=commands.get_nowait()
                if request.get('action')=='stop':return
                try:
                    ok=await asyncio.wait_for(adapter.command(request),3)
                    if not ok:write({'type':'notice','message':'이 앱에서 해당 조작을 지원하지 않거나 연결이 바뀌었습니다.'})
                except Exception:write({'type':'notice','message':'음악 앱이 조작 요청에 응답하지 않았습니다.'})
            try:write({'type':'snapshot',**await adapter.snapshot()})
            except Exception:write({'type':'snapshot','sessions':[],'connected':False,'error':'음악 앱 정보를 읽지 못했습니다. 연결을 새로고침하세요.'})
            await asyncio.sleep(.5)
    finally:adapter.unsubscribe()

def run():
    output=None
    try:
        incoming=stdio('stdin',-10);output=stdio('stdout',-11);asyncio.run(serve(incoming,output));return 0
    except Exception as error:
        if output:
            output.write(json.dumps({'type':'snapshot','connected':False,'sessions':[],'error':'미디어 연결을 시작하지 못했습니다. 의존성 설치 후 새로고침하세요.','detail':str(error)[:500]})+'\n');output.flush()
        return 1

if __name__=='__main__':sys.exit(run())
