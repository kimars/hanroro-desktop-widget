import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from state import Store,validate
from backend import Bridge
from panels import Settings
from PySide6.QtWidgets import QApplication

def test_slide_validation_and_scene_roundtrip(tmp_path):
    data=validate({'wallpaperRotation':True,'wallpaperSlides':[{'path':'a','seconds':-9},{'path':'b','seconds':'bad'},{'path':'c','seconds':float('inf')},{'path':5}]})
    assert [r['seconds'] for r in data['wallpaperSlides']]==[1,30,30]
    a=Store(tmp_path/'a');image=tmp_path/'p.png';photo=QImage(24,12,QImage.Format_RGB32);photo.fill(0xff236050);photo.save(str(image))
    a.data['wallpaperSlides']=[{'path':a.ingest(image),'seconds':7}];a.data['wallpaperRotation']=True
    archive=tmp_path/'scene.zip';a.export_scene(archive,tmp_path)
    b=Store(tmp_path/'b');b.import_scene(archive)
    assert b.data['wallpaperSlides'][0]['seconds']==7 and Path(b.data['wallpaperSlides'][0]['path']).is_file()
    assert b.data['wallpaperRotation']

def test_rotation_durations_pause_missing_and_video(tmp_path):
    assets=Path(__file__).resolve().parents[1]/'assets';b=Bridge(Store(tmp_path),assets)
    try:
        paths=list((assets/'photos').glob('*.jpg'))[:2]
        b.store.data['wallpaperSlides']=[{'path':str(paths[0]),'seconds':2},{'path':str(paths[1]),'seconds':7},{'path':str(tmp_path/'missing.jpg'),'seconds':1}]
        b.set_option('wallpaperRotation',True)
        assert b.active_wallpaper()==str(paths[0]) and b.slides.interval()==2000
        b.advance_wallpaper();assert b.active_wallpaper()==str(paths[1]) and b.slides.interval()==7000
        b.set_paused(True);assert not b.slides.isActive();remaining=b._slide_remaining
        b.set_paused(False);assert b.slides.isActive() and b.slides.interval()==remaining
        b.set_option('backgroundMode','video');assert not b.slides.isActive()
        b.set_option('backgroundMode','image');assert b.slides.isActive()
        b.store.data['wallpaperSlides'].pop(1);b.wallpaper_slides_changed();assert not b.slides.isActive()
    finally:
        b.slides.stop();b.midnight.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.updates.close();b.media.close();b.telemetry_link.close();b.features_controller.close()

def test_editor_multiselect_time_reorder_delete(tmp_path):
    assets=Path(__file__).resolve().parents[1]/'assets';b=Bridge(Store(tmp_path),assets);panel=Settings(b,QApplication.instance())
    try:
        paths=list((assets/'photos').glob('*.jpg'))[:2];panel.add_wallpaper_paths([str(p) for p in paths]);assert len(b.store.data['wallpaperSlides'])==2 and b.store.data['wallpaperRotation']
        panel.wallpaper_duration(0,11);assert b.store.data['wallpaperSlides'][0]['seconds']==11
        panel.wallpaper_list.setCurrentRow(0);panel.move_wallpaper(1);assert b.store.data['wallpaperSlides'][1]['seconds']==11
        panel.remove_wallpaper();assert len(b.store.data['wallpaperSlides'])==1
        b.persist();assert Store(tmp_path).data['wallpaperSlides']==b.store.data['wallpaperSlides']
    finally:
        panel.close();panel.deleteLater();b.slides.stop();b.midnight.stop();b.media_importer.close();b.wallpaper_cache.close();b.writer.close();b.updates.close();b.media.close();b.telemetry_link.close();b.features_controller.close()
