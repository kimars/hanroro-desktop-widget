"""Versioned, atomic user data and portable scene exchange. No Qt dependency."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

WIDGET_SIZES={'clock':(600,220),'photos':(210,280),'player':(348,432),'memo':(360,260),'calendar':(280,194),'dock':(652,164),'visualizer':(340,112),'system':(340,190),'focus':(340,250)}
WIDGETS = {
    'clock': {'x':64,'y':54,'scale':1.,'visible':True,'color':''},
    'photos': {'x':1330,'y':86,'scale':.8,'visible':False,'color':''},
    'player': {'x':64,'y':296,'scale':1.,'visible':True,'color':''},
    'memo': {'x':436,'y':296,'scale':1.,'visible':True,'color':''},
    'calendar': {'x':820,'y':532,'scale':1.,'visible':True,'color':''},
    'dock': {'x':64,'y':736,'scale':.94,'visible':True,'color':''},
    'visualizer': {'x':820,'y':54,'scale':1.,'visible':True,'color':''},
    'system': {'x':1180,'y':54,'scale':1.,'visible':True,'color':''},
    'focus': {'x':1180,'y':270,'scale':1.,'visible':True,'color':''},
}

def layout_for(preset):
    result=copy.deepcopy(WIDGETS)
    if preset=='right':
        for key,row in result.items():row['x']=1600-WIDGET_SIZES[key][0]*row['scale']-row['x']
    elif preset=='bottom':
        for key,x,y in [('player',64,420),('memo',436,450),('calendar',820,480),('dock',436,724)]:result[key].update(x=x,y=y)
    return result

DEFAULT_LINKS = [
    {'title':'팬 페이지','target':'https://hanroro.mars0216.com','glyph':'home'},
    {'title':'인스타그램','target':'https://www.instagram.com/hanr0r0/','glyph':'camera'},
    {'title':'사진 보관함','target':'https://drive.google.com/drive/folders/12XMxlyG-_EHeyMdRtWctJwzu_sDwnL1u','glyph':'folder'},
    {'title':'유튜브','target':'https://www.youtube.com/results?search_query=HANRORO','glyph':'play'},
    {'title':'음악','target':'https://open.spotify.com/search/HANRORO','glyph':'music'},
    {'title':'문서','target':'special:documents','glyph':'folder'},
    {'title':'다운로드','target':'special:downloads','glyph':'download'},
    {'title':'메모','target':'action:memo','glyph':'edit'},
    {'title':'배경 변경','target':'action:background','glyph':'image'},
    {'title':'재생 앱 연결','target':'action:music','glyph':'plus'},
    {'title':'기념일','target':'action:events','glyph':'calendar'},
    {'title':'버튼 관리','target':'action:shortcuts','glyph':'app'},
]
DEFAULT = {
    'version': 4, 'macDock':True, 'dockAutoHide':True, 'hideTaskbar':False, 'winKeySearch':False, 'wallpaperQuality':'4k', 'nightLighting':False, 'theme': 'apricot', 'backgroundMode': 'image', 'background': '',
    'imageBackground': '', 'videoBackground': '', 'wallpaperSlides': [], 'wallpaperRotation': False, 'screen': '', 'motion': True, 'fps': 30, 'photoInterval': 30,
    'wallpaperFit':'fill','mediaSource':'', 'dim': .0, 'volume': .6, 'slideshow': True,
    'widgets': WIDGETS, 'photos': [], 'playlist': [], 'memo': '',
    'tasks': [], 'selectedTask': -1, 'links': DEFAULT_LINKS, 'events': [], 'selectedTrack': 0, 'photoIndex': 0,
    'layoutRevision':4, 'layoutPreset':'left','hideDesktopIcons':True,'fontPreset':'round',
    'focusTimer':{'minutes':25,'phase':'focus','remaining':1500,'deadline':0,'finished':False,'alarmMode':'bell','alarmFile':'','alarmVolume':.65},
    'decorations':[], 'audioReactive':True, 'updatesAutoCheck':True, 'updatesAutoInstall':False,
    'widgetColor':'','accentColor':'#edb8b4','widgetOpacity':.9,
}

def validate(data):
    """Whitelist editable state and normalize untrusted imported values."""
    out = copy.deepcopy(DEFAULT)
    if not isinstance(data, dict):
        return out
    def number(name, lo, hi, cast=float):
        try:
            value=cast(data.get(name,out[name]))
            if math.isfinite(value): out[name]=max(lo,min(hi,value))
        except (ValueError, TypeError, OverflowError): pass
    for key, options in [('theme', ('apricot','ocean','night')), ('backgroundMode', ('room','image','video'))]:
        if data.get(key) in options: out[key] = 'image' if key=='backgroundMode' and data[key]=='room' else data[key]
    for key in ('background','imageBackground','videoBackground','screen','memo','mediaSource'):
        if isinstance(data.get(key),str): out[key] = data[key][:20000]
    for key in ('macDock','dockAutoHide','hideTaskbar','winKeySearch','nightLighting','motion','slideshow','wallpaperRotation','hideDesktopIcons','audioReactive','updatesAutoCheck','updatesAutoInstall'):
        if isinstance(data.get(key),bool): out[key] = data[key]
    for name,lo,hi,cast in [('fps',15,60,int),('photoInterval',5,3600,int),('volume',0,1,float),('widgetOpacity',.35,1,float),('dim',0,.85,float),('selectedTrack',0,10000,int),('photoIndex',0,10000,int)]:
        number(name,lo,hi,cast)
    if isinstance(data.get('wallpaperSlides'),list):
        for row in data['wallpaperSlides'][:200]:
            if not isinstance(row,dict) or not isinstance(row.get('path'),str) or not row['path'] or len(row['path'])>4096:continue
            try:seconds=max(1,min(86400,int(row.get('seconds',30))))
            except (ValueError,TypeError,OverflowError):seconds=30
            out['wallpaperSlides'].append({'path':row['path'],'seconds':seconds})
    for key in ('photos','playlist'):
        if isinstance(data.get(key),list): out[key] = [p for p in data[key][:500] if isinstance(p,str) and len(p)<4096]
    if isinstance(data.get('tasks'),list):
        out['tasks']=[]
        for row in data['tasks'][:100]:
            if not isinstance(row,dict):
                continue
            title=str(row.get('title') or row.get('text') or '').strip()[:120]
            detail=str(row.get('detail') or '').strip()[:12000]
            if title or detail:
                attachments=row.get('attachments',[]) if isinstance(row.get('attachments',[]),list) else []
                out['tasks'].append({'title':title or '할 일','text':title or '할 일','detail':detail,'done':bool(row.get('done',False)),'attachments':[str(a)[:4096] for a in attachments[:30] if isinstance(a,str)]})
    try:
        selected=int(data.get('selectedTask',-1))
        out['selectedTask']=selected if -1 <= selected < len(out['tasks']) else -1
    except (TypeError,ValueError,OverflowError):
        out['selectedTask']=-1
    for key, fields in [('links',('title','target','glyph','icon')),('events',('title','date','attachment'))]:
        if isinstance(data.get(key),list):
            out[key]=[]
            for row in data[key][:(64 if key=='links' else 100)]:
                if isinstance(row,dict): out[key].append({k:(str(row.get(k,''))[:4096]) for k in fields})
    timer=data.get('focusTimer',{})
    if isinstance(timer,dict):
        t=out['focusTimer']
        for key,lo,hi in [('minutes',1,180),('remaining',0,10800),('deadline',0,4102444800),('alarmVolume',0,1)]:
            try:
                value=float(timer.get(key,t[key]))
                if math.isfinite(value):t[key]=max(lo,min(hi,value))
            except (TypeError,ValueError,OverflowError):pass
        t['minutes']=int(t['minutes']);t['remaining']=int(t['remaining'])
        for key,options in [('phase',('focus','break')),('alarmMode',('bell','file'))]:
            if timer.get(key) in options:t[key]=timer[key]
        if isinstance(timer.get('alarmFile'),str):t['alarmFile']=timer['alarmFile'][:4096]
        t['finished']=bool(timer.get('finished',False))
    from room_items import normalize_item
    if isinstance(data.get('decorations'),list):
        seen=set()
        for value in data['decorations'][:80]:
            item=normalize_item(value)
            if item and item['id'] not in seen:out['decorations'].append(item);seen.add(item['id'])
    for link in out['links']:

        if link.get('target')=='action:music' and link.get('title')=='음악 추가':link['title']='재생 앱 연결'
    for key,options in [('wallpaperQuality',('native','4k')),('wallpaperFit',('fill','fit')),('fontPreset',('round','clean','soft')),('layoutPreset',('left','right','bottom'))]:
        if data.get(key) in options:out[key]=data[key]
    for key in ('widgetColor','accentColor'):
        if isinstance(data.get(key),str) and re.fullmatch(r'#[0-9a-fA-F]{6}',data[key]):out[key]=data[key]
    if data.get('accentColor')=='#86b8d6':out['accentColor']='#edb8b4'
    for key,default in WIDGETS.items():
        row=data.get('widgets',{}).get(key,{}) if isinstance(data.get('widgets'),dict) else {}
        if not isinstance(row,dict): continue
        for attr,lo,hi in [('x',0,1500),('y',0,850),('scale',.45,1.8)]:
            try:
                v=float(row.get(attr,default[attr]))
                if math.isfinite(v): out['widgets'][key][attr]=max(lo,min(hi,v))
            except (TypeError,ValueError,OverflowError): pass
        if isinstance(row.get('visible'),bool): out['widgets'][key]['visible']=row['visible']
        if isinstance(row.get('color'),str) and re.fullmatch(r'#[0-9a-fA-F]{6}',row['color']):out['widgets'][key]['color']=row['color']
    if data.get('version')==1 and data.get('layoutRevision',0)<2:
        out['widgets']=copy.deepcopy(WIDGETS)
        if out['memo']=='오늘 남겨두고 싶은 이야기를 적어보세요.':out['memo']=''
        existing={r['target'] for r in out['links']}
        out['links'] += [copy.deepcopy(r) for r in DEFAULT_LINKS if r['target'] not in existing]
        out['backgroundMode']='image'
    if data.get('version') in (1,2,3) and data.get('layoutRevision',0)<3:
        for key,row in out['widgets'].items():row.update(x=WIDGETS[key]['x'],y=WIDGETS[key]['y'],scale=WIDGETS[key]['scale'])
    if data.get('layoutRevision',0)<4:
        old_memo={'x':436,'y':296};old_calendar={'x':436,'y':532}
        memo_row=out['widgets']['memo'];calendar_row=out['widgets']['calendar']
        if memo_row['x']==old_memo['x'] and memo_row['y']==old_memo['y'] and calendar_row['x']==old_calendar['x'] and calendar_row['y']==old_calendar['y']:
            calendar_row['x']=820
    out['layoutRevision']=4
    for key,row in out['widgets'].items():
        width,height=WIDGET_SIZES[key]
        row['x']=max(0,min(row['x'],1600-width*row['scale']))
        row['y']=max(0,min(row['y'],900-height*row['scale']))
    return out

def checksum(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

class Store:
    def __init__(self, directory: Path):
        self.directory=Path(directory); self.directory.mkdir(parents=True,exist_ok=True)
        self.media=self.directory/'media'; self.media.mkdir(exist_ok=True)
        self.path=self.directory/'settings.json'
        self.data=copy.deepcopy(DEFAULT)
        self.load_warning=''
        if self.path.exists():
            try:
                raw=json.loads(self.path.read_text('utf-8'))
                if raw.get('version',0)<4 and not (self.directory/'settings.before-inline.json').exists():shutil.copy2(self.path,self.directory/'settings.before-inline.json')
                self.data=validate(raw)
            except (ValueError,OSError):
                shutil.copy2(self.path,self.directory/'settings.damaged.json')
                self.load_warning='설정 파일을 읽지 못했습니다. 원본을 백업하고 기본 설정을 적용했습니다.'
    def save(self,snapshot=None):
        fd,temp=tempfile.mkstemp(dir=self.directory,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(self.data if snapshot is None else snapshot,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    def ingest(self, source):
        p=Path(source).resolve()
        if not p.is_file(): raise ValueError('파일을 찾을 수 없습니다.')
        digest=checksum(p)[:20]
        target=self.media/(digest+p.suffix.lower())
        if target != p and not target.exists(): shutil.copy2(p,target)
        return str(target)
    def export_scene(self, destination, asset_root):
        data=copy.deepcopy(self.data); mapping={}
        # The export is self-contained, including selected local audio/media.
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
            def pack(value):
                p=Path(value)
                if not value or not p.is_file(): return ''
                if str(p) not in mapping:
                    name='media/'+checksum(p)[:20]+p.suffix.lower()
                    mapping[str(p)]=name;z.write(p,name)
                return mapping[str(p)]
            for key in ('photos','playlist'): data[key]=[pack(p) for p in data[key] if Path(p).is_file()]
            for row in data['wallpaperSlides']:row['path']=pack(row['path'])
            for key in ('background','imageBackground','videoBackground'): data[key]=pack(data[key])
            for row in data['links']:row['icon']=pack(row.get('icon',''))
            for row in data['tasks']:row['attachments']=[pack(p) for p in row.get('attachments',[]) if Path(p).is_file()]
            for row in data['events']:row['attachment']=pack(row.get('attachment',''))
            for item in data['decorations']:item['image']=pack(item['image'])
            data['focusTimer']['alarmFile']=pack(data['focusTimer']['alarmFile'])
            # Links are plain text only; import never executes anything.
            z.writestr('scene.json',json.dumps(data,ensure_ascii=False))
    def import_scene(self, source):
        with zipfile.ZipFile(source) as z:
            infos=z.infolist()
            if len(infos)>1500 or sum(i.file_size for i in infos)>2*1024**3: raise ValueError('테마 파일이 너무 큽니다. 최대 크기는 2 GB입니다.')
            if 'scene.json' not in z.namelist() or z.getinfo('scene.json').file_size>2*1024**2: raise ValueError('올바른 테마 파일이 아닙니다.')
            raw=json.loads(z.read('scene.json')); data=validate(raw)
            pending={}
            def unpack(name):
                if not name: return ''
                p=Path(name)
                if p.is_absolute() or '..' in p.parts or not name.startswith('media/') or '\\' in name: raise ValueError('테마 안의 경로가 올바르지 않습니다.')
                if name not in pending:
                    info=z.getinfo(name)
                    if info.file_size>1024**3: raise ValueError('개별 파일의 최대 크기는 1 GB입니다.')
                    blob=z.read(name); target=self.media/(hashlib.sha256(blob).hexdigest()[:20]+p.suffix.lower())
                    pending[name]=(target,blob)
                return str(pending[name][0])
            for key in ('photos','playlist'): data[key]=[unpack(p) for p in data[key]]
            for row in data['wallpaperSlides']:row['path']=unpack(row['path'])
            for key in ('background','imageBackground','videoBackground'): data[key]=unpack(data[key])
            for row in data['links']:row['icon']=unpack(row.get('icon',''))
            for row in data['tasks']:row['attachments']=[unpack(p) for p in row.get('attachments',[])]
            for row in data['events']:row['attachment']=unpack(row.get('attachment',''))
            for item in data['decorations']:item['image']=unpack(item['image'])
            data['focusTimer']['alarmFile']=unpack(data['focusTimer']['alarmFile'])
            for target,blob in pending.values():
                if not target.exists(): target.write_bytes(blob)
            self.data=data;self.save()
