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
