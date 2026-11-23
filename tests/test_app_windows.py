import sys
import pytest
import app_windows


def test_non_windows_window_toggle_is_explicit(monkeypatch):
    monkeypatch.setattr(app_windows.sys,'platform','linux')
    with pytest.raises(OSError):
        app_windows.toggle_or_launch('app:Example.App!App')


def test_shortcut_resolution_cache(monkeypatch,tmp_path):
    shortcut=tmp_path/'app.lnk';shortcut.write_text('shortcut')
    calls=[]
    class Result:
        stdout='C:\\Program Files\\Example\\example.exe'
    def fake_run(*args,**kwargs):
        calls.append(args[0]);return Result()
    monkeypatch.setattr(app_windows.subprocess,'run',fake_run)
    monkeypatch.setattr(app_windows.sys,'platform','win32')
    first=app_windows._resolve_shortcut(str(shortcut))
    second=app_windows._resolve_shortcut(str(shortcut))
    assert first==second==Result.stdout
    assert len(calls)==1


def test_desktop_window_id_and_resolved_executable_are_matched():
    paths={r'c:\program files\browser\browser.exe'}
    assert app_windows.identity_matches('Browser.App',set(),'Browser.App','','')
    assert app_windows.identity_matches('Store.App!Main',set(),'','Store.App!Main','')
    assert app_windows.identity_matches('Old.AppId',paths,'','',r'C:\Program Files\Browser\Browser.exe')
    assert not app_windows.identity_matches('Browser.App',paths,'Other.App','',r'C:\Other\browser.exe')


def test_catalog_links_backfill_saved_app_ids(monkeypatch,tmp_path):
    link=tmp_path/'Browser.lnk';link.touch()
    monkeypatch.setitem(app_windows._shortcut_cache,str(link.resolve()),r'C:\Browser\browser.exe')
    app_windows.register_app_shortcuts([{'target':'app:Browser.App','path':str(link)}])
    assert app_windows.target_executables('app:Browser.App')=={r'c:\browser\browser.exe'}


class NativeFunction:
    def __init__(self,fn):self.fn=fn
    def __call__(self,*args):return self.fn(*args)


def test_existing_app_is_activated_then_minimized_without_launch(monkeypatch):
    from types import SimpleNamespace as NS
    current=[99];iconic=[False];calls=[];launched=[]
    api=NS(GetForegroundWindow=NativeFunction(lambda:current[0]),GetAncestor=NativeFunction(lambda hwnd,flag:hwnd),IsIconic=NativeFunction(lambda hwnd:iconic[0]),ShowWindow=NativeFunction(lambda hwnd,action:calls.append((hwnd,action))),BringWindowToTop=NativeFunction(lambda hwnd:True),SetForegroundWindow=NativeFunction(lambda hwnd:current.__setitem__(0,hwnd) or True))
    monkeypatch.setattr(app_windows.sys,'platform','win32');monkeypatch.setattr(app_windows.ctypes,'WinDLL',lambda *a,**k:api,raising=False);monkeypatch.setattr(app_windows,'_matching_windows',lambda target:[100]);monkeypatch.setattr(app_windows.os,'startfile',lambda target:launched.append(target),raising=False)
    assert app_windows.toggle_or_launch('app:Browser.App')=='activated'
    assert current[0]==100 and not launched
    assert app_windows.toggle_or_launch('app:Browser.App')=='minimized'
    assert calls[-1]==(100,app_windows.SW_MINIMIZE) and not launched
    iconic[0]=True
    assert app_windows.toggle_or_launch('app:Browser.App')=='activated'
    assert calls[-1]==(100,app_windows.SW_RESTORE) and not launched


def test_rapid_repeated_click_does_not_spawn_multiple_launches(monkeypatch):
    launched=[];app_windows._launch_times.clear()
    monkeypatch.setattr(app_windows.sys,'platform','win32');monkeypatch.setattr(app_windows,'_matching_windows',lambda target:[]);monkeypatch.setattr(app_windows.os,'startfile',lambda target:launched.append(target),raising=False)
    assert app_windows.toggle_or_launch('app:Starting.App')=='launched'
    assert app_windows.toggle_or_launch('app:Starting.App')=='starting'
    assert launched==['shell:AppsFolder\\Starting.App']


def test_squirrel_launcher_matches_child_inside_its_installation(monkeypatch):
    path=r'c:\users\user\appdata\local\discord\update.exe'
    monkeypatch.setitem(app_windows._launcher_children,path,'Discord.exe')
    assert app_windows.identity_matches('',{path},'','',r'C:\Users\user\AppData\Local\Discord\app-1.0.0\Discord.exe')
    assert not app_windows.identity_matches('',{path},'','',r'C:\Other\Discord.exe')


def test_shortcut_json_preserves_launcher_arguments_and_unicode(monkeypatch,tmp_path):
    import json
    link=tmp_path/'디스코드.lnk';link.touch()
    from types import SimpleNamespace
    output='\ufeff'+json.dumps({'path':r'C:\Users\홍길동\Discord\Update.exe','arguments':'--processStart "Discord.exe"'},ensure_ascii=False)
    monkeypatch.setattr(app_windows.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=output))
    assert app_windows._resolve_shortcut(str(link))==r'C:\Users\홍길동\Discord\Update.exe'
    path=r'c:\users\홍길동\discord\update.exe'
    assert app_windows._launcher_children[path]=='Discord.exe'
