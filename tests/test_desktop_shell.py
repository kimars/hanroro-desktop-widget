import time,hashlib
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import Qt,QPoint,QSize,QTimer
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from state import Store,validate
from backend import Bridge
from shell_search import rank_apps,local_files
from wallpaper_cache import output_size,WallpaperCache


def pump(predicate,timeout=5000):
    for _ in range(timeout//10):
        QTest.qWait(10);time.sleep(.001)
        if predicate():return
    raise AssertionError('Timed out')


def test_quality_and_preferences_validate():
    assert output_size((1920,1080),'4k')==(3840,2160)
    assert output_size((1080,1920),'4k')==(2160,3840)
    assert output_size((2560,1080),'4k')==(3840,1620)
    d=validate({'macDock':'yes','hideTaskbar':True,'winKeySearch':True,'wallpaperQuality':'invalid','accentColor':'#112233'})
    assert d['macDock'] is True and d['hideTaskbar'] and d['winKeySearch'] and d['wallpaperQuality']=='4k' and d['accentColor']=='#112233'


def test_rank_and_bounded_file_search(tmp_path):
    rows=[{'name':'Photos','target':'p'},{'name':'My Photo','target':'m'},{'name':'Video','target':'v'}]
    assert [r['target'] for r in rank_apps(rows,'photo')]==['p','m']
    (tmp_path/'photo.png').write_bytes(b'a');(tmp_path/'music.txt').write_bytes(b'b')
    assert local_files('photo',[tmp_path])[0]['name']=='photo.png'
    assert not local_files('p',[tmp_path])


def test_wallpaper_import_and_4k_render_are_async_lossless(tmp_path,qt_application):
    source=tmp_path/'image.png';image=QImage(200,100,QImage.Format_RGB32);image.fill(QColor('#ffccaa'));image.save(str(source));original=hashlib.sha256(source.read_bytes()).hexdigest()
    b=Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets')
    ticks=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
    try:
        b.importBackground([str(source)],False);pump(lambda:len(b.store.data['wallpaperSlides'])==1)
        stored=Path(b.store.data['imageBackground']);assert hashlib.sha256(stored.read_bytes()).hexdigest()==original
        b.wallpaper_path();pump(lambda:b._wallpaper_cache_key==b._wallpaper_request)
        reader=__import__('PySide6.QtGui',fromlist=['QImageReader']).QImageReader(str(b.wallpaper_path()));assert reader.size()==QSize(3840,2160)
        assert len(ticks)>3
    finally:
        timer.stop();b.slides.stop();b.midnight.stop();b.debounce.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.updates.close();b.update_prompt.close();b.telemetry_link.close();b.features_controller.close();b.deleteLater();QTest.qWait(10)


def test_shell_search_without_os_changes_and_catalog_cache(tmp_path,qt_application,monkeypatch):
    from desktop_shell import DesktopShell
    b=Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets')
    p=SimpleNamespace(app=qt_application,bridge=b,pick_screen=qt_application.primaryScreen)
    shell=DesktopShell(p);shell.started=True;shell.apps=[{'name':'Test Music','target':'app:test','path':''}]
    calls=[];monkeypatch.setattr(shell,'open_item',calls.append)
    try:
        shell.toggle_search();shell.search.field.setText('Test');QTest.qWait(20)
        assert shell.search.rows[0]['name']=='Test Music'
        QTest.keyClick(shell.search.field,Qt.Key_Return);assert calls[0]['target']=='app:test' and not shell.search.isVisible()
        shell.dock.refresh();assert shell.dock.rows[0]['target']=='shell:search'
        # UI test never changes taskbar visibility or captures the Windows key.
        assert shell.native.process is None
    finally:
        shell.close();b.slides.stop();b.midnight.stop();b.debounce.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.updates.close();b.update_prompt.close();b.telemetry_link.close();b.features_controller.close();b.deleteLater();QTest.qWait(10)


def test_taskbar_order_all_apps_and_multiple_windows():
    from taskbar_catalog import normalize_taskbar,dock_rows,group_windows
    catalog=[{'name':'Z app','target':'app:z','path':'z.exe'},{'name':'A app','target':'app:a','path':'a.exe'}]
    raw=[{'name':'A app','appid':'a','left':200},{'name':'Z app','appid':'z','left':100}]
    pins=normalize_taskbar(raw,catalog);assert [r['target'] for r in pins]==['app:z','app:a']
    windows=[{'name':'Window one','target':'app:z','hwnd':1},{'name':'Window two','target':'app:z','hwnd':2}]
    assert len(group_windows(windows)['app:z'])==2
    assert len(dock_rows(pins,windows))==2
    extra=[{'name':str(i),'target':'app:extra'+str(i)} for i in range(70)]
    assert len(dock_rows(pins,extra))==72


def test_dock_has_pages_restores_widget_buttons_and_uses_desktop_layer(tmp_path,qt_application):
    from desktop_shell import DesktopShell
    from PySide6.QtCore import Qt
    b=Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets');shell=DesktopShell(SimpleNamespace(app=qt_application,bridge=b,pick_screen=qt_application.primaryScreen))
    try:
        shell.taskbar_rows=[{'name':str(i),'target':'app:'+str(i),'kind':'taskbar'} for i in range(70)];shell.taskbar_loaded=True;shell.dock.refresh()
        assert not shell.dock.windowFlags()&Qt.WindowStaysOnTopHint
        assert len([r for r in shell.dock.all_rows if r.get('kind')=='taskbar'])==70 and shell.dock.pages>1
        assert shell.dock.rows[-1]['target']=='shell:next'
        source=(Path(__file__).resolve().parents[1]/'qml/Scene.qml').read_text();line=next(l for l in source.splitlines() if 'LauncherCard {' in l)
        assert 'scene.layerRole' in line  # Launcher shortcuts live in the system dock on the desktop.
    finally:
        shell.close();b.slides.stop();b.midnight.stop();b.debounce.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.updates.close();b.update_prompt.close();b.telemetry_link.close();b.features_controller.close();b.deleteLater();QTest.qWait(10)


def test_window_picker_keeps_all_windows_and_start_has_all_apps(tmp_path,qt_application,monkeypatch):
    import desktop_shell
    b=Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets');shell=desktop_shell.DesktopShell(SimpleNamespace(app=qt_application,bridge=b,pick_screen=qt_application.primaryScreen));shell.started=True
    try:
        shell.running_rows=[{'target':'app:test','hwnd':i,'pid':10,'name':'Document '+str(i)} for i in range(4)]
        shell.choose_item({'name':'Test','target':'app:test'});assert len(shell.chooser.entries)==4;shell.chooser.close()
        shell.apps=[{'name':'App '+str(i),'target':'app:'+str(i),'path':''} for i in range(300)];shell.toggle_search();shell.search.field.clear();shell.search.query_changed()
        assert shell.search.results.count()==300
        from PySide6.QtWidgets import QListView
        assert shell.search.results.viewMode()==QListView.ViewMode.IconMode
        b.media.data.update(connected=True,playing=False);b.sync_telemetry();assert not b.telemetry_link.config['audio']
        b.media.data.update(playing=True);b.sync_telemetry();assert b.telemetry_link.config['audio']
    finally:
        shell.close();b.slides.stop();b.midnight.stop();b.debounce.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.updates.close();b.update_prompt.close();b.telemetry_link.close();b.features_controller.close();b.deleteLater();QTest.qWait(10)
