import copy,json,math,time,threading
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import QObject,Qt,QPointF,QTimer,QModelIndex
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest,QSignalSpy
from state import Store,validate
from room_items import normalize_item
from telemetry_link import TelemetryLink,EMPTY
from settings_writer import SettingsWriter


def test_audio_frames_do_not_rebuild_system_monitor():
    link=TelemetryLink('unused');audio=QSignalSpy(link.levelsChanged);system=QSignalSpy(link.changed)
    for index in range(100):link.apply({**EMPTY,'levels':[index/100]*32,'cpu':20,'ram':40})
    assert audio.count()==99 and system.count()==1
    link.close()


def test_pending_disk_write_keeps_input_event_loop_free_and_latest_state_wins(tmp_path):
    store=Store(tmp_path);original=store.save;entered=threading.Event();release=threading.Event();writes=[]
    def blocked(snapshot):
        entered.set();release.wait(2);writes.append(snapshot['memo']);original(snapshot)
    store.save=blocked;writer=SettingsWriter(store);state=copy.deepcopy(store.data)
    writer.submit(state);assert entered.wait(.5)
    start=time.perf_counter()
    for index in range(100):writer.submit({**state,'memo':str(index)})
    ticks=[];QTimer.singleShot(0,lambda:ticks.append(1));QTest.qWait(25)
    assert ticks==[1] and time.perf_counter()-start<.25
    release.set();writer.flush({**state,'memo':'final'});writer.close()
    assert json.loads(store.path.read_text())['memo']=='final' and len(writes)<=3


def test_room_import_validation_and_rotated_bounds(tmp_path):
    bad=validate({'decorations':[{'kind':'invalid'},{'kind':'desk','scale':float('nan'),'x':-1000,'y':9000}]})
    assert len(bad['decorations'])==1
    for angle in [-180,-90,-45,0,45,90,180]:
        row=normalize_item({'kind':'desk','x':1600,'y':0,'rotation':angle,'scale':2})
        a=math.radians(angle)
        for x,y in [(0,0),(row['width'],0),(0,row['height']),(row['width'],row['height'])]:
            px=row['x']+(x*math.cos(a)-y*math.sin(a))*row['scale'];py=row['y']+(x*math.sin(a)+y*math.cos(a))*row['scale']
            assert -.001<=px<=1600.001 and 39.999<=py<=900.001
    picture=tmp_path/'portrait.png';image=QImage(100,250,QImage.Format_RGB32);image.fill(QColor('#aabbcc'));image.save(str(picture))
    store=Store(tmp_path/'one');store.data['decorations']=[normalize_item({'kind':'photo','image':store.ingest(picture),'width':108,'height':252})];archive=tmp_path/'scene.hanroom';store.export_scene(archive,'unused');other=Store(tmp_path/'two');other.import_scene(archive)
    assert Path(other.data['decorations'][0]['image']).read_bytes()==picture.read_bytes()


def visual_find(item,name):
    if item.objectName()==name:return item
    for child in item.childItems():
        found=visual_find(child,name)
        if found:return found
    return None

def test_room_editor_drag_scale_layer_lock_delete_and_reopen(tmp_path):
    from main import Program
    app=QApplication.instance();p=Program(app,SimpleNamespace(data_dir=str(tmp_path/'data'),render=None,smoke_run=False,preview=True))
    try:
        QTest.qWait(270);b=p.bridge;root=p.preview.rootObject();assert root.findChild(QObject,'playerSpectrum') and root.findChild(QObject,'lpSpectrum') is None and root.findChild(QObject,'visualizerCard') is None
        b.addFurniture('desk');identity=b.store.data['decorations'][0]['id'];QTest.qWait(50);item=visual_find(root,'decoration-'+identity);assert item is not None
        reset=QSignalSpy(b.room_model.modelReset);b.toggleEdit();QTest.qWait(20)
        begin=item.mapToScene(QPointF(300,120)).toPoint();end=begin+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(45,-30)
        QTest.mousePress(p.preview,Qt.LeftButton,pos=begin);QTest.mouseMove(p.preview,begin+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(15,-10),20);QTest.mouseMove(p.preview,end,40);QTest.mouseRelease(p.preview,Qt.LeftButton,pos=end);QTest.qWait(50)
        assert b.store.data['decorations'][0]['x']>430 and visual_find(root,'decoration-'+identity) is item and reset.count()==0
        b.adjustDecoration(identity,'scale',.8);b.adjustDecoration(identity,'rotation',15);b.adjustDecoration(identity,'z',10);QTest.qWait(20)
        assert item.property('scale')==.8 and item.property('rotation')==15 and item.property('z')==300 # selected edit handle sits above other items
        b.actionDecoration(identity,'lock');old=copy.deepcopy(b.store.data['decorations'][0]);b.moveDecoration(identity,0,0);b.actionDecoration(identity,'delete');assert b.store.data['decorations'][0]==old
        p.settings(8);panel=b._settings;assert panel.stack.currentIndex()==8;panel.room_lock.setChecked(False);assert not b.store.data['decorations'][0]['locked']
        b.actionDecoration(identity,'flip');assert b.store.data['decorations'][0]['flipped'];b.persist();assert Store(tmp_path/'data').data['decorations']==b.store.data['decorations']
        b.actionDecoration(identity,'delete');assert b.room_model.rowCount()==0 and reset.count()==0
        assert not p.errors
    finally:
        p.shutdown()
        for view in b.views:view.hide();view.deleteLater()
        if b._settings:b._settings.close();b._settings.deleteLater()
        QTest.qWait(20)


def test_decorative_pixels_remain_painted_but_do_not_capture_input(tmp_path):
    from backend import Bridge
    from PySide6.QtCore import QPoint
    store=Store(tmp_path);b=Bridge(store,Path(__file__).resolve().parents[1]/'assets');masks=[];b.desktop=True;b.overlay=SimpleNamespace(setMask=lambda region:masks.append(region))
    try:
        b.hitRegions([{'x':10,'y':10,'w':100,'h':100,'paintOnly':True},{'x':200,'y':10,'w':100,'h':100}])
        assert masks[-1].contains(QPoint(40,40)) and not b._interactive_region.contains(QPoint(40,40))
        assert b._interactive_region.contains(QPoint(230,40))
        b.hitRegions([{'x':10,'y':10,'w':100,'h':100,'paintOnly':False},{'x':200,'y':10,'w':100,'h':100}])
        assert b._interactive_region.contains(QPoint(40,40)) and len(masks)==2
    finally:b.desktop=False;b.overlay=None;b.media.close();b.telemetry_link.close();b.features_controller.close();b.writer.close()


def test_decoration_scene_regions_include_locked_items_and_rotation(tmp_path):
    from main import Program
    app=QApplication.instance();p=Program(app,SimpleNamespace(data_dir=str(tmp_path),render=None,smoke_run=False,preview=True))
    try:
        QTest.qWait(260);b=p.bridge;b.addFurniture('chair');row=b.store.data['decorations'][0];b.adjustDecoration(row['id'],'rotation',30);b.actionDecoration(row['id'],'lock');QTest.qWait(20)
        rows=[];b.hitRegions=lambda value:rows.extend(value);root=p.preview.rootObject();root.setProperty('layerRole','overlay');root.updateRegions();assert any(r.get('paintOnly') for r in rows);assert not p.errors
    finally:
        p.shutdown()
        for view in p.bridge.views:view.hide();view.deleteLater()
        QTest.qWait(10)


def test_layout_updates_do_not_refresh_wallpaper_or_rebuild_other_widgets(tmp_path):
    from backend import Bridge
    b=Bridge(Store(tmp_path),Path(__file__).resolve().parents[1]/'assets');states=QSignalSpy(b.stateChanged);layouts=QSignalSpy(b.layoutChanged)
    try:
        for index in range(100):b.moveWidget('memo',400+index,300)
        b.scaleWidget('memo',1.2)
        assert states.count()==0 and layouts.count()==101 and b.widgetLayout('memo')['x']==499
        b.addFurniture('chair');resets=QSignalSpy(b.room_model.modelReset);changed=QSignalSpy(b.room_model.dataChanged);identity=b.store.data['decorations'][0]['id']
        for index in range(100):b.moveDecoration(identity,500+index,400)
        assert resets.count()==0 and changed.count()==100
    finally:b.media.close();b.telemetry_link.close();b.features_controller.close();b.writer.close()


def test_portable_autostart_uses_current_launcher(tmp_path,monkeypatch):
    import backend,sys
    b=backend.Bridge(Store(tmp_path/'data'),Path(__file__).resolve().parents[1]/'assets')
    folder=tmp_path/'app';(folder/'_internal').mkdir(parents=True);launcher=folder/'한로로 바탕화면 위젯.exe';launcher.write_bytes(b'fixture')
    values=[]
    class Key:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    registry=SimpleNamespace(HKEY_CURRENT_USER=0,REG_SZ=1,CreateKey=lambda *args:Key(),SetValueEx=lambda *args:values.append(args[-1]))
    try:
        monkeypatch.setattr(backend.sys,'platform','win32');monkeypatch.setattr(backend.sys,'executable',str(folder/'_internal/pythonw.exe'));monkeypatch.setitem(sys.modules,'winreg',registry)
        b.set_autostart(True);assert str(launcher) in values[0] and 'pythonw' not in values[0]
    finally:b.media.close();b.telemetry_link.close();b.features_controller.close();b.writer.close()
