import copy, math
import pytest
from urllib.parse import parse_qs,urlparse
from PySide6.QtCore import Qt,QPoint,QObject
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QSlider
from state import Store,validate

def test_dark_theme_preserves_custom_colors_and_switches_player(tmp_path,qt_application):
    from backend import Bridge
    from pathlib import Path
    b=Bridge(Store(tmp_path),Path(__file__).resolve().parents[1]/'assets')
    b.store.data['widgets']['memo']['color']='#fad1d9';b.set_option('theme','night')
    assert b.appearance()['memo']['solid']=='#fad1d9'
    assert b.appearance()['player']['dark'] and b.appearance()['calendar']['dark']
    b.set_option('widgetColor','#bde0cd');assert b.appearance()['calendar']['solid']=='#bde0cd'
    b.set_option('nightLighting',True);b.persist();restored=Store(tmp_path)
    assert restored.data['nightLighting'] and restored.data['widgets']['memo']['color']=='#fad1d9'
    b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.telemetry_link.close();b.features_controller.close();b.update_prompt.close();b.updates.close()

def test_palette_wheel_has_no_slider_and_mouse_changes_hue(qt_application):
    from panel_ui import PaletteDialog
    d=PaletteDialog(QColor('#00ff00'));d.show();QTest.qWait(20)
    assert not d.findChildren(QSlider)
    QTest.mouseClick(d.hue,Qt.LeftButton,pos=QPoint(d.hue.width()//2+48,d.hue.height()//2))
    assert d.plane.hue<10 or d.plane.hue>350
    d.close();d.deleteLater();QTest.qWait(10)


def test_native_photo_night_dim_changes_file_and_restores_day(tmp_path,qt_application,monkeypatch):
    from pathlib import Path
    from PySide6.QtGui import QImage
    from backend import Bridge
    source=tmp_path/'white.png';image=QImage(24,24,QImage.Format_RGB32);image.fill(QColor('white'));image.save(str(source))
    b=Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets');b.wallpaper_size=(24,24);b.store.data['wallpaperQuality']='native'
    try:
        b.store.data.update(backgroundMode='image',imageBackground=str(source),background=str(source),dim=0,nightLighting=True)
        import backend
        from types import SimpleNamespace
        class Clock:
            hour=22
            @classmethod
            def now(cls):return SimpleNamespace(hour=cls.hour)
        monkeypatch.setattr(backend,'datetime',Clock)
        def rendered():
            b.wallpaper_path()
            for _ in range(150):
                QTest.qWait(10)
                if b._wallpaper_cache_key==b._wallpaper_request:return b.wallpaper_path()
            raise AssertionError('Wallpaper did not finish')
        night=rendered();assert QImage(str(night)).pixelColor(12,12).red()<210
        Clock.hour=12
        day=rendered();assert day!=night and QImage(str(day)).pixelColor(12,12).red()==255
        b.store.data['nightLighting']=False;Clock.hour=22
        assert b.wallpaper_path()==day
    finally:
        b.slides.stop();b.midnight.stop();b.debounce.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.media.close();b.telemetry_link.close();b.features_controller.close();b.update_prompt.close();b.updates.close();b.deleteLater();QTest.qWait(10)


def test_weather_is_removed_from_old_settings():
    data=validate({'weatherCity':'서울','nightLighting':True,'widgets':{'weather':{'visible':True,'x':20,'y':20}}})
    assert 'weatherCity' not in data and 'weather' not in data['widgets']
    assert data['nightLighting']
