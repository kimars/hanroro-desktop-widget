from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import QObject,QPointF
from PySide6.QtWidgets import QApplication,QTabWidget,QAbstractButton
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from room_items import CATALOG
from test_room_and_performance import visual_find
ROOT=Path(__file__).resolve().parents[1]

def test_expanded_catalog_svg_and_moving_layers_are_valid():
    assert len(CATALOG)==26
    for kind,spec in CATALOG.items():
        if kind=='photo':continue
        assert QSvgRenderer(str(ROOT/'assets/furniture'/(kind+'.svg'))).isValid()
        if spec['motion']:
            for suffix in ['-base.svg','-moving.svg']:assert QSvgRenderer(str(ROOT/'assets/furniture'/(kind+suffix))).isValid()
    assert not CATALOG['desk']['motion'] and CATALOG['pendant']['motion']=='sway'


def test_all_furniture_motion_settings_and_audio_position(tmp_path):
    from main import Program
    p=Program(QApplication.instance(),SimpleNamespace(data_dir=str(tmp_path),render=None,smoke_run=False,preview=True))
    try:
        b=p.bridge
        for kind in CATALOG:
            if kind!='photo':b.addFurniture(kind)
        QTest.qWait(320);root=p.preview.rootObject();assert not p.errors and b.room_model.rowCount()==25
        desk=next(r for r in b.store.data['decorations'] if r['kind']=='desk');pendant=next(r for r in b.store.data['decorations'] if r['kind']=='pendant')
        desk_item=visual_find(root,'decoration-'+desk['id']);lamp=visual_find(root,'decoration-'+pendant['id'])
        assert not desk_item.property('motionActive') and lamp.property('motionActive')
        b.actionDecoration(pendant['id'],'animate');QTest.qWait(25);assert not lamp.property('motionActive')
        b.actionDecoration(pendant['id'],'animate');b.toggleEdit();QTest.qWait(25);assert not lamp.property('motionActive') and not b.telemetry_link.config['audio']
        b.toggleEdit();QTest.qWait(25);assert lamp.property('motionActive')
        audio=root.findChild(QObject,'playerSpectrum');record=root.findChild(QObject,'paperRecord');music=root.findChild(QObject,'musicCard')
        assert audio and audio.parentItem() is music and audio.parentItem() is not record
        assert audio.property('y')+audio.property('height')<362
        assert root.findChild(QObject,'countdownCard') is None
        p.settings(8);panel=b._settings;catalog=panel.findChild(QTabWidget,'furnitureCatalog');assert catalog.count()==6
        assert len([btn for btn in panel.findChildren(QAbstractButton) if btn.objectName().startswith('addFurniture_')])==25
        assert not p.errors
    finally:
        p.shutdown()
        for view in p.bridge.views:view.hide();view.deleteLater()
        if b._settings:b._settings.close();b._settings.deleteLater()
        QTest.qWait(20)
