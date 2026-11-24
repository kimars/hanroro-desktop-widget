"""Exercise editor workflows with real Qt widgets and persistent state."""
import os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_AUDIO_BACKEND','pulseaudio')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from PySide6.QtWidgets import QApplication,QTabWidget,QAbstractSpinBox,QPushButton,QLineEdit
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from state import Store
from backend import Bridge
from panels import Settings
from panel_ui import ToggleSwitch,Stepper

@pytest.fixture
def panel(tmp_path):
    app=QApplication.instance() or QApplication([])
    b=Bridge(Store(tmp_path),Path(__file__).resolve().parents[1]/'assets')
    p=Settings(b,app);p.resize(1220,840);p.show();QTest.qWait(30)
    yield p
    b.persist();b.slides.stop();b.midnight.stop();b.debounce.stop();b.writer.close();b.media.close();b.weather_link.close();b.telemetry_link.close();b.features_controller.close();b.update_prompt.close();b.updates.close();p.close();p.deleteLater();b.deleteLater();QTest.qWait(10)

def test_shortcuts_modes_search_edit_and_save(panel):
    p=panel;p.show_section(4);assert not p.link_save.isEnabled()
    p.set_link_mode(1);assert p.link_target.isVisible()
    p.link_title.setText('작업실');p.link_target.setText('https://example.com')
    assert p.link_save.isEnabled()
    count=len(p.b.store.data['links']);QTest.mouseClick(p.link_save,Qt.LeftButton)
    assert len(p.b.store.data['links'])==count+1
    p.link_title.setText('음악 작업실');QTest.mouseClick(p.link_save,Qt.LeftButton)
    assert p.b.store.data['links'][-1]['title']=='음악 작업실'
    p.link_search.setText('음악 작업실')
    assert sum(not p.link_list.item(i).isHidden() for i in range(p.link_list.count()))==1
    p.link_search.clear();p.reorder_link(-1);assert p.b.store.data['links'][-2]['title']=='음악 작업실'
    p.delete_link();assert len(p.b.store.data['links'])==count
    p.b.persist();assert [(r['title'],r['target']) for r in Store(p.b.store.directory).data['links']]==[(r['title'],r['target']) for r in p.b.store.data['links']]

def test_wallpaper_selection_is_independent_from_media_artwork(panel):
    p=panel;p.show_section(1);before=p.b.photo
    path=p.b.store.data['photos'][1];p.set_background(path,False)
    assert Path(p.b.store.data['imageBackground']).is_file() and p.b.store.data['backgroundMode']=='image'
    assert p.b.photo==before and p.b.albumCover==''
    assert not hasattr(p,'photo_list') and not hasattr(p,'photo_interval')
    p.wallpaper_fit.setCurrentIndex(1);assert p.b.store.data['wallpaperFit']=='fit'
    assert not p.wallpaper_preview.pixmap().isNull()

def test_switch_and_stepper_are_interactive(panel):
    p=panel;p.show_section(2);step=p.widget_spins['clock'];before=step.value()
    assert isinstance(step.number,QLineEdit) and step.number.text()==f"{before:.2f}"
    plus=next(b for b in step.findChildren(QPushButton) if b.text()=='+')
    QTest.mouseClick(plus,Qt.LeftButton);assert step.value()>before
    assert p.b.store.data['widgets']['clock']['scale']==step.value()
    step.number.setText('1.35');step.number.commit();assert p.b.store.data['widgets']['clock']['scale']==1.35
    step.number.setText('999');step.number.commit();assert step.value()==1.8
    check=p.widget_checks['clock'];before=check.isChecked();QTest.mouseClick(check,Qt.LeftButton,pos=QPoint(18,18));assert check.isChecked()!=before
    assert p.b.store.data['widgets']['clock']['visible']==check.isChecked()

def test_notes_are_separate_tabs_and_details_save(panel):
    p=panel;p.show_section(5);tabs=p.stack.widget(5).findChild(QTabWidget);assert tabs.count()==3
    tabs.setCurrentIndex(1);p.task_title_input.setText('공연 준비');p.task_detail_input.setPlainText('티켓 챙기기');p.add_task()
    p.tasks.setCurrentRow(0);p.task_detail_input.setPlainText('티켓과 신분증 챙기기');QTest.qWait(350)
    assert p.b.store.data['tasks'][0]['detail']=='티켓과 신분증 챙기기'
    tabs.setCurrentIndex(2);p.event_title.setText('공연');p.add_event();assert p.b.store.data['events'][-1]['title']=='공연'
    assert not p.events.isHidden()


def test_connection_type_change_clears_previous_destination(panel):
    p=panel;p.show_section(4);p.link_list.setCurrentRow(0)
    assert p.link_target.text().startswith('https:')
    p.switch_link_mode(0)
    assert not p.link_target.text() and not p.link_save.isEnabled()


def test_photo_preview_keeps_portrait_landscape_and_square_ratio(panel,tmp_path):
    from PySide6.QtGui import QImage,QColor
    from PySide6.QtCore import QSize
    from panel_ui import thumbnail
    for width,height in [(120,300),(400,100),(180,180)]:
        path=tmp_path/f'{width}-{height}.png';img=QImage(width,height,QImage.Format_RGB32);img.fill(QColor('red'));assert img.save(str(path))
        preview=thumbnail(path).actualSize(QSize(220,190))
        assert abs(preview.width()/preview.height()-width/height)<.04
    paths=[str(tmp_path/f'{w}-{h}.png') for w,h in [(120,300),(400,100),(180,180)]]
    assert not hasattr(panel,'photo_list')


def test_settings_has_no_sidebar_copy_or_card_descriptions(panel):
    from PySide6.QtWidgets import QLabel
    assert panel.windowTitle()=='한로로 바탕화면 위젯'
    texts=[w.text() for w in panel.findChildren(QLabel) if not w.isHidden()]
    assert '내 공간' not in texts and '바탕화면을 원하는 모습으로' not in texts
    assert '선택한 사진을 바탕화면 배경으로 사용할 수 있어요.' not in texts


def test_recycle_bin_can_be_added_saved_and_opened(panel,monkeypatch):
    import backend
    p=panel;p.new_link();p.switch_link_mode(3)
    p.action_combo.setCurrentIndex(p.action_combo.findData('action:recyclebin'));p.submit_link()
    row=p.b.store.data['links'][-1]
    assert row['target']=='action:recyclebin' and row['glyph']=='trash' and row['title']=='휴지통'
    calls=[];monkeypatch.setattr(backend.sys,'platform','win32');monkeypatch.setattr(backend.os,'startfile',lambda target:calls.append(target),raising=False)
    p.b.launch(len(p.b.store.data['links'])-1)
    assert calls==['shell:RecycleBinFolder']
    p.b.persist();assert Store(p.b.store.directory).data['links'][-1]['target']=='action:recyclebin'


def test_color_picker_uses_mouse_plane_and_hue_without_hex_field(panel):
    from PySide6.QtGui import QColor
    from panel_ui import PaletteDialog
    dialog=PaletteDialog(QColor('#73a192'),panel);dialog.show();QTest.qWait(30)
    assert not dialog.findChildren(QLineEdit)
    dialog.hue.setValue(200);QTest.mouseClick(dialog.plane,Qt.LeftButton,pos=QPoint(dialog.plane.width()-5,5))
    assert dialog.selected.saturation()>220 and dialog.selected.value()>220
    QTest.mouseClick(dialog.plane,Qt.LeftButton,pos=QPoint(5,dialog.plane.height()-5))
    assert dialog.selected.value()<20
    dialog.select_swatch(QColor('#ff0000'));assert dialog.selected.name()=='#ff0000'
    dialog.reject()


def test_wallpaper_fill_and_fit_cover_full_desktop(tmp_path):
    from PySide6.QtGui import QImage,QColor
    from wallpaper import render_wallpaper
    path=tmp_path/'wide.png';image=QImage(200,100,QImage.Format_RGB32);image.fill(QColor('#ff0000'));image.save(str(path))
    fill=QImage(str(render_wallpaper(path,tmp_path/'render',size=(100,100),fit='fill')))
    assert fill.pixelColor(0,50).name()=='#ff0000' and fill.pixelColor(99,50).name()=='#ff0000'
    fit=QImage(str(render_wallpaper(path,tmp_path/'render',size=(100,100),fit='fit')))
    assert fit.pixelColor(50,50).name()=='#ff0000' and fit.pixelColor(50,0).name()!='#ff0000'


def test_compact_navigation_reaches_secondary_pages_and_dark_mode(panel):
    assert panel.nav.count()==6
    for target in range(10):
        panel.open_page(target);assert panel.stack.currentIndex()==target
    panel.open_page(5);panel.nav.setCurrentRow(2);assert panel.stack.currentIndex()==2
    panel.theme.setChecked(True)
    assert panel.b.store.data['theme']=='night' and panel.property('darkTheme')
    assert '#182325' in panel.styleSheet()
    panel.theme.setChecked(False)
    assert panel.b.store.data['theme']=='apricot' and not panel.property('darkTheme')
