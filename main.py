from __future__ import annotations
import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

# Run native work before loading Qt Quick or creating a GUI in the helper process.
if __name__=='__main__' and '--update-worker' in sys.argv:
    from update_worker import run
    sys.exit(run())

if __name__=='__main__' and '--install-update' in sys.argv:
    from updater import install_update
    sys.exit(install_update(sys.argv[sys.argv.index('--install-update')+1]))

if __name__=='__main__' and '--native-job' in sys.argv:
    from native_job import run
    sys.exit(run(sys.argv[sys.argv.index('--native-job')+1]))

if __name__=='__main__' and '--telemetry-worker' in sys.argv:
    from telemetry_worker import run
    sys.exit(run())

if __name__=='__main__' and '--media-worker' in sys.argv:
    from media_worker import run
    sys.exit(run())

from font_config import configure_windows_fonts,register_fonts,ui_family
configure_windows_fonts()

# Qt uses Direct3D 11 on Windows. Set HANRORO_SOFTWARE=1 for a driver fallback.
if os.environ.get('HANRORO_SOFTWARE')=='1':os.environ['QT_QUICK_BACKEND']='software'
from PySide6.QtCore import Qt,QTimer,QUrl,QStandardPaths,QMetaObject,QObject
from PySide6.QtGui import QIcon,QFont,QFontDatabase,QColor,QSurfaceFormat,QAction,QRegion
from PySide6.QtWidgets import QApplication,QSystemTrayIcon,QMenu,QMessageBox
from PySide6.QtQuick import QQuickView
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from state import Store
from backend import Bridge
from panels import Settings
from native_jobs import NativeJobs
from desktop_events import DesktopEventFilter
from windows_desktop import DesktopHost,IS_WINDOWS,NativeWallpaper,DesktopIcons

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

class Preview(QQuickView):
    keep_in_tray=False
    def closeEvent(self,event):
        if self.keep_in_tray:event.ignore();self.hide()
        else:QApplication.instance().quit();event.accept()

class Program:
    def __init__(self,app,args):
        self.app=app;self.args=args;self.host=DesktopHost();self.errors=[];self.preview=None;self.background=None;self.overlay=None;self.tray=None;self.settings_panel=None
        data_dir=Path(args.data_dir) if args.data_dir else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.store=Store(data_dir);self.bridge=Bridge(self.store,ROOT/'assets');self.icons=DesktopIcons(self.host,data_dir)
        if IS_WINDOWS and self.bridge.autostart_enabled():
            try:self.bridge.set_autostart(True)
            except OSError:logging.exception('Automatic startup path migration failed')
        self.server=None;self._shutting_down=False;self._applying=False
        self.desktop_events=DesktopEventFilter(lambda:self.host,lambda:(self.bridge.overlay,self.bridge._interactive_region) if self.bridge.desktop else None);app.installNativeEventFilter(self.desktop_events)
        self.wallpaper_jobs=NativeJobs(data_dir,ROOT/'main.py',app);self.wallpaper_jobs.completed.connect(self.native_finished)
        self._wallpaper_inflight_signature=None
        self._wallpaper_signature=None;self._wallpaper_failed_signature=None;self.native_wallpaper_updates=0
        self.wallpaper_timer=QTimer();self.wallpaper_timer.setSingleShot(True);self.wallpaper_timer.setInterval(400);self.wallpaper_timer.timeout.connect(self.refresh_wallpaper)
        self.bridge.stateChanged.connect(lambda:self.wallpaper_timer.start() if self.bridge.desktop else None)
        self.screen=self.pick_screen()
        self.bridge.requestRestore.connect(self.restore_background);self.bridge.requestSection.connect(self.settings);self.bridge.requestShowDesktop.connect(self.show_desktop);self.bridge.requestSettings.connect(lambda:self.settings(0));self.bridge.requestMemo.connect(lambda:self.settings(5));self.bridge.requestEvents.connect(lambda:self.settings(5))
        self.app.setFont(QFont(self.bridge.uiFont,10));self.bridge.stateChanged.connect(self.update_font);self.bridge.stateChanged.connect(self.sync_icons)
        self.bridge.inputChanged.connect(self.input_changed);app.focusWindowChanged.connect(self.focus_changed)
        self.bridge.requestDesktop.connect(self.desktop);self.bridge.requestPreview.connect(self.show_preview)
        app.aboutToQuit.connect(self.shutdown)
        from app_windows import warm_app_shortcuts
        warm_app_shortcuts()
        self.make_tray()
        self.preview=self.make_view('preview',Preview);self.preview.setTitle('한로로 바탕화면 위젯 · 미리보기');self.preview.resize(1440,810);self.preview.keep_in_tray=bool(self.tray)
        if args.render or args.smoke_run or args.preview or not IS_WINDOWS:self.show_preview()
        else:QTimer.singleShot(0,self.desktop)
        self.watch=QTimer();self.watch.setInterval(750);self.watch.timeout.connect(self.tick);self.watch.start()
        self.icon_watch=QTimer();self.icon_watch.setInterval(5000);self.icon_watch.timeout.connect(lambda:self.sync_icons() if self.bridge.desktop else None);self.icon_watch.start()
        self.app.screenAdded.connect(self.screens_changed);self.app.screenRemoved.connect(self.screens_changed)
        for monitor in self.app.screens():monitor.geometryChanged.connect(self.screens_changed);monitor.availableGeometryChanged.connect(self.screens_changed)
        self.bridge.updates.available.connect(self.update_available)
        if IS_WINDOWS and not args.render and not args.smoke_run:
            QTimer.singleShot(5000,self.auto_check_updates)
            self.update_timer=QTimer(self.app);self.update_timer.setInterval(6*60*60*1000);self.update_timer.timeout.connect(self.auto_check_updates);self.update_timer.start()
        if args.render:QTimer.singleShot(2300,self.render)
        if args.smoke_run:
            self.bridge.previewUpdateNotice()
            QTimer.singleShot(2500,self.finish_smoke)
        if self.store.load_warning:QTimer.singleShot(1200,lambda:self.bridge.toast.emit(self.store.load_warning))
    def finish_smoke(self):
        notice=self.preview.rootObject().findChild(QObject,'updateAnnouncement')
        if notice is None or not notice.property('characterReady'):
            self.errors.append('Update character did not load in the packaged application')
        print('Packaged update character ready:',not bool(self.errors),flush=True)
        self.app.exit(1 if self.errors else 0)
    def auto_check_updates(self):
        if self.store.data.get('updatesAutoCheck',True) or self.store.data.get('updatesAutoInstall',False):self.bridge.updates.check()
    def update_available(self,version):
        self.bridge.toast.emit('새 버전 '+version+' · 설정에서 업데이트할 수 있어요.')
        if self.tray:self.tray.showMessage('한로로 위젯 업데이트','새 버전 '+version+'이 있습니다. 설정 → 업데이트에서 설치하세요.')
    def update_font(self):
        if self.app.font().family()!=self.bridge.uiFont:self.app.setFont(QFont(self.bridge.uiFont,10))
    def make_view(self,role,cls=QQuickView):
        v=cls();v.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        fmt=v.format();fmt.setAlphaBufferSize(8);v.setFormat(fmt)
        v.setColor(QColor('transparent') if role=='overlay' else QColor('#e6e7e5'))
        if role=='overlay':v.setFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint)
        elif role=='background':v.setFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        c=v.rootContext();c.setContextProperty('bridge',self.bridge);c.setContextProperty('uiFont',self.font('ui'));c.setContextProperty('handFont',self.font('hand'));c.setContextProperty('serifFont',self.font('serif'))
        v.setInitialProperties({'layerRole':role})
        v.engine().warnings.connect(self.qml_warnings)
        v.setSource(QUrl.fromLocalFile(str(ROOT/'qml/Scene.qml')))
        if v.status()==QQuickView.Status.Error:
            self.errors += [e.toString() for e in v.errors()];logging.error('QML failed: %s',self.errors)
        self.bridge.views.append(v);return v
    def qml_warnings(self,errors):
        for error in errors:
            msg=error.toString();logging.warning(msg)
            if 'ReferenceError' in msg or 'TypeError' in msg or 'is not' in msg:self.errors.append(msg)
    def font(self,kind):
        return ui_family('soft' if kind=='hand' else 'round') if kind!='serif' else 'Georgia'
    def pick_screen(self):return next((s for s in self.app.screens() if s.name()==self.store.data['screen']),self.app.primaryScreen())
    def make_tray(self):
        if self.args.render or self.args.smoke_run or not QSystemTrayIcon.isSystemTrayAvailable():return
        self.tray=QSystemTrayIcon(QIcon(str(ROOT/'assets/icon.ico')),self.app);self.tray.setToolTip('한로로 바탕화면 위젯')
        self.tray_menu=QMenu();menu=self.tray_menu;menu.addAction('설정',lambda:self.settings(0));menu.addAction('업데이트 확인',lambda:(self.settings(9),self.bridge.updates.check()));menu.addAction('배치 편집',self.bridge.toggleEdit);menu.addAction('바탕화면에 적용',self.desktop);menu.addAction('미리보기',self.show_preview);menu.addSeparator();menu.addAction('애니메이션 일시 정지',self.toggle_pause);menu.addAction('종료',self.app.quit)
        self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.settings(0) if reason in (QSystemTrayIcon.ActivationReason.Trigger,QSystemTrayIcon.ActivationReason.DoubleClick) else None);self.tray.show()
    def toggle_pause(self):self.manual_pause=not getattr(self,'manual_pause',False);self.bridge.set_paused(self.manual_pause)
    def settings(self,section):
        if not self.bridge._settings:
            self.settings_panel=Settings(self.bridge,self.app)
        else:self.settings_panel=self.bridge._settings
        self.settings_panel.show_section(section)
    def show_preview(self):
        if self.bridge.desktop:self.leave_desktop()
        if self.preview:self.preview.show();self.preview.raise_();self.preview.requestActivate()
    def leave_desktop(self):
        self.bridge.setInputActive(False);self.bridge.desktop=False;self.wallpaper_jobs.cancel();self._wallpaper_inflight_signature=None;self.icons.restore();self.host.detach()
        for v in (self.background,self.overlay):
            if v:v.hide();v.close();v.deleteLater();self.bridge.views.remove(v)
        self.background=None;self.overlay=None;self.bridge.overlay=None
    def restore_background(self):
        if not IS_WINDOWS:return
        if self.wallpaper_jobs.busy:
            self.bridge.toast.emit('배경을 적용하는 중입니다. 잠시 후 다시 눌러주세요.');return
        self.wallpaper_jobs.start({'operation':'restore','directory':str(self.store.directory)})
    def native_finished(self,request,ok,detail):
        if self._shutting_down:return
        if request['operation']=='restore':
            if ok:
                if self.background:self.background.hide()
                self.manual_pause=True;self.bridge.set_paused(True);self.bridge.toast.emit('이전 배경 복원됨')
            else:self.report_native_error(detail)
            return
        signature=tuple(request['signature']);self._wallpaper_inflight_signature=None
        if not self.bridge.desktop:return
        if detail=='cancelled':self.wallpaper_timer.start();return
        if ok:
            self._wallpaper_signature=signature;self.native_wallpaper_updates+=1
            logging.info('Native wallpaper applied: %s',request['path'])
        else:self._wallpaper_failed_signature=signature;self.report_native_error(detail)
        self.wallpaper_timer.start()
    def report_native_error(self,detail):
        logging.error('Native wallpaper failed: %s',detail)
        self.bridge.toast.emit('배경 적용 실패. 프로그램 폴더의 app.log를 확인하세요.')
        if self.tray:self.tray.showMessage('한로로','배경 적용 실패. 위젯은 계속 사용할 수 있습니다. app.log를 확인하세요.')
    def show_desktop(self):
        if IS_WINDOWS:self.host.show_desktop()
    def refresh_wallpaper(self):
        if not IS_WINDOWS or not self.bridge.desktop:return
        if getattr(self,'_desktop_background_mode',None)!=self.store.data['backgroundMode']:
            self.desktop();return
        try:
            path=self.bridge.wallpaper_path()
            signature=(str(path),self.screen.name())
            if signature in (self._wallpaper_signature,self._wallpaper_failed_signature,self._wallpaper_inflight_signature):return
            if self.wallpaper_jobs.busy:return
            request={'operation':'apply','path':str(path),'screen':self.screen.name(),'directory':str(self.store.directory),'signature':list(signature)}
            if self.wallpaper_jobs.start(request):self._wallpaper_inflight_signature=signature
        except Exception as error:
            self._wallpaper_failed_signature=locals().get('signature');logging.exception('Native wallpaper failed');self.bridge.toast.emit('배경 적용 실패. 진단 로그를 확인하세요.')
    def desktop(self):
        if self._shutting_down or self._applying:return
        self._applying=True
        logging.info('Desktop start: entering widget setup')
        try:self._desktop()
        except Exception:
            logging.exception('Desktop setup failed')
            self.leave_desktop()
            if self.tray:self.tray.showMessage('한로로','바탕화면 연결 실패. app.log를 확인하세요.')
        finally:self._applying=False
    def _desktop(self):
        if not IS_WINDOWS:
            if not self.args.render and not self.args.smoke_run:QMessageBox.information(None,'Windows 전용','바탕화면 적용은 Windows에서 지원합니다.')
            self.show_preview();return
        if self.bridge.desktop:self.leave_desktop()
        self.screen=self.pick_screen();dpr=self.screen.devicePixelRatio();g=self.screen.geometry()
        self.bridge.wallpaper_size=(max(640,round(g.width()*dpr)),max(360,round(g.height()*dpr)))
        self._wallpaper_signature=None;self._wallpaper_failed_signature=None
        logging.info('Desktop stage: loading overlay QML')
        self.overlay=self.make_view('overlay');self.bridge.overlay=self.overlay
        logging.info('Desktop stage: creating native widget window')
        self.overlay.setScreen(self.screen);self.overlay.setGeometry(self.screen.availableGeometry());self.overlay.setMask(QRegion(0,0,1,1));self.overlay.show()
        logging.info('Desktop stage: attaching widget window')
        if not self.host.attach_widgets(int(self.overlay.winId())):
            self.leave_desktop();logging.error('Desktop shell not found; preview was not opened')
            if self.tray:self.tray.showMessage('한로로','바탕화면 연결 실패. 트레이에서 다시 적용하세요.')
            return
        self.bridge.desktop=True;self._desktop_background_mode=self.store.data['backgroundMode'];self.preview.hide();self.refresh_wallpaper()
        if self.store.data['backgroundMode']=='video':
            self.background=self.make_view('background');self.background.setScreen(self.screen);self.background.setGeometry(g);self.background.show()
            if not self.host.attach(int(self.background.winId()),int(self.overlay.winId()),self.screen):
                self.background.hide();self.background.close();self.background.deleteLater();self.bridge.views.remove(self.background);self.background=None
                self.host.attach_widgets(int(self.overlay.winId()));self.bridge.toast.emit('영상 배경 연결 실패. 사진 배경을 유지합니다.')
        QMetaObject.invokeMethod(self.overlay.rootObject(),'updateRegions');self.host.sync_overlay();self.sync_icons()
        logging.info('Desktop ready; wallpaper job runs independently')
    def input_changed(self):
        if self.bridge.desktop and self.overlay:
            self.host.set_input_active(self.bridge.inputActive)
            if self.bridge.inputActive:self.overlay.requestActivate()
        if not self.bridge.inputActive:self.app.inputMethod().hide()
    def focus_changed(self,window):
        if not self.bridge.inputActive:return
        if window is None or window in (self.overlay,self.preview):return
        # File pickers and the custom date dialog are transient application-modal
        # windows. Keep inline desktop editing alive while one of them is open.
        if self.app.activeModalWidget() is not None:return
        self.bridge.setInputActive(False)
    def sync_icons(self):
        if self.bridge.desktop and self.store.data['hideDesktopIcons']:self.icons.hide()
        else:self.icons.restore()
    def screens_changed(self,*_):
        if self.bridge.desktop and not self._applying:QTimer.singleShot(500,self.desktop)
    def tick(self):
        if self.bridge.desktop:
            if not self.host.alive():
                self.bridge.toast.emit('바탕화면 재연결');self.desktop();return
            self.host.sync_overlay()
            self.bridge.set_paused(getattr(self,'manual_pause',False) or self.host.fullscreen_app(self.screen))
        else:self.bridge.set_paused(getattr(self,'manual_pause',False))
    def render(self):
        self.preview.grabWindow().save(self.args.render);print('Rendered:',self.args.render,'QML errors:',self.errors,flush=True);self.app.exit(1 if self.errors else 0)
    def shutdown(self):
        if self._shutting_down:return
        self._shutting_down=True;logging.info('Shutdown started')
        self.wallpaper_jobs.cancel()
        self.watch.stop();self.icon_watch.stop();self.wallpaper_timer.stop();self.bridge.slides.stop();self.bridge.midnight.stop();self.bridge.debounce.stop();self.app.inputMethod().commit();self.bridge.setInputActive(False);self.bridge.persist();self.bridge.writer.close();self.bridge.update_prompt.close();self.bridge.updates.close();self.bridge.media.close();self.bridge.telemetry_link.close();self.bridge.features_controller.close();self.icons.restore();self.host.detach()
        for view in self.bridge.views:
            view.hide();view.setSource(QUrl())
        if self.tray:self.tray.hide()
        if self.server:self.server.close()
        self.app.removeNativeEventFilter(self.desktop_events)
        logging.info('Shutdown finished')


def main():
    parser=argparse.ArgumentParser(description='한로로 바탕화면 위젯 · Windows 바탕화면 테마 위젯')
    parser.add_argument('--desktop',action='store_true');parser.add_argument('--preview',action='store_true');parser.add_argument('--render');parser.add_argument('--smoke-run',action='store_true');parser.add_argument('--data-dir');args=parser.parse_args()
    app=QApplication(sys.argv);app.setOrganizationName('Mars');app.setApplicationName('HanroroDesktop');app.setApplicationDisplayName('한로로 바탕화면 위젯');app.setWindowIcon(QIcon(str(ROOT/'assets/icon.ico')));app.setQuitOnLastWindowClosed(False)
    data_dir=Path(args.data_dir) if args.data_dir else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation));data_dir.mkdir(parents=True,exist_ok=True)
    handlers=[logging.FileHandler(data_dir/'app.log',encoding='utf-8')]
    try:handlers.append(logging.FileHandler(Path(sys.executable).parent/'app.log' if getattr(sys,'frozen',False) else ROOT/'app.log',encoding='utf-8'))
    except OSError:pass
    logging.basicConfig(handlers=handlers,level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',force=True)
    logging.info('Startup PID=%s data=%s software=%s',os.getpid(),data_dir,os.environ.get('HANRORO_SOFTWARE','0'))
    import faulthandler
    fault_log=(data_dir/'hang.log').open('a',encoding='utf-8');faulthandler.enable(file=fault_log);faulthandler.dump_traceback_later(20,repeat=True,file=fault_log)
    logging.info('Startup stage: loading fonts; platform=%s skip_custom=%s',os.environ.get('QT_QPA_PLATFORM','default'),os.environ.get('HANRORO_SKIP_CUSTOM_FONTS','0'))
    register_fonts(ROOT/'assets/fonts',QFontDatabase,skip=os.environ.get('HANRORO_SKIP_CUSTOM_FONTS')=='1',marker=data_dir/'font-loading.json')
    logging.info('Startup stage: fonts ready; ui=%s',ui_family('round'))
    sock=None;server=None
    if not args.render and not args.smoke_run:
        channel='hanroro-'+hashlib.sha256(str(data_dir).encode()).hexdigest()[:16]
        sock=QLocalSocket();sock.connectToServer(channel)
        if sock.waitForConnected(400):
            sock.write(b'show');sock.waitForBytesWritten(500)
            faulthandler.cancel_dump_traceback_later();faulthandler.disable();fault_log.close();return 0
        QLocalServer.removeServer(channel);server=QLocalServer();server.listen(channel)
    logging.info('Startup stage: creating controller')
    p=Program(app,args);p.server=server
    logging.info('Startup stage: entering event loop')
    if server:
        def receive():
            conn=server.nextPendingConnection()
            if not conn:return
            handled={'done':False}
            def command():
                if handled['done'] or not conn.bytesAvailable():return
                handled['done']=True;message=bytes(conn.readAll()).decode('utf-8','replace').strip();conn.disconnectFromServer();conn.deleteLater()
                if message=='quit':app.quit()
                else:p.settings(0)
            conn.readyRead.connect(command);command()
        server.newConnection.connect(receive)
    heartbeat=QTimer();heartbeat.setInterval(5000);heartbeat.timeout.connect(lambda:faulthandler.dump_traceback_later(20,repeat=True,file=fault_log));heartbeat.start()
    try:return app.exec()
    finally:faulthandler.cancel_dump_traceback_later();faulthandler.disable();fault_log.close()


if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        import traceback
        detail=traceback.format_exc();logging.exception('Application failed')
        if QApplication.instance():QMessageBox.critical(None,'한로로 바탕화면 위젯 · 실행 오류','실행 중 오류가 발생했습니다. diagnose.bat으로 다시 실행하면 상세 오류를 확인할 수 있습니다.\n\n'+detail[-1800:])
        else:print(detail,file=sys.stderr)
        sys.exit(1)
