import ctypes,json,sys,subprocess
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import windows_desktop as native
from app_catalog import collect_apps,app_shell_target
from state import Store,validate,layout_for,WIDGET_SIZES

class Function:
    def __init__(self,call):self.call=call
    def __call__(self,*args):return self.call(*args)

def test_wallpaper_com_uses_local_server(monkeypatch):
    calls=[]
    ole=SimpleNamespace(CoInitializeEx=Function(lambda *_:0),CoUninitialize=Function(lambda:calls.append('uninit')),CoTaskMemFree=Function(lambda *_:None),CoCreateInstance=Function(lambda cls,outer,context,iid,ptr:calls.append(context) or 0))
    monkeypatch.setattr(native,'IS_WINDOWS',True)
    monkeypatch.setattr(ctypes,'WinDLL',lambda *_:ole,raising=False)
    wall=native.NativeWallpaper();wall.close()
    assert calls==[4,'uninit']

def test_icon_visibility_recovers_after_restart_and_preserves_hidden(tmp_path):
    visibility={11:True,12:False};calls=[]
    def show(hwnd,command):calls.append((hwnd,command));visibility[hwnd]=command!=0
    host=SimpleNamespace(desktop_icon_views=lambda:list(visibility),u=SimpleNamespace(IsWindowVisible=lambda hwnd:visibility[hwnd],ShowWindow=show))
    icons=native.DesktopIcons(host,tmp_path);icons.hide()
    assert not any(visibility.values()) and icons.path.is_file()
    restarted=native.DesktopIcons(host,tmp_path);restarted.hide();restarted.restore()
    # The original visible list is restored; the originally hidden list must stay hidden.
    assert visibility=={11:True,12:False}
    assert not icons.path.exists()

def test_explicit_recovery_handles_corrupt_record(tmp_path):
    (tmp_path/'desktop-icons-session.json').write_text('[]')
    calls=[];host=SimpleNamespace(desktop_icon_views=lambda:[5],u=SimpleNamespace(ShowWindow=lambda *a:calls.append(a)))
    native.DesktopIcons(host,tmp_path).restore(force=True)
    assert calls==[(5,5)]

def test_focus_only_enabled_for_inline_edit(monkeypatch):
    monkeypatch.setattr(native,'IS_WINDOWS',True)
    host=object.__new__(native.DesktopHost);host.overlay=100
    style=[0x08000080];focus=[7];calls=[]
    host.getlong=lambda *_:style[0]
    host.setlong=lambda hwnd,index,value:style.__setitem__(0,value)
    def foreground(hwnd):focus[0]=hwnd;calls.append(hwnd)
    host.u=SimpleNamespace(GetForegroundWindow=lambda:focus[0],SetForegroundWindow=foreground,SetFocus=lambda *_:None,IsWindow=lambda _:True)
    host.set_input_active(True);assert not style[0]&0x08000000
    host.set_input_active(False);assert style[0]&0x08000000 and focus[0]==7

def test_app_catalog_unicode_dedupe_and_start_menu_fallback(tmp_path):
    directory=tmp_path/'Microsoft/Windows/Start Menu/Programs';directory.mkdir(parents=True)
    (directory/'메모장.lnk').touch();(directory/'Discord.lnk').touch()
    def runner(args,**kwargs):
        assert args[:3]==['powershell.exe','-NoProfile','-NonInteractive'] and kwargs['timeout']==20
        return SimpleNamespace(stdout=json.dumps([{'Name':'메모장','AppID':'Microsoft.WindowsNotepad_8wekyb3d8bbwe!App'},{'Name':'계산기','AppID':'Calculator!App'}],ensure_ascii=False))
    result=collect_apps(runner,{'APPDATA':str(tmp_path)},force=True)
    assert len(result)==3
    assert sum(r['name']=='메모장' for r in result)==1
    assert any(r['name']=='Discord' and r['target'].endswith('.lnk') for r in result)
    assert any(r['target']=='app:Calculator!App' for r in result)

def test_app_catalog_falls_back_when_powershell_fails(tmp_path):
    directory=tmp_path/'Microsoft/Windows/Start Menu/Programs';directory.mkdir(parents=True);(directory/'Steam.lnk').touch()
    def failure(*a,**k):raise subprocess.TimeoutExpired('powershell',20)
    assert collect_apps(failure,{'PROGRAMDATA':str(tmp_path)},force=True)[0]['name']=='Steam'

@pytest.mark.parametrize('value',['','bad\ncommand','bad\0command'])
def test_invalid_app_ids_rejected(value):
    with pytest.raises(ValueError):app_shell_target(value)

def test_app_launch_shell_namespace():
    assert app_shell_target('Microsoft.WindowsCalculator_8wekyb3d8bbwe!App')=='shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App'

def test_appearance_and_layout_settings_survive_restart(tmp_path):
    store=Store(tmp_path);store.data.update(fontPreset='soft',widgetColor='#edf5fc',accentColor='#778899',widgetOpacity=.74,hideDesktopIcons=False)
    store.data['widgets']['memo']['color']='#253343';store.save();loaded=Store(tmp_path)
    assert loaded.data['widgets']['memo']['color']=='#253343' and loaded.data['fontPreset']=='soft'
    assert not loaded.data['hideDesktopIcons'] and loaded.data['widgetOpacity']==.74
    for preset in ['left','right','bottom']:
        for key,row in layout_for(preset).items():
            w,h=WIDGET_SIZES[key]
            assert 0<=row['x']<=1600-w*row['scale'] and 0<=row['y']<=900-h*row['scale']
