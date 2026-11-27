import json,sys,time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from desktop_native import matching_windows
from taskbar_catalog import dock_rows
from shell_service import ShellService

def test_shortcuts_match_executable_and_keep_every_window():
    windows=[{'target':r'c:\app\edit.exe','path':r'C:\App\EDIT.exe','hwnd':i} for i in (1,2)]
    pinned={'target':'app:editor.id','path':r'C:\menu\Editor.lnk','executables':[r'c:\app\edit.exe']}
    assert len(matching_windows(pinned,windows))==2
    assert dock_rows([pinned],windows)==[pinned]
    assert len(matching_windows({'target':'app:discord','child_exe':'Discord.exe'},[{'path':r'c:\x\discord.exe'}]))==1

def test_appid_does_not_merge_different_browser_profiles():
    rows=[{'app_id':'browser.profile1','path':'browser.exe'},{'app_id':'browser.profile2','path':'browser.exe'}]
    assert matching_windows({'target':'app:browser.profile1','exe':'browser.exe'},rows)==rows[:1]

def test_slow_worker_does_not_block_qt_and_closes(tmp_path,qt_application):
    script=tmp_path/'worker.py';script.write_text("import sys,json,time\nfor line in sys.stdin:\n r=json.loads(line);time.sleep(.15);print(json.dumps({'id':r['id'],'data':{'rows':[]}}),flush=True)\n")
    service=ShellService(script,enabled=True);received=[];ticks=[];service.result.connect(lambda *x:received.append(x));timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
    try:
        service.request('windows');until=time.monotonic()+3
        while not received and time.monotonic()<until:QTest.qWait(10);time.sleep(.001)
        assert received and len(ticks)>10
        assert service.process is not None
    finally:timer.stop();service.close()
    assert service.process is None

def test_worker_failure_reports_and_can_restart(tmp_path,qt_application):
    script=tmp_path/'worker.py';script.write_text('import sys\nsys.exit(3)\n');service=ShellService(script,enabled=True);errors=[];service.error.connect(lambda *x:errors.append(x))
    try:
        service.request('windows');until=time.monotonic()+3
        while not errors and time.monotonic()<until:QTest.qWait(10);time.sleep(.001)
        assert errors and service.pending is None
        script.write_text("import sys,json\nfor line in sys.stdin:\n r=json.loads(line);print(json.dumps({'id':r['id'],'data':{'rows':[]}}),flush=True)\n")
        results=[];service.result.connect(lambda *x:results.append(x));service.request('windows');until=time.monotonic()+3
        while not results and time.monotonic()<until:QTest.qWait(10);time.sleep(.001)
        assert results
    finally:service.close()
