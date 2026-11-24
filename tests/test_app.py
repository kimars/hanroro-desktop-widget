import copy,os,sys,wave
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_AUDIO_BACKEND','pulseaudio')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from PySide6.QtCore import Qt,QPoint,QUrl,QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import Program

@pytest.fixture(scope='module')
def app():
    a=QApplication.instance() or QApplication([]);a.setOrganizationName('MarsTest');a.setApplicationName('HanroroTest');return a

@pytest.fixture
def program(tmp_path,app):
    p=Program(app,SimpleNamespace(data_dir=str(tmp_path),render=None,smoke_run=False,preview=True));QTest.qWait(250)
    yield p
    p.shutdown()
    for v in p.bridge.views:v.hide();v.deleteLater()
    if p.bridge._settings:p.bridge._settings.close();p.bridge._settings.deleteLater()
    QTest.qWait(20)

def test_scene_renders_and_controls_work(program):
    p=program;b=p.bridge;view=p.preview
    assert not p.errors and not view.grabWindow().isNull()
    assert b.photo.startswith('file:') and b.secondPhoto!=b.photo
    assert view.rootObject().findChild(QObject,'photoViewer') is None
    # Toolbar edit button, mapped from the 1600x900 design to 1440x810.
    QTest.mouseClick(view,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(1337,752));QTest.qWait(50)
    assert b.editMode
    b.moveWidget('clock',150,140);b.persist()
    assert p.store.data['widgets']['clock']['x']==150
    assert not p.errors

def test_settings_roundtrip_and_widget_visibility(program):
    p=program;b=p.bridge;p.settings(2);QTest.qWait(50);panel=b._settings
    b.hideWidget('memo');panel.show_section(2)
    assert not panel.widget_checks['memo'].isChecked()
    panel.widget_checks['memo'].setChecked(True);assert b.state['widgets']['memo']['visible']
    panel.reset_layout();assert b.state['widgets']['memo']['visible'] and panel.widget_checks['memo'].isChecked()
    panel.memo.setPlainText('새 메모');b.persist()
    assert p.store.data['memo']=='새 메모'
    panel.task_title_input.setText('연습하기');panel.add_task();b.toggleTask(0)
    assert p.store.data['tasks'][0]['done']
    panel.event_title.setText('기념일');panel.add_event()
    assert b.state['eventsView'][0]['day']=='D-DAY'
    for i in range(7):panel.show_section(i);QTest.qWait(10)
    assert not p.errors

def test_external_media_state_and_controls(program,monkeypatch):
    b=program.bridge;sent=[];monkeypatch.setattr(b.media,'send',lambda request:sent.append(request) or True)
    b.media.apply({'connected':True,'source':'Spotify.exe','sourceName':'Spotify','title':'입춘','artist':'한로로','playing':True,'position':30000,'duration':180000,'canPlayPause':True,'canNext':True,'canPrevious':True,'canSeek':True})
    QTest.qWait(40)
    assert b.playing and b.trackTitle=='입춘' and b.trackArtist=='한로로'
    assert b.elapsed=='00:30' and b.duration=='03:00' and abs(b.progress-1/6)<.001
    b.playPause();b.nextTrack();b.previousTrack();b.seek(.5)
    assert [r['action'] for r in sent]==['toggle','next','previous','seek']
    assert sent[-1]['fraction']==.5 and all(r['source']=='Spotify.exe' for r in sent)
    b.media.apply({'connected':False});QTest.qWait(20)
    assert not b.playing and b.trackTitle=='재생 앱 연결' and b.progress==0
    assert not program.errors

def test_video_background_decodes(program):
    from PySide6.QtMultimedia import QVideoSink
    b=program.bridge;b.set_option('backgroundMode','video');QTest.qWait(400)
    assert not program.errors
    assert b.state['backgroundUrl'].endswith('loop.mp4')
    output=program.preview.rootObject().findChild(QObject,'backgroundVideoOutput')
    assert output.property('videoSink').videoFrame().isValid()
    b.set_paused(True);assert b.backgroundPaused
    b.set_option('backgroundMode','room')

def test_scale_keeps_widget_within_scene(program):
    b=program.bridge;b.moveWidget('photos',1300,800);b.scaleWidget('photos',1.8)
    r=b.state['widgets']['photos'];assert r['x']+210*r['scale']<=1600 and r['y']+280*r['scale']<=900


def test_shortcut_editor_can_add_reorder_and_remove(program):
    p=program;p.settings(4);panel=p.bridge._settings
    before=len(p.store.data['links'])
    panel.link_title.setText('새 버튼');panel.link_target.setText('https://example.com');panel.add_link()
    assert len(p.store.data['links'])==before+1
    panel.reorder_link(-1)
    assert p.store.data['links'][-2]['title']=='새 버튼'
    panel.delete_link();assert len(p.store.data['links'])==before


def test_static_desktop_does_not_depend_on_worker_or_open_preview(program,monkeypatch):
    import main
    p=program
    class Host:
        calls=[]
        def attach_widgets(self,hwnd):self.calls.append('widgets');return True
        def apply_static_wallpaper(self,path,screen,directory):
            assert Path(path).is_file();self.calls.append('wallpaper');return True
        def worker(self):raise AssertionError('Static mode must not depend on WorkerW')
        def sync_overlay(self):pass
        def detach(self):pass
        def alive(self):return True
        def fullscreen_app(self,screen):return False
    p.host=Host();monkeypatch.setattr(main,'IS_WINDOWS',True)
    requests=[]
    def submit(request):
        requests.append(request);p.host.calls.append('wallpaper');return True
    monkeypatch.setattr(p.wallpaper_jobs,'start',submit)
    p.desktop();QTest.qWait(50)
    p.native_finished(requests[0],True,'')
    assert p.bridge.desktop and not p.preview.isVisible()
    assert p.overlay.flags() & Qt.WindowType.FramelessWindowHint
    assert p.host.calls==['widgets','wallpaper']
    # Editing unrelated data must not keep rewriting the native wallpaper.
    p.bridge.set_option('memo','test');p.refresh_wallpaper()
    assert p.host.calls==['widgets','wallpaper']
    p.leave_desktop()


def test_failed_shell_attach_never_opens_regular_window(program,monkeypatch):
    import main
    p=program;p.preview.hide()
    class Host:
        def attach_widgets(self,hwnd):return False
        def detach(self):pass
    p.host=Host();monkeypatch.setattr(main,'IS_WINDOWS',True)
    p.desktop()
    assert not p.preview.isVisible() and not p.bridge.desktop


def test_inline_memo_typing_saves_without_settings_window(program):
    p=program;b=p.bridge;root=p.preview.rootObject()
    card=root.findChild(QObject,'memoCard');editor=root.findChild(QObject,'memoEditor')
    assert card is not None and editor is not None and b._settings is None
    button=editor
    from PySide6.QtCore import QPointF
    center=button.mapToScene(QPointF(button.property('width')/2,button.property('height')/2))
    QTest.mouseClick(p.preview,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,center.toPoint());QTest.qWait(80)
    assert b.inputActive and editor.property('activeFocus')
    
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    for char in 'direct desktop memo':
        QApplication.sendEvent(p.preview,QKeyEvent(QEvent.Type.KeyPress,0,Qt.KeyboardModifier.NoModifier,char))
        QApplication.sendEvent(p.preview,QKeyEvent(QEvent.Type.KeyRelease,0,Qt.KeyboardModifier.NoModifier,char))
    QTest.qWait(300)
    assert b.store.data['memo']=='direct desktop memo'
    assert wait_for_saved_memo(b,'direct desktop memo')
    assert b._settings is None
    QTest.keyClick(p.preview,Qt.Key.Key_Return,Qt.KeyboardModifier.ControlModifier);QTest.qWait(40)
    assert not b.inputActive and not card.property('editing')
    b.setMemo('한글 메모\n두 번째 줄');QTest.qWait(40)
    assert editor.property('text')=='한글 메모\n두 번째 줄'
    assert not p.errors


def test_inline_memo_reveals_hidden_widget_and_commits_on_focus_loss(program):
    b=program.bridge;b.hideWidget('memo');b.editMemo();QTest.qWait(50)
    assert b.state['widgets']['memo']['visible'] and b.inputActive
    editor=program.preview.rootObject().findChild(QObject,'memoEditor');editor.setProperty('text','수정한 내용')
    b.setInputActive(False);QTest.qWait(40);b.persist()
    assert b.store.data['memo']=='수정한 내용' and not b.inputActive


def test_widget_palette_contrast_and_button_app_target(program,monkeypatch):
    import backend,app_windows
    b=program.bridge;b.setWidgetColor('memo','#f7e7e6')
    assert b.state['appearance']['memo']['ink']=='#233441'
    b.setWidgetColor('memo','#253343');assert b.state['appearance']['memo']['ink']=='#f3f7fb'
    b.store.data['links']=[{'title':'계산기','target':'app:Calculator!App','glyph':'app'}]
    launched=[];monkeypatch.setattr(backend.sys,'platform','win32');monkeypatch.setattr(app_windows,'toggle_or_launch',lambda target:launched.append(target) or 'opened')
    b.launch(0);assert launched==['app:Calculator!App']


def test_failed_wallpaper_is_not_retried_on_each_memo_edit(program,monkeypatch):
    import main
    p=program;count=[]
    p.bridge.desktop=True;p._desktop_background_mode=p.store.data['backgroundMode']
    monkeypatch.setattr(p.wallpaper_jobs,'start',lambda request:count.append(request) or True)
    monkeypatch.setattr(main,'IS_WINDOWS',True)
    p.refresh_wallpaper();p.native_finished(count[0],False,'native failure');p.bridge.setMemo('unrelated change');p.refresh_wallpaper()
    assert len(count)==1
    p.bridge.desktop=False


def test_tray_single_click_opens_settings_and_menu_is_kept(program,monkeypatch):
    import main,gc
    from PySide6.QtWidgets import QSystemTrayIcon
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',lambda:True)
    program.make_tray();gc.collect()
    assert program.tray.contextMenu() is program.tray_menu
    program.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger);QTest.qWait(30)
    assert program.bridge._settings is not None and program.bridge._settings.isVisible()


def test_shutdown_is_idempotent_and_cancels_native_work(program,monkeypatch):
    calls=[];monkeypatch.setattr(program.wallpaper_jobs,'cancel',lambda:calls.append('cancel'))
    program.shutdown();program.shutdown()
    assert calls==['cancel'] and program._shutting_down


def test_memo_typing_does_not_refresh_whole_scene_or_render_wallpaper(program,monkeypatch):
    b=program.bridge;states=[];memos=[]
    b.stateChanged.connect(lambda:states.append(1));b.memoChanged.connect(lambda:memos.append(1))
    def forbidden(*_):raise AssertionError('Typing must not compose a wallpaper or refresh all widgets')
    monkeypatch.setattr(b,'wallpaper_path',forbidden)
    for i in range(100):b.setMemo('입력 중 '+str(i))
    assert states==[] and len(memos)==100 and b.memo=='입력 중 99'
    QTest.qWait(300)
    assert wait_for_saved_memo(b,'입력 중 99')


def test_state_snapshot_and_input_region_work_are_reused(program,monkeypatch):
    b=program.bridge;b.invalidate_state();calls=[];original=b.appearance
    monkeypatch.setattr(b,'appearance',lambda:calls.append(1) or original())
    for _ in range(100):b.state
    assert len(calls)==1
    masks=[];view=SimpleNamespace(setMask=lambda region:masks.append(region))
    old_overlay=b.overlay;old_desktop=b.desktop;b.overlay=view;b.desktop=True
    try:
        for _ in range(100):b.hitRegions([{'x':20,'y':20,'w':300,'h':200}])
        assert len(masks)==1
        b.overlay=SimpleNamespace(setMask=lambda region:masks.append(region));b.hitRegions([{'x':20,'y':20,'w':300,'h':200}]);assert len(masks)==2
    finally:b.overlay=old_overlay;b.desktop=old_desktop


def test_memo_preedit_is_not_replaced_by_global_state_updates(program):
    from PySide6.QtGui import QInputMethodEvent
    b=program.bridge;b.editMemo();QTest.qWait(60)
    states=[];b.stateChanged.connect(lambda:states.append(1))
    for composing in ['ㅎ','하','한']:
        QApplication.sendEvent(program.preview,QInputMethodEvent(composing,[]))
    commit=QInputMethodEvent();commit.setCommitString('한');QApplication.sendEvent(program.preview,commit)
    assert b.memo=='한' and states==[]
    b.setInputActive(False)


def wait_for_saved_memo(bridge,expected):
    # QTest.qWait holds the Python GIL; give the asynchronous disk worker time to run.
    import time,json
    deadline=time.monotonic()+1
    while time.monotonic()<deadline:
        QTest.qWait(10);time.sleep(.005)
        if bridge.store.path.exists() and json.loads(bridge.store.path.read_text('utf-8'))['memo']==expected:return True
    return False

def test_update_character_notice_is_above_widgets_and_clickable(program,monkeypatch):
    from PySide6.QtCore import QPointF
    p=program;b=p.bridge;view=p.preview;b.previewUpdateNotice();QTest.qWait(180)
    notice=view.rootObject().findChild(QObject,'updateAnnouncement')
    assert notice.property('visible') and notice.property('z')>10000
    dismiss=view.rootObject().findChild(QObject,'noticeDismiss')
    point=dismiss.mapToScene(QPointF(dismiss.width()/2,dismiss.height()/2)).toPoint()
    QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,point);QTest.qWait(40)
    assert not b.updateNotice['visible']
    calls=[];monkeypatch.setattr(b.updates,'download',lambda:calls.append('download'))
    b.updates.publish({'status':'available','version':'9.2.0'});QTest.qWait(180)
    action=view.rootObject().findChild(QObject,'noticeUpdateNow');point=action.mapToScene(QPointF(action.width()/2,action.height()/2)).toPoint()
    QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,point);QTest.qWait(30)
    assert calls==['download'] and not p.errors

def test_update_character_has_its_own_desktop_paint_region(program):
    from PySide6.QtCore import QPointF
    p=program;b=p.bridge;view=p.preview;root=view.rootObject();b.previewUpdateNotice();QTest.qWait(520)
    notice=root.findChild(QObject,'updateAnnouncement');character=root.findChild(QObject,'updateCharacter')
    assert notice.property('characterReady') and character.implicitWidth()>0
    masks=[];b.desktop=True;b.overlay=SimpleNamespace(setMask=lambda region:masks.append(region))
    root.setProperty('layerRole','overlay');root.updateRegions()
    # A decorative pixel left of all regular widgets must still be painted,
    # without turning it into an invisible mouse-blocking rectangle.
    point=character.mapToScene(QPointF(8,80)).toPoint()
    assert masks[-1].contains(point) and not b._interactive_region.contains(point)
    b.dismissUpdateNotice();root.updateRegions();assert not masks[-1].contains(point)
    assert not p.errors
