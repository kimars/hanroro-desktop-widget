import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from native_jobs import NativeJobs


def test_blocked_native_job_times_out_while_ui_keeps_running(tmp_path):
    app=QApplication.instance() or QApplication([])
    script=tmp_path/'blocked.py';script.write_text('import time\ntime.sleep(20)\n')
    jobs=NativeJobs(tmp_path/'jobs',script,timeout_ms=220);answers=[];ticks=[]
    jobs.completed.connect(lambda *args:answers.append(args))
    heartbeat=QTimer();heartbeat.setInterval(25);heartbeat.timeout.connect(lambda:ticks.append(1));heartbeat.start()
    jobs.start({'operation':'apply'});assert jobs.busy
    assert not jobs.start({'operation':'apply'})
    QTest.qWait(500);heartbeat.stop()
    assert len(ticks)>=3 and len(answers)==1 and not answers[0][1]
    assert '시간 초과' in answers[0][2] and not jobs.busy
    assert not list((tmp_path/'jobs').glob('*.json'))


def test_native_job_success_and_shutdown_cancel(tmp_path):
    app=QApplication.instance() or QApplication([])
    script=tmp_path/'success.py';script.write_text("import sys,json\nfrom pathlib import Path\np=Path(sys.argv[2]);p.with_suffix('.result.json').write_text(json.dumps({'ok':True,'detail':''}))\n")
    jobs=NativeJobs(tmp_path/'jobs',script);answers=[];jobs.completed.connect(lambda *args:answers.append(args))
    jobs.start({'operation':'restore'});QTest.qWait(300)
    assert len(answers)==1 and answers[0][1] and not jobs.busy
    script.write_text('import time\ntime.sleep(20)\n')
    jobs.start({'operation':'apply'});QTest.qWait(30);jobs.cancel();QTest.qWait(30)
    assert not jobs.busy and answers[-1][2]=='cancelled'


def test_native_process_missing_executable_is_reported(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    jobs=NativeJobs(tmp_path/'jobs',tmp_path/'entry.py');answers=[];jobs.completed.connect(lambda *args:answers.append(args))
    monkeypatch.setattr(sys,'executable',str(tmp_path/'does-not-exist'))
    jobs.start({'operation':'apply'});QTest.qWait(100)
    assert len(answers)==1 and not answers[0][1] and not jobs.busy
