"""Independent dock/search windows; worker searches and bounded icon/catalog caches."""
import ctypes,math,sys,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QPoint,QRectF,QFileInfo,QEvent
from PySide6.QtGui import QPainter,QColor,QPen,QCursor,QIcon,QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QLabel,QFileIconProvider,QMenu,QAbstractItemView
from shell_native import ShellNative
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
        bus=self.owner.bus;roots=self.owner.roots
        def work():
            rows=indexed_files(text,roots)
            try:bus.files.emit(token,rows)
            except RuntimeError:pass
        self.future=self.owner.pool.submit(work)
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
    def hideEvent(self,event):self.token+=1;self.delay.stop();super().hideEvent(event)
    def show_search(self):
        self.setStyleSheet(settings_style(self.owner.b.store.data['theme']=='night')+'QDialog#settingsWindow {border:1px solid #becbd4;border-radius:24px;}');screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();g=screen.availableGeometry();self.resize(min(760,g.width()-32),min(590,g.height()-48));self.move(g.center().x()-self.width()//2,g.y()+max(28,(g.height()-self.height())//4));self.show();self.raise_();self.activateWindow();self.owner.native.focus(int(self.winId()));self.field.setFocus();self.field.clear();self.query_changed()

class MacDock(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setWindowTitle('한로로 독');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus);self.setAttribute(Qt.WA_ShowWithoutActivating);self.setAttribute(Qt.WA_TranslucentBackground);self.setMouseTracking(True);self.hover=-1;self.rows=[];self.all_rows=[];self.page=0;self.hit=[];self.last_hover=time.monotonic();self.closed=False
        self.timer=QTimer(self);self.timer.setInterval(180);self.timer.timeout.connect(self.check_edge)
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
        screen=self.owner.program.pick_screen() if hasattr(self.owner.program,'pick_screen') else QApplication.primaryScreen();g=screen.geometry() if self.owner.b.store.data.get('hideTaskbar',True) and self.owner.taskbar_loaded else screen.availableGeometry()
        capacity=max(5,int((g.width()-60)//54));self.pages=max(1,math.ceil(len(self.all_rows)/max(1,capacity-2)));self.page=min(self.page,self.pages-1)
        if self.pages>1:self.rows=[{'name':'이전 앱','target':'shell:prev','glyph':'chevron-left'}]+self.all_rows[self.page*(capacity-2):(self.page+1)*(capacity-2)]+[{'name':'다음 앱','target':'shell:next','glyph':'chevron-right'}]
        else:self.rows=list(self.all_rows)
        self.slot=min(64,max(40,(g.width()-80)/max(1,len(self.rows))));size=(round(self.slot*len(self.rows)+28),96);point=(g.center().x()-size[0]//2,g.bottom()-size[1]-7)
        if (self.width(),self.height())!=size:self.resize(*size)
        if (self.x(),self.y())!=point:self.move(*point)
    def check_edge(self):
        if not self.owner.active or (IS_WINDOWS and not self.owner.taskbar_loaded):return
        menu=getattr(self.owner,'window_menu',None)
        if menu and menu.isVisible():self.last_hover=time.monotonic();return
        p=QCursor.pos();inside=self.geometry().adjusted(-8,-12,8,8).contains(p);screen=QApplication.screenAt(p);g=screen.geometry() if screen else None;edge=g and g.bottom()-p.y()<5 and abs(p.x()-g.center().x())<self.width()/2
        if inside or edge:
            if not self.isVisible():self.owner.schedule_scan()
            self.last_hover=time.monotonic();self.setVisible(True)
        elif self.owner.b.store.data.get('dockAutoHide',True) and time.monotonic()-self.last_hover>.8:self.hide()
        elif not self.owner.b.store.data.get('dockAutoHide',True):self.show()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform);dark=self.owner.b.store.data['theme']=='night';surface=QColor('#e52b3943' if dark else '#e6fff8f0');p.setPen(QPen(QColor('#65ffffff'),1));p.setBrush(surface);p.drawRoundedRect(QRectF(1,20,self.width()-2,74),23,23);self.hit=[]
        xmouse=self.mapFromGlobal(QCursor.pos()).x() if self.underMouse() else -1000
        for i,row in enumerate(self.rows):
            x=14+self.slot*(i+.5);magnify=1+.28*math.exp(-((xmouse-x)/55)**2) if self.owner.b.store.data['motion'] else 1;size=min(46,self.slot-8)*magnify;r=QRectF(x-size/2,77-size,size,size);self.hit.append(QRectF(x-self.slot/2,12,self.slot,78));p.setPen(Qt.NoPen);p.setBrush(QColor('#516578' if dark else '#e9edf5'));p.drawRoundedRect(r,14,14);self.owner.item_icon(row).paint(p,r.adjusted(8,8,-8,-8).toRect())
            if row.get('target','').casefold() in self.owner.running_targets:p.setBrush(QColor('#f0acc0' if dark else '#4c6877'));p.drawEllipse(QPoint(round(x),86),2,2)
    def mouseMoveEvent(self,event):
        point=event.position();self.hover=next((i for i,r in enumerate(self.hit) if r.contains(point)),-1);self.setCursor(Qt.PointingHandCursor);self.setToolTip(self.rows[self.hover]['name'] if self.hover>=0 else '');self.update()
    def leaveEvent(self,event):self.hover=-1;self.update()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            index=next((i for i,r in enumerate(self.hit) if r.contains(event.position())),-1)
            if index>=0:
                target=self.rows[index]['target']
                if target in ('shell:prev','shell:next'):self.page=max(0,min(self.pages-1,self.page+(-1 if target=='shell:prev' else 1)));self.reposition();self.update()
                else:self.owner.choose_item(self.rows[index])
    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)

class DesktopShell(QObject):
    def __init__(self,program):
        super().__init__(program.app);self.program=program;self.b=program.bridge;self.active=False;self.apps=[];self.loading=False;self.started=False;self.closed=False;self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='shell');self.launch_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='app-open');self.launching=set();self.bus=Bus(self);self.bus.catalog.connect(self.catalog_ready);self.bus.error.connect(self.b.toast);self.bus.launched.connect(self.launching.discard);self.bus.running.connect(self.running_ready);self.bus.taskbar.connect(self.taskbar_ready);self.native=ShellNative(self.b.store.directory);self.running_targets=set();self.running_rows=[];self.taskbar_rows=[];self.taskbar_loading=False;self.taskbar_loaded=False;self.last_scan=0;self._scan_pending=False;self._icons={};self.provider=QFileIconProvider();self.search=SearchWindow(self);self.bus.files.connect(self.search.receive_files);self.dock=MacDock(self)
        from PySide6.QtCore import QStandardPaths
        self.roots=[QStandardPaths.writableLocation(x) for x in (QStandardPaths.DesktopLocation,QStandardPaths.DocumentsLocation,QStandardPaths.DownloadLocation)]
        self.monitor=QTimer(self);self.monitor.setInterval(10000);self.monitor.timeout.connect(self.periodic_scan);self.scanning=False
        self.b.stateChanged.connect(self.configure);self.alt=QShortcut(QKeySequence('Alt+Space'),self.search);self.alt.activated.connect(self.toggle_search)
        self.configure()
    def configure(self):
        if self.closed:return
        was_active=self.active;self.active=self.b.desktop and self.b.store.data.get('macDock',True)
        if not self.active:
            self.dock.timer.stop();self.dock.hide();self.search.hide();self.monitor.stop();self.native.close();
            if hasattr(self.program,'reserve_shell_space'):self.program.reserve_shell_space(False)
            return
        self.dock.refresh();
        if IS_WINDOWS:self.program.host.attach_auxiliary(int(self.dock.winId()));
        if IS_WINDOWS and not self.taskbar_loaded:self.dock.hide()
        elif not was_active or not self.b.store.data.get('dockAutoHide',True):self.dock.show()
        if hasattr(self.program,'reserve_shell_space'):self.program.reserve_shell_space(self.taskbar_loaded,self.dock.y())
        self.dock.timer.start();self.monitor.start()
        if not self.started:self.load_apps()
        d=self.b.store.data
        if not self.native.configure(int(self.search.winId()),d.get('hideTaskbar',True) and self.taskbar_loaded,d.get('winKeySearch',True)):self.b.toast.emit('Windows 연결을 시작하지 못했습니다. 기본 작업 표시줄은 유지됩니다.')
    def load_apps(self):
        if self.loading or self.closed:return
        self.loading=True;self.started=True;bus=self.bus
        def work():
            from app_catalog import collect_apps
            rows=collect_apps()
            try:bus.catalog.emit(rows)
            except RuntimeError:pass
        self.pool.submit(work)
    def catalog_ready(self,rows):self.apps=rows;self.loading=False;self._icons.clear();self.load_taskbar();self.dock.refresh();self.search.query_changed()
    def load_taskbar(self):
        if self.taskbar_loading or self.closed:return
        self.taskbar_loading=True;catalog=list(self.apps);bus=self.bus
        def work():
            try:rows=collect_taskbar(catalog);error=''
            except Exception as e:rows=[];error=str(e)
            try:bus.taskbar.emit(rows,error)
            except RuntimeError:pass
        self.pool.submit(work)
    def taskbar_ready(self,rows,error):
        self.taskbar_loading=False
        if self.closed:return
        if rows:self.taskbar_rows=rows;self.taskbar_loaded=True;self.dock.refresh();self.configure();self.schedule_scan()
        elif IS_WINDOWS:self.b.toast.emit('작업 표시줄 순서를 읽지 못해 기존 작업 표시줄을 유지합니다.');__import__('logging').getLogger(__name__).warning('Taskbar snapshot failed: %s',error)
    def schedule_scan(self):
        if self._scan_pending or self.closed or not self.active:return
        self._scan_pending=True;QTimer.singleShot(250,self.scan_running)
    def choose_item(self,row):
        matches=[r for r in self.running_rows if r['target'].casefold()==row['target'].casefold() or (row.get('path') and r.get('path','').casefold()==row['path'].casefold())]
        if len(matches)>1:
            menu=QMenu(self.dock);menu.setStyleSheet(settings_style(self.b.store.data['theme']=='night'))
            for window in matches:
                action=menu.addAction(self.item_icon(row),window['name'].replace('&','&&'));action.triggered.connect(lambda checked=False,w=window:select_window(w))
            menu.popup(QCursor.pos());self.window_menu=menu
        elif len(matches)==1:select_window(matches[0])
        else:self.open_item(row)
    def item_icon(self,row):
        key=row.get('icon') or row.get('path') or row.get('target','');glyph=row.get('glyph','app');key=(key,glyph,self.b.store.data['theme'])
        if key not in self._icons:
            path=row.get('icon') or row.get('path') or row.get('target','')
            if path.startswith('app:'):path=next((r.get('path','') for r in self.apps if r['target']==path),path)
            value=QIcon(path) if row.get('icon') and Path(path).is_file() else self.provider.icon(QFileInfo(path)) if Path(path).is_file() else icon(glyph,self.b.store.data['theme']=='night')
            if len(self._icons)>256:self._icons.clear()
            self._icons[key]=value
        return self._icons[key]
    def toggle_search(self):
        if self.search.isVisible():self.search.hide()
        else:
            if not self.started:self.load_apps()
            self.search.show_search()
    def open_item(self,row):
        target=row.get('target','')
        if target=='shell:search':self.toggle_search();return
        if target.startswith('app:') or (IS_WINDOWS and Path(target).suffix.lower() in ('.exe','.lnk')):
            if target in self.launching:return
            self.launching.add(target);bus=self.bus
            def work():
                try:
                    from app_windows import toggle_or_launch
                    toggle_or_launch(target)
                except (OSError,ValueError) as e:
                    try:bus.error.emit(str(e))
                    except RuntimeError:pass
                finally:
                    try:bus.launched.emit(target)
                    except RuntimeError:pass
            self.launch_pool.submit(work);return
        if 'index' in row:self.b.launch(row['index']);return
        if target=='action:settings':self.b.settings();return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if Path(target).exists():QDesktopServices.openUrl(QUrl.fromLocalFile(target))
    def periodic_scan(self):
        if self.dock.isVisible() or self.search.isVisible():self.schedule_scan()
    def scan_running(self):
        self._scan_pending=False
        if self.native.process and self.native.process.poll() is not None:
            self.native.close();self.b.store.data['hideTaskbar']=False;self.b.store.data['winKeySearch']=False;self.b.toast.emit('Windows 연결이 종료되어 기본 작업 표시줄로 복원했습니다.');self.b.changed()
        if not self.active or self.closed:return
        if self.scanning:self._rescan=True;return
        if time.monotonic()-self.last_scan<1:
            self._scan_pending=True;QTimer.singleShot(max(30,round((1-(time.monotonic()-self.last_scan))*1000)),self.scan_running);return
        self.last_scan=time.monotonic();self.scanning=True;bus=self.bus
        def work():
            try:paths=visible_processes();bus.running.emit(paths)
            except (RuntimeError,OSError):
                try:bus.running.emit({'paths':set(),'rows':[]})
                except RuntimeError:pass
        self.pool.submit(work)
    def running_ready(self,data):
        self.scanning=False;paths=data['paths'];self.running_rows=data['rows']
        if getattr(self,'_rescan',False):self._rescan=False;self.schedule_scan()
        # Catalog IDs map to shortcut files; match classic app basenames without resolving shortcuts on the UI thread.
        names={Path(p).stem.casefold() for p in paths};self.running_targets={r['target'].casefold() for r in self.b.store.data['links'] if r['target'].casefold() in paths or (Path(r['target']).suffix.lower() in ('.lnk','.exe') and Path(r['target']).stem.casefold() in names)}|paths;self.dock.refresh()
    def close(self):
        if self.closed:return
        self.closed=True;self.monitor.stop();self.native.close();self.dock.close();self.search.close();self.pool.shutdown(wait=False,cancel_futures=True);self.launch_pool.shutdown(wait=False,cancel_futures=True)
