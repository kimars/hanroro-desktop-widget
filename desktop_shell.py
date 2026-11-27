"""Independent dock/search windows; worker searches and bounded icon/catalog caches."""
import ctypes,math,sys,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QPoint,QRectF,QFileInfo,QEvent
from PySide6.QtGui import QPainter,QColor,QPen,QCursor,QIcon,QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QLabel,QFileIconProvider
from shell_native import ShellNative
from shell_search import rank_apps,indexed_files
from panel_ui import settings_style,icon
from windows_desktop import IS_WINDOWS

class Bus(QObject):
    catalog=Signal(object);files=Signal(int,object);error=Signal(str);running=Signal(object);launched=Signal(str)

def visible_processes():
    if sys.platform!='win32':return {'paths':set(),'rows':[]}
    from ctypes import wintypes
    from app_windows import _process_path,_window_app_id,_window_property_id
    u=ctypes.WinDLL('user32');k=ctypes.WinDLL('kernel32');u.IsWindowVisible.argtypes=[wintypes.HWND];k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE];k.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)];u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    k.GetApplicationUserModelId.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.UINT),wintypes.LPWSTR]
    paths=set();seen=set();rows=[];callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback
    def visit(hwnd,_):
        if not u.IsWindowVisible(hwnd):return True
        pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value in seen or pid.value==__import__('os').getpid():return True
        seen.add(pid.value);p=k.OpenProcess(0x1000,False,pid.value)
        if p:
            try:
                value=_process_path(k,p)
                if value:paths.add(value.casefold())
                app_id=_window_app_id(k,p) or _window_property_id(hwnd)
                if app_id:paths.add('app:'+app_id.casefold())
                text=ctypes.create_unicode_buffer(256);u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];u.GetWindowTextW(hwnd,text,256)
                if value and text.value:rows.append({'name':text.value[:80],'target':'app:'+app_id if app_id else value,'path':value,'kind':'running'})
            finally:k.CloseHandle(p)
        return True
    u.EnumWindows.argtypes=[callback,wintypes.LPARAM];u.EnumWindows(visit,0);return {'paths':paths,'rows':rows}

class SearchWindow(QDialog):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setWindowTitle('한로로 검색');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint);self.resize(640,450)
        self.setObjectName('settingsWindow');self.setAttribute(Qt.WA_TranslucentBackground);layout=QVBoxLayout(self);layout.setContentsMargins(22,20,22,18);layout.setSpacing(12)
        self.field=QLineEdit();self.field.setPlaceholderText('앱 또는 파일 검색');self.field.setMinimumHeight(44);layout.addWidget(self.field)
        self.results=QListWidget();self.results.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(30,30));layout.addWidget(self.results,1)
        self.status=QLabel('앱 · Windows 검색 인덱스');self.status.setObjectName('sub');layout.addWidget(self.status)
        self.delay=QTimer(self);self.delay.setSingleShot(True);self.delay.setInterval(280);self.delay.timeout.connect(self.search_files)
        self.field.textChanged.connect(self.query_changed);self.field.returnPressed.connect(self.open_current);self.results.itemActivated.connect(lambda _:self.open_current());self.results.itemClicked.connect(lambda _:self.open_current());self.field.installEventFilter(self)
        self.rows=[];self.token=0;self.future=None;self.cache={};self._dialog_open=False
        self.escape=QShortcut(QKeySequence('Escape'),self);self.escape.activated.connect(self.hide)
    def nativeEvent(self,eventType,message):
        if sys.platform=='win32':
            from ctypes import wintypes
            m=wintypes.MSG.from_address(int(message))
            if m.message==0x8000+441:QTimer.singleShot(0,self.owner.toggle_search);return True,0
        return super().nativeEvent(eventType,message)
    def eventFilter(self,obj,event):
        if obj is self.field and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Down,Qt.Key_Up):
            self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+(1 if event.key()==Qt.Key_Down else -1))));return True
        return super().eventFilter(obj,event)
    def query_changed(self):
        self.token+=1
        if self.future:self.future.cancel()
        links=[dict(r,name=r['title'],index=i) for i,r in enumerate(self.owner.b.store.data['links'])];self.rows=[dict(r,kind='app') for r in rank_apps(links+self.owner.apps,self.field.text())];self.draw_results()
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
        self.results.clear()
        for row in self.rows:
            item=QListWidgetItem(self.owner.item_icon(row),row['name']);item.setData(Qt.UserRole,row);item.setToolTip(row.get('path') or row['target']);self.results.addItem(item)
        if self.results.count():self.results.setCurrentRow(0)
        self.status.setText('앱 목록 불러오는 중' if self.owner.loading else (str(len(self.rows))+'개 결과' if self.field.text() else '앱 · 파일 검색'))
    def open_current(self):
        item=self.results.currentItem()
        if item:self.hide();self.owner.open_item(item.data(Qt.UserRole))
    def hideEvent(self,event):self.token+=1;self.delay.stop();super().hideEvent(event)
    def show_search(self):
        self.setStyleSheet(settings_style(self.owner.b.store.data['theme']=='night')+'QDialog#settingsWindow {border:1px solid #becbd4;border-radius:24px;}');screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();g=screen.availableGeometry();self.resize(min(640,g.width()-32),min(450,g.height()-48));self.move(g.center().x()-self.width()//2,g.y()+max(28,(g.height()-self.height())//4));self.show();self.raise_();self.activateWindow();self.field.setFocus();self.field.selectAll();self.query_changed()

class MacDock(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setWindowTitle('한로로 독');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus);self.setAttribute(Qt.WA_ShowWithoutActivating);self.setAttribute(Qt.WA_TranslucentBackground);self.setMouseTracking(True);self.hover=-1;self.rows=[];self.hit=[];self.last_hover=time.monotonic();self.closed=False
        self.timer=QTimer(self);self.timer.setInterval(180);self.timer.timeout.connect(self.check_edge)
    def refresh(self):
        self.rows=[{'name':'검색','target':'shell:search','glyph':'search'}]+[dict(r,name=r['title'],index=i) for i,r in enumerate(self.owner.b.store.data['links'][:12])];pinned={r['target'].casefold() for r in self.rows};self.rows += [r for r in self.owner.running_rows if r['target'].casefold() not in pinned][:6];self.rows += [{'name':'설정','target':'action:settings','glyph':'settings'}]
        self.reposition();self.update()
    def reposition(self):
        screen=self.owner.program.pick_screen() if hasattr(self.owner.program,'pick_screen') else QApplication.primaryScreen();g=screen.geometry() if self.owner.b.store.data.get('hideTaskbar',False) else screen.availableGeometry();self.slot=min(64,max(38,(g.width()-80)/max(1,len(self.rows))));self.resize(round(self.slot*len(self.rows)+28),96);self.move(g.center().x()-self.width()//2,g.bottom()-self.height()-7)
    def check_edge(self):
        if not self.owner.active:return
        p=QCursor.pos();inside=self.geometry().adjusted(-8,-12,8,8).contains(p);screen=QApplication.screenAt(p);g=screen.geometry() if screen else None;edge=g and g.bottom()-p.y()<5 and abs(p.x()-g.center().x())<self.width()/2
        if inside or edge:self.last_hover=time.monotonic();self.setVisible(True)
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
            if index>=0:self.owner.open_item(self.rows[index])
    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)

class DesktopShell(QObject):
    def __init__(self,program):
        super().__init__(program.app);self.program=program;self.b=program.bridge;self.active=False;self.apps=[];self.loading=False;self.started=False;self.closed=False;self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='shell');self.launch_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='app-open');self.launching=set();self.bus=Bus(self);self.bus.catalog.connect(self.catalog_ready);self.bus.error.connect(self.b.toast);self.bus.launched.connect(self.launching.discard);self.bus.running.connect(self.running_ready);self.native=ShellNative(self.b.store.directory);self.running_targets=set();self.running_rows=[];self._icons={};self.provider=QFileIconProvider();self.search=SearchWindow(self);self.bus.files.connect(self.search.receive_files);self.dock=MacDock(self)
        from PySide6.QtCore import QStandardPaths
        self.roots=[QStandardPaths.writableLocation(x) for x in (QStandardPaths.DesktopLocation,QStandardPaths.DocumentsLocation,QStandardPaths.DownloadLocation)]
        self.monitor=QTimer(self);self.monitor.setInterval(3500);self.monitor.timeout.connect(self.scan_running);self.scanning=False
        self.b.stateChanged.connect(self.configure);self.alt=QShortcut(QKeySequence('Alt+Space'),self.search);self.alt.activated.connect(self.toggle_search)
        self.configure()
    def configure(self):
        if self.closed:return
        was_active=self.active;self.active=self.b.desktop and self.b.store.data.get('macDock',True)
        if not self.active:
            self.dock.timer.stop();self.dock.hide();self.search.hide();self.monitor.stop();self.native.close();return
        self.dock.refresh();
        if not was_active or not self.b.store.data.get('dockAutoHide',True):self.dock.show()
        self.dock.timer.start();self.monitor.start()
        if not self.started:self.load_apps()
        d=self.b.store.data
        if not self.native.configure(int(self.search.winId()),d.get('hideTaskbar',False),d.get('winKeySearch',False)):self.b.toast.emit('Windows 연결을 시작하지 못했습니다. 기본 작업 표시줄은 유지됩니다.')
    def load_apps(self):
        if self.loading or self.closed:return
        self.loading=True;self.started=True;bus=self.bus
        def work():
            from app_catalog import collect_apps
            rows=collect_apps()
            try:bus.catalog.emit(rows)
            except RuntimeError:pass
        self.pool.submit(work)
    def catalog_ready(self,rows):self.apps=rows;self.loading=False;self._icons.clear();self.dock.update();self.search.query_changed()
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
    def scan_running(self):
        if self.native.process and self.native.process.poll() is not None:
            self.native.close();self.b.store.data['hideTaskbar']=False;self.b.store.data['winKeySearch']=False;self.b.toast.emit('Windows 연결이 종료되어 기본 작업 표시줄로 복원했습니다.');self.b.changed()
        if self.scanning or not self.active or self.closed:return
        self.scanning=True;bus=self.bus
        def work():
            try:paths=visible_processes();bus.running.emit(paths)
            except (RuntimeError,OSError):
                try:bus.running.emit({'paths':set(),'rows':[]})
                except RuntimeError:pass
        self.pool.submit(work)
    def running_ready(self,data):
        self.scanning=False;paths=data['paths'];self.running_rows=data['rows']
        # Catalog IDs map to shortcut files; match classic app basenames without resolving shortcuts on the UI thread.
        names={Path(p).stem.casefold() for p in paths};self.running_targets={r['target'].casefold() for r in self.b.store.data['links'] if r['target'].casefold() in paths or (Path(r['target']).suffix.lower() in ('.lnk','.exe') and Path(r['target']).stem.casefold() in names)}|paths;self.dock.refresh()
    def close(self):
        if self.closed:return
        self.closed=True;self.monitor.stop();self.native.close();self.dock.close();self.search.close();self.pool.shutdown(wait=False,cancel_futures=True);self.launch_pool.shutdown(wait=False,cancel_futures=True)
