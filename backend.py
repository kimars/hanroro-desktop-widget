from __future__ import annotations
import copy
import logging
import os
import subprocess
import sys
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QObject,Property,Signal,Slot,QTimer,QUrl,QStandardPaths
from PySide6.QtGui import QDesktopServices,QRegion,QColor
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QFileDialog,QMessageBox,QApplication
from state import Store,WIDGETS,WIDGET_SIZES,layout_for
from wallpaper import render_wallpaper
from app_catalog import app_shell_target
from font_config import ui_family
from weather_link import WeatherLink
from media_link import MediaLink
from telemetry_link import TelemetryLink
from desktop_features import DesktopFeatures
from settings_writer import SettingsWriter
from updater import Updater
from update_prompt import UpdatePrompt
from decoration_model import DecorationModel
from room_items import CATALOG,normalize_item

log=logging.getLogger(__name__)
class Bridge(QObject):
    weatherChanged=Signal()
    updateNoticeChanged=Signal()
    decorationsChanged=Signal();dragActivity=Signal();layoutChanged=Signal();audioChanged=Signal();featureChanged=Signal();telemetryChanged=Signal()
    stateChanged=Signal();photoChanged=Signal();musicChanged=Signal();pausedChanged=Signal()
    memoChanged=Signal();inputChanged=Signal();memoInputRequested=Signal();editChanged=Signal();toast=Signal(str);requestRestore=Signal();requestSection=Signal(int);requestShowDesktop=Signal();requestSettings=Signal();requestMemo=Signal();requestEvents=Signal();requestDesktop=Signal();requestPreview=Signal()
    def __init__(self,store,assets):
        super().__init__();self.store=store;self.assets=Path(assets);self.views=[];self.overlay=None;self.desktop=False
        self.weather_link=WeatherLink(self);self.weather_link.changed.connect(self.weatherChanged);self.weather_link.changed.connect(self.refresh_state)
        self.stateChanged.connect(self.sync_weather);QTimer.singleShot(0,self.sync_weather)
        self._state_cache=None;self._wallpaper_cache_key=None;self._wallpaper_cache_path=None;self._region_key=None;self._interactive_region=QRegion()
        self._input=False;self._edit=False;self._paused=False;self._settings=None;self.wallpaper_size=(1920,1080)
        self.updates=Updater(store.directory,Path(__file__).resolve().parent/'main.py',self);self.updates.notice.connect(self.toast)
        self.update_prompt=UpdatePrompt(self.updates,store,lambda:not self._input and not self._edit and QApplication.activeModalWidget() is None,self);self.update_prompt.changed.connect(self.updateNoticeChanged)
        self.room_model=DecorationModel(store.data['decorations'],self)
        self._photo_index=int(store.data['photoIndex']);self._pending_task_attachments=[]
        self.media=MediaLink(store.directory,Path(__file__).resolve().parent/'main.py',self);self.media.preferred=store.data.get('mediaSource','');self.media.changed.connect(self.musicChanged);self.media.notice.connect(self.toast)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(250);self.debounce.timeout.connect(self.queue_persist)
        self.writer=SettingsWriter(store,self);self.writer.failed.connect(self.toast)
        self.features_controller=DesktopFeatures(store,self.assets,self)
        self.features_controller.changed.connect(self.featureChanged);self.features_controller.persist.connect(self.debounce.start);self.features_controller.notice.connect(self.toast)
        self.telemetry_link=TelemetryLink(Path(__file__).resolve().parent/'main.py',self);self.telemetry_link.changed.connect(self.telemetryChanged);self.telemetry_link.levelsChanged.connect(self.audioChanged)
        self.stateChanged.connect(self.sync_telemetry);self.pausedChanged.connect(self.sync_telemetry);self.editChanged.connect(self.sync_telemetry);self.sync_telemetry()
        self.slides=QTimer(self);self.slides.setSingleShot(True);self.slides.timeout.connect(self.advance_wallpaper);self._wallpaper_index=0;self._slide_remaining=None;self.set_slide_timer()
        self.midnight=QTimer(self);self.midnight.setInterval(60000);self.midnight.timeout.connect(self.refresh_state);self.midnight.start()
        if not self.store.path.exists() or self.store.load_warning:
            store.data['photos']=[str(p) for p in sorted((self.assets/'photos').glob('*.jpg'))]
            store.data['background']=str(self.assets/'loop.mp4')
            self.persist()
        # Locate bundled media again if the application folder was moved.
        for key in ('background','imageBackground','videoBackground'):
            p=Path(store.data[key])
            if store.data[key] and not p.is_file() and (self.assets/p.name).is_file():store.data[key]=str(self.assets/p.name)
        store.data['photos']=[str(self.assets/'photos'/Path(p).name) if not Path(p).is_file() and (self.assets/'photos'/Path(p).name).is_file() else p for p in store.data['photos']]
    def sync_weather(self):
        d=self.store.data;self.weather_link.configure(d['widgets']['weather']['visible'],d.get('weatherCity',''))
    @Property('QVariantMap',notify=weatherChanged)
    def weather(self):return dict(self.weather_link.data)
    @Slot()
    def refreshWeather(self):self.weather_link.refresh()
    @Property('QVariantMap',notify=updateNoticeChanged)
    def updateNotice(self):return dict(self.update_prompt.data)
    @Slot()
    def dismissUpdateNotice(self):self.update_prompt.dismiss()
    @Slot()
    def previewUpdateNotice(self):self.update_prompt.preview()
    @Slot()
    def updateFromNotice(self):
        if self.update_prompt.demo:self.update_prompt.dismiss();self.requestSection.emit(9)
        else:self.update_prompt.act()
    @Property('QVariantMap',notify=featureChanged)
    def features(self):return self.features_controller.snapshot()
    @Property('QVariantMap',notify=telemetryChanged)
    def telemetry(self):return {k:v for k,v in self.telemetry_link.data.items() if k!='levels'}
    @Property('QVariantList',notify=audioChanged)
    def audioLevels(self):return self.telemetry_link.data['levels']
    def sync_telemetry(self):
        widgets=self.store.data['widgets']
        self.telemetry_link.configure(audio=widgets['player']['visible'] and self.store.data['audioReactive'] and self.store.data['motion'] and not self._paused and not self._edit,monitor=widgets['system']['visible'])
    @Slot()
    def timerToggle(self):self.features_controller.toggle()
    @Slot()
    def timerReset(self):self.features_controller.reset()
    @Slot(str)
    def timerPhase(self,phase):
        if phase in ('focus','break'):self.features_controller.set_duration(25 if phase=='focus' else 5,phase)
    @Slot()
    def manageFocus(self):self._extras_tab=0;self.requestSection.emit(7)
    @Slot()
    def stopAlarm(self):self.features_controller.stop_alarm()
    @Property(QObject,constant=True)
    def decorationModel(self):return self.room_model
    @Property('QVariantList',notify=decorationsChanged)
    def decorations(self):
        rows=copy.deepcopy(self.store.data['decorations'])
        for row in rows:
            row['imageUrl']=QUrl.fromLocalFile(row['image']).toString() if row['image'] else ''
        return rows
    @Slot()
    def manageRoom(self):self.requestSection.emit(8)
    def room_changed(self):self.room_model.sync(self.store.data['decorations']);self.invalidate_state();self.debounce.start();self.decorationsChanged.emit()
    @Slot(str)
    def addFurniture(self,kind):
        if kind not in CATALOG or kind=='photo' or len(self.store.data['decorations'])>=80:return
        count=len(self.store.data['decorations']);item=normalize_item({'kind':kind,'x':430+(count%4)*90,'y':500-(count%3)*30})
        self.store.data['decorations'].append(item);self.room_changed()
    def add_room_photos(self,paths):
        from PySide6.QtGui import QImageReader
        for path in paths:
            if len(self.store.data['decorations'])>=80:break
            reader=QImageReader(str(path));size=reader.size()
            if not size.isValid():continue
            image=self.store.ingest(path);ratio=size.width()/max(1,size.height());height=210; width=max(84,min(370,height*ratio))
            if width==370:height=370/ratio
            self.store.data['decorations'].append(normalize_item({'kind':'photo','image':image,'width':width+24,'height':height+42,'x':550,'y':350,'z':3}))
        self.room_changed()
    @Slot(str,float,float)
    def moveDecoration(self,identity,x,y):
        for row in self.store.data['decorations']:
            if row['id']==identity and not row['locked']:
                row.update(x=x,y=y);row.update(normalize_item(row));self.room_changed();return
    @Slot(str,str,float)
    def adjustDecoration(self,identity,field,value):
        if field not in ('scale','rotation','z'):return
        for row in self.store.data['decorations']:
            if row['id']==identity and not row['locked']:
                row[field]=value;row.update(normalize_item(row));self.room_changed();return
    @Slot(str,str)
    def actionDecoration(self,identity,action):
        rows=self.store.data['decorations']
        for index,row in enumerate(rows):
            if row['id']!=identity:continue
            if action=='lock':row['locked']=not row['locked']
            elif action=='animate':row['animate']=not row.get('animate',True)
            elif row['locked']:return
            elif action=='flip':row['flipped']=not row['flipped']
            elif action=='delete':rows.pop(index)
            self.room_changed();return
    def wallpaper_entries(self):
        return [row for row in self.store.data['wallpaperSlides'] if Path(row['path']).is_file()]
    def active_wallpaper(self):
        rows=self.wallpaper_entries()
        if self.store.data['wallpaperRotation'] and self.store.data['backgroundMode']=='image' and rows:
            self._wallpaper_index%=len(rows)
            return rows[self._wallpaper_index]['path']
        return self.store.data['imageBackground'] or str(self.assets/'photos/photo1.jpg')
    def set_slide_timer(self):
        self.slides.stop();self._slide_remaining=None
        rows=self.wallpaper_entries()
        if self.store.data['wallpaperRotation'] and self.store.data['backgroundMode']=='image' and len(rows)>1:
            self._wallpaper_index%=len(rows)
            duration=rows[self._wallpaper_index]['seconds']*1000
            if self._paused:self._slide_remaining=duration
            else:self.slides.start(duration)
    def advance_wallpaper(self):
        rows=self.wallpaper_entries()
        if not rows or not self.store.data['wallpaperRotation'] or self.store.data['backgroundMode']!='image':return
        self._wallpaper_index=(self._wallpaper_index+1)%len(rows)
        self.refresh_state();self.set_slide_timer()
    def wallpaper_slides_changed(self):
        self._wallpaper_index=0;self.set_slide_timer();self.changed()

    def invalidate_state(self):self._state_cache=None
    def refresh_state(self):self.invalidate_state();self.stateChanged.emit()
    @Property('QVariantMap',notify=stateChanged)
    def state(self):
        if self._state_cache is not None:
            self._state_cache['memo']=self.store.data['memo']
            return self._state_cache
        d=copy.deepcopy(self.store.data)
        d['wallpaperUrl']=QUrl.fromLocalFile(str(self.wallpaper_path())).toString()
        path=(d['videoBackground'] or str(self.assets/'loop.mp4')) if d['backgroundMode']=='video' else self.active_wallpaper();d['backgroundUrl']=QUrl.fromLocalFile(path).toString() if path and Path(path).is_file() else ''
        d['eventsView']=self.events_view();d['widgetSizes']={k:list(v) for k,v in WIDGET_SIZES.items()};d['appearance']=self.appearance()
        for row in d['links']:
            path=row.get('icon','');row['icon']=QUrl.fromLocalFile(path).toString() if path and Path(path).is_file() else ''
        d['assetUrl']=QUrl.fromLocalFile(str(self.assets)).toString()+'/'
        self._state_cache=d
        return d
    @Property(str,notify=photoChanged)
    def photo(self):return self.photo_at(0)
    @Property(str,notify=photoChanged)
    def secondPhoto(self):return self.photo_at(1)
    def photo_at(self,offset):
        photos=[p for p in self.store.data['photos'] if Path(p).is_file()]
        if not photos:return ''
        return QUrl.fromLocalFile(photos[(self._photo_index+offset)%len(photos)]).toString()
    @Property(str,notify=stateChanged)
    def uiFont(self):
        return ui_family(self.store.data['fontPreset'])
    @Property(str,notify=stateChanged)
    def clockFont(self):return self.uiFont
    @Property(bool,notify=inputChanged)
    def inputActive(self):return self._input
    @Slot(bool)
    def setInputActive(self,active):
        if self._input!=active:self._input=active;self.inputChanged.emit()
    @Property(str,notify=memoChanged)
    def memo(self):return self.store.data['memo']
    @Property(int,notify=stateChanged)
    def pendingTaskAttachmentCount(self):return len(self._pending_task_attachments)
    @Slot(str)
    def setMemo(self,text):
        text=text[:20000]
        if self.store.data['memo']!=text:
            self.store.data['memo']=text;self.debounce.start();self.memoChanged.emit()
    @Slot(str,str)
    def setWidgetColor(self,key,color):
        if key in WIDGETS and (not color or QColor(color).isValid()):
            self.store.data['widgets'][key]['color']=QColor(color).name() if color else '';self.changed()
    @Slot(str)
    def applyLayout(self,preset):
        if preset not in ('left','right','bottom'):return
        positions=layout_for(preset)
        for key,row in self.store.data['widgets'].items():
            for field in ('x','y','scale'):row[field]=positions[key][field]
        self.store.data['layoutPreset']=preset;self.changed()
    def appearance(self):
        d=self.store.data;night=d['theme']=='night';out={}
        for key,row in d['widgets'].items():
            base=row.get('color') or d['widgetColor'] or ('#24313d' if night else '#f2f7fb')
            if key=='player' and not night and not row.get('color') and not d['widgetColor']:base='#f1eee7'
            color=QColor(base);light=(color.redF()*.2126+color.greenF()*.7152+color.blueF()*.0722)>.56
            ink='#233441' if light else '#f3f7fb';muted='#657b8c' if light else '#bacbd8'
            color.setAlphaF(d['widgetOpacity'])
            out[key]={'surface':color.name(QColor.NameFormat.HexArgb),'solid':base,'ink':ink,'muted':muted,'accent':d['accentColor'],'dark':not light}
        return out
    @Property(bool,notify=editChanged)
    def editMode(self):return self._edit
    @Property(bool,notify=pausedChanged)
    def backgroundPaused(self):return self._paused
    @Property(bool,notify=musicChanged)
    def playing(self):return self.media.data['playing']
    @Property(str,notify=musicChanged)
    def trackTitle(self):return self.media.data['title'] or ('제목 정보 없음' if self.media.data['connected'] else '재생 앱 연결')
    @Property(str,notify=musicChanged)
    def trackArtist(self):return self.media.data['artist'] or self.media.data['sourceName']
    @Property(str,notify=musicChanged)
    def trackHint(self):return self.media.data['sourceName'] or '연결 안 됨'
    @Property(str,notify=musicChanged)
    def albumCover(self):return self.media.data['cover']
    @Property(bool,notify=musicChanged)
    def canPlayPause(self):return self.media.data['canPlayPause']
    @Property(bool,notify=musicChanged)
    def canNext(self):return self.media.data['canNext']
    @Property(bool,notify=musicChanged)
    def canPrevious(self):return self.media.data['canPrevious']
    @Property(bool,notify=musicChanged)
    def canSeek(self):return self.media.data['canSeek']
    @Property(float,notify=musicChanged)
    def progress(self):return max(0.,min(1.,self.media.data['position']/self.media.data['duration'])) if self.media.data['duration'] else 0.
    @Property(str,notify=musicChanged)
    def elapsed(self):return self.format_time(self.media.data['position']) if self.media.data['duration'] else '—'
    @Property(str,notify=musicChanged)
    def duration(self):return self.format_time(self.media.data['duration']) if self.media.data['duration'] else '—'
    @staticmethod
    def format_time(ms):return f'{ms//60000:02d}:{ms//1000%60:02d}'
    def changed(self):self.debounce.start();self.refresh_state();self.memoChanged.emit()
    def persist(self):
        try:self.writer.flush(copy.deepcopy(self.store.data))
        except OSError as e:log.exception('Settings save');self.toast.emit('설정 저장 실패: '+str(e))
    def queue_persist(self):
        try:self.writer.submit(copy.deepcopy(self.store.data))
        except OSError as error:self.toast.emit(str(error))
    @Slot()
    def toggleEdit(self):self._edit=not self._edit;self.editChanged.emit()
    @Slot(str,result='QVariantMap')
    def widgetLayout(self,key):return copy.deepcopy(self.store.data['widgets'].get(key,{}))
    @Slot()
    def layoutActivity(self):self.dragActivity.emit()
    @Slot(str,float,float)
    def moveWidget(self,key,x,y):
        if key in WIDGETS:
            row=self.store.data['widgets'][key];w,h=WIDGET_SIZES[key];row.update(x=round(max(0,min(x,1600-w*row['scale'])),2),y=round(max(40,min(y,900-h*row['scale'])),2));self.invalidate_state();self.debounce.start();self.layoutChanged.emit()
    @Slot(str,float)
    def scaleWidget(self,key,value):
        if key in WIDGETS:
            row=self.store.data['widgets'][key];row['scale']=max(.45,min(1.8,value))
            sizes=WIDGET_SIZES
            w,h=sizes[key];row['x']=max(0,min(row['x'],1600-w*row['scale']));row['y']=max(40,min(row['y'],900-h*row['scale']));self.invalidate_state();self.debounce.start();self.layoutChanged.emit()
    @Slot(str)
    def hideWidget(self,key):
        if key in WIDGETS:self.store.data['widgets'][key]['visible']=False;self.changed()
    @Slot()
    def settings(self):self.requestSettings.emit()
    @Slot()
    def editMemo(self):
        if not self.store.data['widgets']['memo']['visible']:
            self.store.data['widgets']['memo']['visible']=True;self.changed()
        self.memoInputRequested.emit()
    @Slot()
    def editEvents(self):self.requestEvents.emit()
    @Slot()
    def desktopMode(self):self.requestDesktop.emit()
    @Slot()
    def previewMode(self):self.requestPreview.emit()
    @Slot()
    def nextPhoto(self):
        self._photo_index+=1;self.store.data['photoIndex']=self._photo_index;self.photoChanged.emit()
    @Slot()
    def previousPhoto(self):
        self._photo_index-=1;self.store.data['photoIndex']=self._photo_index;self.photoChanged.emit()
    @Slot(int)
    def toggleTask(self,index):
        tasks=self.store.data['tasks']
        if 0<=index<len(tasks):tasks[index]['done']=not tasks[index]['done'];self.changed()
    @Slot(str,str)
    def addTask(self,title,detail):
        title=str(title).strip()[:120];detail=str(detail).strip()[:12000]
        if not title:
            self.toast.emit('할 일 제목을 입력하세요.');return
        tasks=self.store.data['tasks']
        if len(tasks)>=100:
            self.toast.emit('할 일은 최대 100개까지 저장할 수 있습니다.');return
        tasks.append({'title':title,'text':title,'detail':detail,'done':False,'attachments':list(self._pending_task_attachments)})
        self._pending_task_attachments.clear()
        self.store.data['selectedTask']=len(tasks)-1
        self.changed()
    @Slot(int)
    def selectTask(self,index):
        if index==-1 or 0<=index<len(self.store.data['tasks']):
            if self.store.data.get('selectedTask',-1)!=index:
                self.store.data['selectedTask']=index;self.refresh_state();self.debounce.start()
    @Slot()
    def deleteSelectedTask(self):
        index=int(self.store.data.get('selectedTask',-1));tasks=self.store.data['tasks']
        if 0<=index<len(tasks):
            tasks.pop(index);self.store.data['selectedTask']=-1;self.changed()
    @Slot()
    def chooseTaskAttachments(self):
        paths,_=QFileDialog.getOpenFileNames(self._settings,'할 일에 파일 첨부','','모든 파일 (*)')
        self.addTaskFiles(paths)
    @Slot()
    def clearTaskAttachments(self):
        if self._pending_task_attachments:
            self._pending_task_attachments.clear();self.refresh_state()
    @Slot('QVariantList')
    def addTaskAttachments(self,urls):
        paths=[]
        for value in urls:
            url=QUrl(str(value));path=url.toLocalFile()
            if path and Path(path).is_file():paths.append(path)
        self.addTaskFiles(paths)
    def addTaskFiles(self,paths):
        if not paths:return
        try:
            for path in paths:
                stored=self.store.ingest(path)
                if stored not in self._pending_task_attachments:self._pending_task_attachments.append(stored)
            self.refresh_state();self.toast.emit(f'첨부 파일 {len(self._pending_task_attachments)}개 준비됨')
        except (OSError,ValueError) as error:self.toast.emit(str(error))
    @Slot(int,int)
    def openTaskAttachment(self,task_index,attachment_index):
        tasks=self.store.data['tasks']
        if not 0<=task_index<len(tasks):return
        files=tasks[task_index].get('attachments',[])
        if not 0<=attachment_index<len(files):return
        path=files[attachment_index]
        try:
            if Path(path).is_file():
                if sys.platform=='win32':os.startfile(path)
                else:QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:self.toast.emit('첨부 파일을 찾을 수 없습니다.')
        except OSError as error:self.toast.emit(str(error))
    @Slot()
    def chooseMusic(self):self.requestSection.emit(3)
    def select_media_source(self,source):
        self.store.data['mediaSource']=source;self.debounce.start();self.media.select(source)
    @Slot()
    def playPause(self):self.media.command('toggle')
    @Slot()
    def nextTrack(self):self.media.command('next')
    @Slot()
    def previousTrack(self):self.media.command('previous')
    @Slot(float)
    def seek(self,fraction):self.media.command('seek',fraction=max(0.,min(1.,fraction)))
    @Slot(int,str)
    def videoError(self,code,message):
        log.error('Video background error %s: %s; file=%s',code,message,self.store.data['videoBackground'])
        self.toast.emit('영상 재생 실패: '+str(message)[:140])
    def night_active(self):
        if not self.store.data.get('nightLighting'):return False
        weather=self.weather_link.data
        return not weather['isDay'] if weather['status']=='ready' else datetime.now().hour>=19 or datetime.now().hour<7
    def wallpaper_path(self):
        d=self.store.data;source=self.active_wallpaper();dim=min(.85,1-(1-d['dim'])*(1-(.22 if self.night_active() else 0)))
        key=(source,d['theme'],dim,self.wallpaper_size,d.get('wallpaperFit','fill'))
        if key==self._wallpaper_cache_key:return self._wallpaper_cache_path
        if not Path(source).is_file():source=str(self.assets/'photos/photo1.jpg')
        path=render_wallpaper(source,self.store.directory/'wallpapers',d['theme'],dim,self.wallpaper_size,d.get('wallpaperFit','fill'))
        self._wallpaper_cache_key=key;self._wallpaper_cache_path=path
        return path
    @Slot()
    def restoreBackground(self):self.requestRestore.emit()
    @Slot()
    def manageButtons(self):self.requestSection.emit(4)
    @Slot('QVariantList')
    def addDroppedFiles(self,urls):
        for value in urls:
            url=QUrl(str(value));path=url.toLocalFile()
            if path and Path(path).exists() and len(self.store.data['links'])<64:
                self.store.data['links'].append({'title':Path(path).stem[:30],'target':path,'glyph':'folder' if Path(path).is_dir() else 'app','icon':''})
        self.changed()
    @Slot()
    def openRecycleBin(self):
        if sys.platform!='win32':self.toast.emit('휴지통은 Windows에서 지원합니다.');return
        try:os.startfile('shell:RecycleBinFolder')
        except OSError as error:self.toast.emit(str(error))
    @Slot(int)
    def launch(self,index):
        links=self.store.data['links']
        if not 0<=index<len(links):return
        target=links[index]['target'].strip()
        actions={'action:recyclebin':self.openRecycleBin,'action:settings':lambda:self.requestSection.emit(0),'action:memo':self.editMemo,'action:events':lambda:self.requestSection.emit(5),'action:background':lambda:self.requestSection.emit(1),'action:shortcuts':lambda:self.requestSection.emit(4),'action:music':self.chooseMusic,'action:edit':self.toggleEdit,'action:nextphoto':self.nextPhoto,'action:desktop':self.requestShowDesktop.emit}
        if target in actions:actions[target]();return
        if target.startswith('app:') or (sys.platform=='win32' and Path(target).suffix.lower() in ('.exe','.lnk')):
            try:
                if sys.platform=='win32':
                    from app_windows import toggle_or_launch
                    status=toggle_or_launch(target)
                    if status=='minimized':self.toast.emit('앱을 최소화했습니다.')
                    elif status=='activated':self.toast.emit('열려 있는 앱으로 이동했습니다.')
                else:self.toast.emit('앱 실행은 Windows에서 지원합니다.')
            except (OSError,ValueError) as error:self.toast.emit(str(error))
            return
        folders={'special:documents':QStandardPaths.StandardLocation.DocumentsLocation,'special:downloads':QStandardPaths.StandardLocation.DownloadLocation,'special:desktop':QStandardPaths.StandardLocation.DesktopLocation,'special:music':QStandardPaths.StandardLocation.MusicLocation}
        try:
            if target in folders:target=QStandardPaths.writableLocation(folders[target])
            if target.startswith(('https://','http://')):
                if not QDesktopServices.openUrl(QUrl(target)):raise ValueError('링크를 열지 못했습니다.')
            elif Path(target).exists():
                if sys.platform=='win32':os.startfile(target)
                else:QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            else:raise ValueError('파일이 없습니다. 버튼 관리에서 경로를 확인하세요.')
        except (OSError,ValueError) as e:self.toast.emit(str(e))
    @Slot('QVariantList')
    def hitRegions(self,regions):
        if not self.desktop or self.overlay is None:return
        key=(id(self.overlay),tuple((r.get('x'),r.get('y'),r.get('w'),r.get('h'),r.get('paintOnly',False)) for r in regions))
        if key==self._region_key:return
        self._region_key=key
        region=QRegion();interactive=QRegion()
        for row in regions:
            try:
                part=QRegion(QRect(int(row['x']),int(row['y']),max(1,int(row['w'])),max(1,int(row['h']))));region=region.united(part)
                if not row.get('paintOnly'):interactive=interactive.united(part)
            except (KeyError,TypeError,ValueError):continue
        self._interactive_region=interactive
        if not region.isEmpty():self.overlay.setMask(region)
    @Slot(str)
    def notify(self,text):self.toast.emit(text)
    def events_view(self):
        today=date.today();out=[]
        for row in self.store.data['events']:
            try:
                day=date.fromisoformat(row['date']);delta=(day-today).days
                out.append({'title':row['title'],'date':day.strftime('%m.%d'),'day':('D-DAY' if delta==0 else f'D−{delta}' if delta>0 else f'D+{-delta}'),'sort':abs(delta),'future':delta>=0})
            except (ValueError,KeyError):continue
        return sorted(out,key=lambda r:(not r['future'],r['sort']))[:3]
    def set_paused(self,paused):
        if paused==self._paused:return
        self._paused=paused
        if paused:
            if self.slides.isActive():self._slide_remaining=max(1,self.slides.remainingTime());self.slides.stop()
        elif self._slide_remaining is not None:
            remaining=self._slide_remaining;self._slide_remaining=None;self.slides.start(remaining)
        self.pausedChanged.emit()
    def set_option(self,key,value):
        if key=='memo':self.setMemo(str(value));return
        self.store.data[key]=value
        if key=='updatesAutoInstall':
            if value:self.store.data['updatesAutoCheck']=True
            self.update_prompt.configure()
        if key in ('wallpaperRotation','wallpaperSlides','backgroundMode'):self.set_slide_timer()
        self.changed()
    def set_autostart(self,enabled):
        if sys.platform!='win32':return
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                portable=Path(sys.executable).parent.parent/'한로로 바탕화면 위젯.exe'
                args=[str(portable)] if Path(sys.executable).parent.name=='_internal' and portable.is_file() else ([sys.executable,'--desktop'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).with_name('main.py')),'--desktop'])
                winreg.SetValueEx(key,'HanroroDesktop',0,winreg.REG_SZ,subprocess.list2cmdline(args))
            else:
                try:winreg.DeleteValue(key,'HanroroDesktop')
                except FileNotFoundError:pass
    @staticmethod
    def autostart_enabled():
        if sys.platform!='win32':return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:return bool(winreg.QueryValueEx(key,'HanroroDesktop')[0])
        except OSError:return False
