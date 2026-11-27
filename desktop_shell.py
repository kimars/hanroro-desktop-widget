"""Independent dock/search windows; worker searches and bounded icon/catalog caches."""
import ctypes,math,sys,time,base64,hashlib,logging
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QPoint,QRectF,QFileInfo,QEvent
from PySide6.QtGui import QPainter,QColor,QPen,QCursor,QIcon,QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QLabel,QFileIconProvider,QMenu,QAbstractItemView,QPushButton,QScrollArea,QFrame
from shell_native import ShellNative
from shell_service import ShellService
from desktop_native import matching_windows
from shell_search import rank_apps,indexed_files
from panel_ui import settings_style,icon
from windows_desktop import IS_WINDOWS

class Bus(QObject):
    catalog=Signal(object);files=Signal(int,object);error=Signal(str);running=Signal(object);launched=Signal(str);taskbar=Signal(object,str)

from shell_windows import visible_windows as visible_processes,select_window
from taskbar_catalog import collect_taskbar,dock_rows,group_windows

class SearchWindow(QDialog):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setWindowTitle('한로로 시작');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint);self.resize(760,590)
        self.setObjectName('settingsWindow');self.setAttribute(Qt.WA_TranslucentBackground);layout=QVBoxLayout(self);layout.setContentsMargins(22,20,22,18);layout.setSpacing(12)
        self.field=QLineEdit();self.field.setPlaceholderText('앱, 문서 및 파일 검색');self.field.setMinimumHeight(44);layout.addWidget(self.field)
        self.results=QListWidget();self.results.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(30,30));layout.addWidget(self.results,1)
        self.status=QLabel('앱 · Windows 검색 인덱스');self.status.setObjectName('sub');layout.addWidget(self.status)
        self.delay=QTimer(self);self.delay.setSingleShot(True);self.delay.setInterval(280);self.delay.timeout.connect(self.search_files)
        self.field.textChanged.connect(self.query_changed);self.field.returnPressed.connect(self.open_current);self.results.itemActivated.connect(lambda _:self.open_current());self.results.itemClicked.connect(lambda _:self.open_current());self.field.installEventFilter(self)
        self.results.verticalScrollBar().valueChanged.connect(lambda _:self.icon_delay.start())
        self.icon_delay=QTimer(self);self.icon_delay.setSingleShot(True);self.icon_delay.setInterval(60);self.icon_delay.timeout.connect(self.load_visible_icons)
        self.rows=[];self.token=0;self.future=None;self.cache={};self._dialog_open=False
        self.escape=QShortcut(QKeySequence('Escape'),self);self.escape.activated.connect(self.hide)
    def changeEvent(self,event):
        if event.type()==QEvent.WindowActivate:self._ever_active=True
        elif event.type()==QEvent.WindowDeactivate and getattr(self,'_ever_active',False):QTimer.singleShot(0,lambda:self.hide() if not self.isActiveWindow() else None)
        super().changeEvent(event)
    def nativeEvent(self,eventType,message):
        if sys.platform=='win32':
            from ctypes import wintypes
            m=wintypes.MSG.from_address(int(message))
            if m.message==0x8000+441:QTimer.singleShot(0,self.owner.toggle_search);return True,0
            if m.message==0x8000+442:self.owner.schedule_scan();return True,0
            if m.message==0x8000+443:self.owner.bar_changed(int(m.wParam),int(m.lParam));return True,0
        return super().nativeEvent(eventType,message)
    def eventFilter(self,obj,event):
        if obj is self.field and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Down,Qt.Key_Up):
            self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+(1 if event.key()==Qt.Key_Down else -1))));return True
        return super().eventFilter(obj,event)
    def query_changed(self):
        self.token+=1
        if self.future:self.future.cancel()
        links=[dict(r,name=r['title'],index=i) for i,r in enumerate(self.owner.b.store.data['links'])];empty=not self.field.text().strip();self.rows=[dict(r,kind='app') for r in rank_apps(self.owner.apps if empty else links+self.owner.apps,self.field.text(),5000 if empty else 40)];self.draw_results()
        self.delay.start()
    def search_files(self):
        text=self.field.text().strip();token=self.token
        if len(text)<2 or not self.isVisible():return
        key=text.casefold()
        if key in self.cache:self.receive_files(token,self.cache[key]);return
        self.owner.service.search(token,text,self.owner.roots)
    def receive_files(self,token,rows):
        if token!=self.token or not self.isVisible():return
        if len(self.cache)>40:self.cache.clear()
        self.cache[self.field.text().strip().casefold()]=rows
        self.rows=[r for r in self.rows if r.get('kind')!='file']+rows;self.draw_results()
    def draw_results(self):
        self.results.clear();empty=not self.field.text().strip()
        self.results.setViewMode(QListWidget.IconMode if empty else QListWidget.ListMode);self.results.setResizeMode(QListWidget.Adjust);self.results.setMovement(QListWidget.Static);self.results.setSpacing(8 if empty else 2);self.results.setWordWrap(True)
        from PySide6.QtCore import QSize
        self.results.setGridSize(QSize(108,96) if empty else QSize());self.results.setIconSize(QSize(42,42) if empty else QSize(30,30))
        for row in self.rows:
            item=QListWidgetItem(icon('app'),row['name']);item.setData(Qt.UserRole,row);item.setToolTip(row.get('path') or row['target']);self.results.addItem(item)
        if self.results.count():self.results.setCurrentRow(0)
        self.icon_delay.start()
        self.status.setText('앱 목록 불러오는 중' if self.owner.loading else (str(len(self.rows))+'개 결과' if self.field.text() else '앱 · 파일 검색'))
    def load_visible_icons(self):
        if self.owner.closed:return
        # Only visible rows resolve native icons; never extract hundreds at once.
        viewport=self.results.viewport().rect();visible=set()
        for y in range(12,viewport.height(),24):
            for x in range(18,viewport.width(),54):
                index=self.results.indexAt(QPoint(x,y))
                if index.isValid():visible.add(index.row())
        for i in sorted(visible):
            item=self.results.item(i)
            if item:item.setIcon(self.owner.item_icon(item.data(Qt.UserRole)))
    def open_current(self):
        item=self.results.currentItem()
        if item:self.hide();self.owner.open_item(item.data(Qt.UserRole))
    def hideEvent(self,event):self.token+=1;self.delay.stop();self.icon_delay.stop();self.owner.service.cancel_search();super().hideEvent(event)
    def show_search(self):
        self.setStyleSheet(settings_style(self.owner.b.store.data['theme']=='night')+'QDialog#settingsWindow {border:1px solid #becbd4;border-radius:24px;}');screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();g=screen.availableGeometry();self.resize(min(760,g.width()-32),min(590,g.height()-48));self.move(g.center().x()-self.width()//2,g.y()+max(28,(g.height()-self.height())//4));self.show();self.raise_();self.activateWindow();self.owner.native.focus(int(self.winId()));self.field.setFocus();self.field.clear();self.query_changed()

class MacDock(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setWindowTitle('한로로 독');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus);self.setAttribute(Qt.WA_ShowWithoutActivating);self.setAttribute(Qt.WA_TranslucentBackground);self.setMouseTracking(True);self.hover=-1;self.rows=[];self.all_rows=[];self.page=0;self.hit=[];self.last_hover=time.monotonic();self.closed=False
        self.timer=QTimer(self);self.timer.setInterval(180);self.timer.timeout.connect(self.check_edge)
        self.hover_delay=QTimer(self);self.hover_delay.setSingleShot(True);self.hover_delay.setInterval(350);self.hover_delay.timeout.connect(lambda:self.owner.hover_item(self.rows[self.hover]) if 0<=self.hover<len(self.rows) else None);self.revealed=False
    def refresh(self):
        self.all_rows=[{'name':'시작 · 검색','target':'shell:search','glyph':'search'}]+dock_rows(self.owner.taskbar_rows,self.owner.running_rows)+[{'name':'설정','target':'action:settings','glyph':'settings'}]
        self.reposition();self.update()
    def wheelEvent(self,event):
        if self.pages>1:self.page=max(0,min(self.pages-1,self.page+(-1 if event.angleDelta().y()>0 else 1)));self.reposition();self.update()
    def nativeEvent(self,eventType,message):
        if sys.platform=='win32':
            from ctypes import wintypes
            m=wintypes.MSG.from_address(int(message))
            if m.message==0x21:return True,3
            if m.message==0x46 and not self.owner.program.host.allow_zorder:
                class POS(ctypes.Structure):_fields_=[('hwnd',wintypes.HWND),('after',wintypes.HWND),('x',ctypes.c_int),('y',ctypes.c_int),('cx',ctypes.c_int),('cy',ctypes.c_int),('flags',wintypes.UINT)]
                POS.from_address(m.lParam).flags|=4
        return super().nativeEvent(eventType,message)
    def reposition(self):
        screen=self.owner.program.pick_screen() if hasattr(self.owner.program,'pick_screen') else QApplication.primaryScreen();g=screen.geometry()
        if not self.owner.b.store.data.get('hideTaskbar',True):g=screen.availableGeometry()
        capacity=max(5,int((g.width()-60)//54));self.pages=max(1,math.ceil(len(self.all_rows)/max(1,capacity-2)));self.page=min(self.page,self.pages-1)
        if self.pages>1:self.rows=[{'name':'이전 앱','target':'shell:prev','glyph':'chevron-left'}]+self.all_rows[self.page*(capacity-2):(self.page+1)*(capacity-2)]+[{'name':'다음 앱','target':'shell:next','glyph':'chevron-right'}]
        else:self.rows=list(self.all_rows)
        self.slot=min(64,max(40,(g.width()-80)/max(1,len(self.rows))));size=(round(self.slot*len(self.rows)+28),96)
        bottom=self.owner.bar_rect.bottom()+1 if self.owner.bar_rect else g.bottom()+1
        point=(g.center().x()-size[0]//2,bottom-size[1])
        if (self.width(),self.height())!=size:self.resize(*size)
        if (self.x(),self.y())!=point:self.move(*point)
        for row in self.rows:
            matches=matching_windows(row,self.owner.running_rows)
            if matches:
                window=matches[0];row['hwnd']=window['hwnd']
                if not row.get('path'):row['path']=window.get('path','')
            self.owner.item_icon(row)
    def reveal(self,value):
        if self.revealed==value:return
        self.revealed=value;host=getattr(self.owner.program,'host',None)
        if host and hasattr(host,'set_auxiliary_revealed'):host.set_auxiliary_revealed(int(self.winId()),value)
    def after_action(self):
        self.hover_delay.stop();self.owner.name_tip.hide()
        if self.owner.b.store.data.get('dockAutoHide',False):self.hide();self.reveal(False)
    def hover_target(self):return self.rows[self.hover]['target'] if 0<=self.hover<len(self.rows) else ''
    def check_edge(self):
        if not self.owner.active or self.owner.fullscreen or (IS_WINDOWS and not self.owner.taskbar_loaded):return
        if self.owner.chooser.isVisible():self.last_hover=time.monotonic();return
        always=not self.owner.b.store.data.get('dockAutoHide',False)
        if always:
            # A reserved AppBar strip keeps maximized applications out of the dock.
            if not IS_WINDOWS or self.owner.bar_active:self.show();self.reveal(True)
            return
        p=QCursor.pos();inside=self.isVisible() and self.geometry().adjusted(-8,-12,8,8).contains(p);screen=QApplication.screenAt(p);g=screen.geometry() if screen else None;edge=g and 0<=g.bottom()-p.y()<5 and abs(p.x()-g.center().x())<self.width()/2
        if inside or edge:
            if not self.isVisible():self.owner.schedule_scan()
            self.last_hover=time.monotonic();self.show();self.reveal(True)
        elif time.monotonic()-self.last_hover>.8:self.hide();self.reveal(False);self.owner.name_tip.hide()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform);dark=self.owner.b.store.data['theme']=='night';surface=QColor('#e52b3943' if dark else '#e6fff8f0');p.setPen(QPen(QColor('#65ffffff'),1));p.setBrush(surface);p.drawRoundedRect(QRectF(1,20,self.width()-2,74),23,23);self.hit=[]
        xmouse=self.mapFromGlobal(QCursor.pos()).x() if self.underMouse() else -1000
        for i,row in enumerate(self.rows):
            x=14+self.slot*(i+.5);magnify=1+.28*math.exp(-((xmouse-x)/55)**2) if self.owner.b.store.data['motion'] else 1;size=min(46,self.slot-8)*magnify;r=QRectF(x-size/2,77-size,size,size);self.hit.append(QRectF(x-self.slot/2,12,self.slot,78));p.setPen(Qt.NoPen);p.setBrush(QColor('#516578' if dark else '#e9edf5'));p.drawRoundedRect(r,14,14);self.owner._icons.get(self.owner.icon_key(row),QIcon()).paint(p,r.adjusted(8,8,-8,-8).toRect())
            if row.get('target','').casefold() in self.owner.running_targets:p.setBrush(QColor('#f0acc0' if dark else '#4c6877'));p.drawEllipse(QPoint(round(x),86),2,2)
        p.end()
    def mouseMoveEvent(self,event):
        point=event.position();index=next((i for i,r in enumerate(self.hit) if r.contains(point)),-1)
        if index!=self.hover:
            self.hover=index;self.owner.chooser.hide();self.owner.name_tip.hide();self.hover_delay.stop()
            if index>=0:self.owner.show_name(self.rows[index]);self.hover_delay.start()
        self.setCursor(Qt.PointingHandCursor if index>=0 else Qt.ArrowCursor);self.update()
    def leaveEvent(self,event):
        self.hover_delay.stop();self.hover=-1;self.owner.name_tip.hide();self.update()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            index=next((i for i,r in enumerate(self.hit) if r.contains(event.position())),-1)
            if index>=0:
                target=self.rows[index]['target']
                if target in ('shell:prev','shell:next'):self.page=max(0,min(self.pages-1,self.page+(-1 if target=='shell:prev' else 1)));self.reposition();self.update()
                else:self.owner.choose_item(self.rows[index])
    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)

class WindowChooser(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.entries=[];self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus);self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName('windowChooser');self.setStyleSheet('QWidget#windowChooser {background:#263747;border:1px solid #647785;border-radius:16px;} QLabel {color:#fff7ef;padding:5px;} QPushButton {text-align:left;background:#354958;color:#fff7ef;border:0;border-radius:9px;padding:12px;} QPushButton:hover {background:#506879;} QScrollArea {border:0;background:transparent;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(12,10,12,12);self.title=QLabel();self.title.setTextFormat(Qt.PlainText);layout.addWidget(self.title);self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);layout.addWidget(self.scroll)
        self.expiry=QTimer(self);self.expiry.setInterval(220);self.expiry.timeout.connect(self.check_leave);self.last_inside=time.monotonic()
    def nativeEvent(self,eventType,message):
        if sys.platform=='win32':
            from ctypes import wintypes
            if wintypes.MSG.from_address(int(message)).message==0x21:return True,3
        return super().nativeEvent(eventType,message)
    def show_windows(self,row,windows):
        self.entries=list(windows);self.title.setText(str(row.get('name','')));body=QWidget();layout=QVBoxLayout(body);layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        for window in self.entries:
            button=QPushButton(str(window.get('name','이름 없는 창')).replace('&','&&'));button.setToolTip(str(window.get('name','')));button.setIcon(self.owner.item_icon(row));button.setFocusPolicy(Qt.NoFocus);button.clicked.connect(lambda checked=False,w=dict(window):self.owner.activate_window(w));layout.addWidget(button)
        old=self.scroll.takeWidget()
        if old:old.deleteLater()
        self.scroll.setWidget(body);self.resize(370,min(380,66+len(windows)*54));g=self.owner.program.pick_screen().geometry();x=QCursor.pos().x()-self.width()//2;self.move(max(g.left()+6,min(x,g.right()-self.width()-6)),self.owner.dock.y()-self.height()-6);self.owner.name_tip.hide();self.last_inside=time.monotonic();self.show();self.raise_();self.expiry.start()
    def check_leave(self):
        point=QCursor.pos()
        if self.geometry().adjusted(-12,-12,12,18).contains(point) or self.owner.dock.geometry().contains(point):self.last_inside=time.monotonic()
        elif time.monotonic()-self.last_inside>.65:self.hide()
    def hideEvent(self,event):self.expiry.stop();super().hideEvent(event)

class DesktopShell(QObject):
    def __init__(self,program):
        super().__init__(program.app);self.program=program;self.b=program.bridge;self.active=False;self.closed=False;self.started=False;self.loading=False;self.apps=[];self.taskbar_rows=[];self.running_rows=[];self.running_targets=set();self.taskbar_loaded=False;self.scanning=False;self._scan_pending=False;self.last_scan=0;self.pending_pick=None;self.pick_token=0;self.launching=set();self._icons={};self.icon_handles={};self.icon_pending=set();self.icon_failed=set();self.bar_active=False;self.bar_hwnd=0;self.bar_rect=None;self.fullscreen=False
        self.native=ShellNative(self.b.store.directory,self);self.service=ShellService(Path(__file__).resolve().parent/'main.py',self);self.service.result.connect(self.worker_result);self.service.error.connect(self.worker_error);self.service.inventory.connect(self.inventory_result)
        self.search=SearchWindow(self);self.service.files.connect(self.search.receive_files);self.dock=MacDock(self);self.chooser=WindowChooser(self);self.name_tip=QLabel();self.name_tip.setWindowFlags(Qt.ToolTip|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus);self.name_tip.setAttribute(Qt.WA_TransparentForMouseEvents);self.name_tip.setTextFormat(Qt.PlainText);self.name_tip.setStyleSheet('background:#263747;color:#fff7ef;border-radius:9px;padding:7px 12px;')
        from PySide6.QtCore import QStandardPaths
        self.roots=[QStandardPaths.writableLocation(x) for x in (QStandardPaths.DesktopLocation,QStandardPaths.DocumentsLocation,QStandardPaths.DownloadLocation)]
        self.monitor=QTimer(self);self.monitor.setInterval(5000);self.monitor.timeout.connect(self.periodic_scan);self.b.stateChanged.connect(self.configure);self.configure()
    def configure(self):
        if self.closed:return
        was=self.active;self.active=bool(self.b.desktop and self.b.store.data.get('macDock',True))
        if not self.active:
            self.dock.timer.stop();self.monitor.stop();self.dock.hide();self.search.hide();self.chooser.hide();self.name_tip.hide();self.native.close();self.bar_active=False;self.bar_rect=None
            if hasattr(self.program,'reserve_shell_space'):self.program.reserve_shell_space(False)
            return
        self.dock.refresh();self.dock.timer.start();self.monitor.start()
        if IS_WINDOWS:self.program.host.attach_auxiliary(int(self.dock.winId()))
        if not self.started:self.load_apps()
        ready=self.taskbar_loaded
        d=self.b.store.data
        self.native.configure(int(self.search.winId()),d.get('hideTaskbar',True) and ready,d.get('winKeySearch',True),int(self.dock.winId()) if ready else 0,d.get('dockAutoHide',False))
        if self.native.failed:self.b.toast.emit(self.native.failed)
        self.dock.check_edge()
    def load_apps(self):
        if self.loading or self.closed:return
        self.loading=True;self.started=True;self.service.load_inventory()
    def inventory_result(self,data):
        if self.closed:return
        if data.get('phase')=='catalog':self.catalog_ready(data.get('rows',[]));return
        self.loading=False;self.taskbar_ready(data.get('rows',[]),data.get('error',''))
    def catalog_ready(self,rows):
        if self.closed:return
        self.apps=rows
        from app_windows import register_app_shortcuts
        register_app_shortcuts(rows);self.search.query_changed()
    def taskbar_ready(self,rows,error=''):
        if self.closed:return
        if rows:
            self.taskbar_rows=rows;self.taskbar_loaded=True;self.dock.refresh();self.configure();self.schedule_scan()
        elif IS_WINDOWS:
            logging.getLogger(__name__).warning('Taskbar inventory failed: %s',error);self.b.toast.emit('Windows 작업 표시줄을 읽지 못해 원래 표시줄을 유지합니다.')
    def bar_changed(self,hwnd,state):
        if self.closed or not self.active:return
        if state==0:
            if self.bar_hwnd and self.bar_hwnd!=hwnd:return
            self.bar_active=False;self.bar_hwnd=0;self.bar_rect=None;self.dock.reveal(False)
        elif state==2:self.fullscreen=True;self.dock.reveal(False);self.dock.hide();self.chooser.hide();self.name_tip.hide();return
        else:
            self.fullscreen=False;self.bar_hwnd=hwnd;self.bar_rect=self.native.bar_rect(hwnd,self.program.pick_screen());self.bar_active=self.bar_rect is not None
        self.dock.reposition();self.workarea_changed();self.dock.check_edge()
    def workarea_changed(self):
        if self.closed or not self.active:return
        self.dock.reposition()
        if hasattr(self.program,'reserve_shell_space'):self.program.reserve_shell_space(self.bar_active,self.dock.y())
    def toggle_search(self):
        if self.search.isVisible():self.search.hide()
        else:
            if not self.started:self.load_apps()
            self.chooser.hide();self.name_tip.hide();self.search.show_search()
    def icon_key(self,row):
        return str(row.get('icon') or row.get('target') or row.get('path') or row.get('name'))
    def badge(self,row):
        from PySide6.QtGui import QPixmap,QFont
        name=str(row.get('name') or '?');pix=QPixmap(64,64);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);palette=['#8daac3','#bc929f','#91ada2','#b2a0bd','#c4a278'];color=palette[int(hashlib.sha256(name.encode()).hexdigest()[:4],16)%len(palette)];p.setBrush(QColor(color));p.setPen(Qt.NoPen);p.drawRoundedRect(QRectF(0,0,64,64),15,15);p.setPen(QColor('white'));font=QFont(QApplication.font());font.setPointSize(18);font.setBold(True);p.setFont(font);p.drawText(pix.rect(),Qt.AlignCenter,name[:2].upper());p.end();return QIcon(pix)
    def item_icon(self,row):
        key=self.icon_key(row)
        hwnd=row.get('hwnd')
        if hwnd and key in self.icon_failed and self.icon_handles.get(key)!=hwnd:
            self.icon_handles[key]=hwnd;self.icon_failed.discard(key);self._icons.pop(key,None)
        if key in self._icons:return self._icons[key]
        if row.get('glyph') and str(row.get('target','')).startswith(('shell:','action:','special:','http')):
            self._icons[key]=icon(row['glyph'],self.b.store.data['theme']=='night');return self._icons[key]
        if row.get('icon') and Path(row['icon']).is_file():self._icons[key]=QIcon(row['icon']);return self._icons[key]
        value=self.badge(row)
        self._icons[key]=value
        if key not in self.icon_failed and self.service.enabled:
            self.icon_pending.add(key);self.service.icon(dict(row,key=key))
        return value
    def worker_result(self,action,request,data):
        if self.closed:return
        if action=='icons':
            from PySide6.QtGui import QImage,QPixmap
            for row in data:
                key=row['key'];self.icon_pending.discard(key)
                try:
                    raw=base64.b64decode(row.get('png',''),validate=True)
                    if not raw or len(raw)>256*1024:raise ValueError()
                    image=QImage.fromData(raw)
                    if image.isNull() or image.width()>512 or image.height()>512:raise ValueError()
                    self._icons[key]=QIcon(QPixmap.fromImage(image))
                except (ValueError,TypeError):self.icon_failed.add(key)
            self.dock.update();self.search.icon_delay.start();return
        if action=='windows':self.running_ready(data);return
        if action=='launch':self.launching.clear();self.schedule_scan()
    def worker_error(self,action,request,error):
        if self.closed:return
        logging.getLogger(__name__).warning('Shell worker %s failed: %s',action,error)
        if action=='windows':
            self.scanning=False;self.pending_pick=None;self.b.toast.emit('창 목록을 가져오지 못했습니다. 다시 눌러 주세요.')
        elif action=='launch':self.launching.clear();self.b.toast.emit('앱을 열지 못했습니다. '+error)
    def schedule_scan(self):
        if self._scan_pending or self.closed or not self.active:return
        self._scan_pending=True;QTimer.singleShot(160,self.scan_running)
    def periodic_scan(self):
        if self.native.process and self.native.process.poll() is not None:
            code=self.native.process.returncode;self.native.close();self.bar_active=False;self.bar_rect=None;self.dock.reveal(False);self.b.toast.emit('작업 표시줄 연결이 종료됐습니다. 원래 Windows 표시줄을 복원합니다.');logging.getLogger(__name__).warning('Native shell exit %s',code)
        if self.dock.isVisible() or self.search.isVisible():self.schedule_scan()
    def scan_running(self):
        self._scan_pending=False
        if self.closed:return
        if self.scanning:self._rescan=True;return
        self.scanning=True;self.last_scan=time.monotonic();self.service.request('windows')
        if not self.service.enabled:self.scanning=False
    def running_ready(self,data):
        if self.closed:return
        self.scanning=False;self.running_rows=data.get('rows',[]);self.running_targets=set()
        for row in self.taskbar_rows:
            if matching_windows(row,self.running_rows):self.running_targets.add(row['target'].casefold())
        self.running_targets.update(str(r['target']).casefold() for r in self.running_rows);self.dock.refresh()
        pending=self.pending_pick;self.pending_pick=None
        if pending:
            row,mode,token=pending
            if token==self.pick_token and (mode=='click' or self.dock.hover_target()==row['target']):self.present_windows(row,mode)
        if getattr(self,'_rescan',False):self._rescan=False;self.schedule_scan()
    def choose_item(self,row):
        target=row['target']
        if target.startswith(('shell:','action:')):self.open_item(row);return
        self.dock.hover_delay.stop();self.pick_token+=1;self.pending_pick=(dict(row),'click',self.pick_token)
        if self.service.enabled:self.schedule_scan()
        else:self.present_windows(row,'click')
    def hover_item(self,row):
        if self.closed or (self.pending_pick and self.pending_pick[1]=='click'):return
        self.show_name(row)
        windows=matching_windows(row,self.running_rows)
        if len(windows)>1:self.chooser.show_windows(row,windows)
        elif self.service.enabled:
            self.pick_token+=1;self.pending_pick=(dict(row),'hover',self.pick_token);self.schedule_scan()
    def present_windows(self,row,mode):
        windows=matching_windows(row,self.running_rows)
        if len(windows)>1:self.chooser.show_windows(row,windows)
        elif mode=='click':
            if windows:self.activate_window(windows[0])
            else:self.open_item(row)
    def activate_window(self,row):
        self.chooser.hide();self.name_tip.hide();self.dock.after_action()
        if not select_window(row):self.b.toast.emit('이미 닫힌 창입니다.');self.schedule_scan()
    def show_name(self,row):
        self.name_tip.setText(str(row.get('name','')));self.name_tip.adjustSize();point=QCursor.pos();g=self.program.pick_screen().geometry();self.name_tip.move(max(g.left()+4,min(point.x()-self.name_tip.width()//2,g.right()-self.name_tip.width()-4)),self.dock.y()-self.name_tip.height()-8);self.name_tip.show()
    def open_item(self,row):
        target=row.get('target','')
        if target=='shell:search':self.toggle_search();return
        if target=='action:settings':self.b.settings();return
        if target.startswith('app:') or (IS_WINDOWS and Path(target).suffix.lower() in ('.exe','.lnk')):
            if target in self.launching:return
            self.launching.add(target);self.service.request('launch',row=dict(row));self.dock.after_action();return
        if 'index' in row:self.b.launch(row['index']);return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if Path(target).exists():QDesktopServices.openUrl(QUrl.fromLocalFile(target))
    def close(self):
        if self.closed:return
        self.closed=True;self.monitor.stop();self.dock.hover_delay.stop();self.search.icon_delay.stop();self.search.delay.stop();self.dock.reveal(False);self.service.close();self.native.close();self.dock.close();self.search.close();self.chooser.close();self.name_tip.close()
