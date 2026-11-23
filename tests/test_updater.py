import hashlib,io,json,time
from pathlib import Path
import pytest
import update_worker as worker
from release_info import VERSION,INSTALLER_ASSET
from updater import Updater,install_update


def release(blob=b'MZfixture',version='v9.1.0'):
    return {'tag_name':version,'draft':False,'prerelease':False,'body':'새 기능','assets':[{'name':INSTALLER_ASSET,'state':'uploaded','size':len(blob),'digest':'sha256:'+hashlib.sha256(blob).hexdigest(),'browser_download_url':'https://github.com/kimars/hanroro-desktop-widget/releases/download/'+version+'/'+INSTALLER_ASSET}]}


def test_release_versions_and_trusted_sources(monkeypatch):
    data=release();monkeypatch.setattr(worker,'limited_read',lambda *args:json.dumps(data).encode())
    assert worker.release_info('kimars/hanroro-desktop-widget',VERSION)['version']=='9.1.0'
    data['tag_name']='v'+VERSION;assert worker.release_info('kimars/hanroro-desktop-widget',VERSION)['status']=='current'
    assert worker.version_tuple('1.10.0')>worker.version_tuple('1.9.9')
    data['tag_name']='v9.0.0';data['assets'][0]['browser_download_url']='https://github.com/other/untrusted/releases/download/v9.0.0/app.exe'
    with pytest.raises(ValueError):worker.release_info('kimars/hanroro-desktop-widget',VERSION)
    for url in ['http://github.com/x','https://evil.example/x','https://user:password@github.com/x','https://github.com:81/x']:
        with pytest.raises(ValueError):worker.trusted_url(url)
    with pytest.raises(ValueError):worker.version_tuple('1.2.3-beta')


def test_download_atomicity_and_hash_mismatch(tmp_path,monkeypatch):
    blob=b'MZ'+b'a'*100000;meta=release(blob);monkeypatch.setattr(worker,'limited_read',lambda *args:json.dumps(meta).encode());monkeypatch.setattr(worker,'open_url',lambda *args:io.BytesIO(blob));messages=[]
    result=worker.download('kimars/hanroro-desktop-widget',VERSION,tmp_path,messages.append)
    assert Path(result['path']).read_bytes()==blob and not list(tmp_path.glob('*.part'))
    Path(result['path']).unlink();monkeypatch.setattr(worker,'open_url',lambda *args:io.BytesIO(b'MZ'+b'b'*100000))
    with pytest.raises(ValueError):worker.download('kimars/hanroro-desktop-widget',VERSION,tmp_path,messages.append)
    assert not list(tmp_path.glob('*.exe')) and not list(tmp_path.glob('*.part'))
    monkeypatch.setattr(worker,'open_url',lambda *args:io.BytesIO(blob[:-10]))
    with pytest.raises(ValueError):worker.download('kimars/hanroro-desktop-widget',VERSION,tmp_path,messages.append)
    assert not list(tmp_path.glob('*.part'))


def test_sidecar_fallback(monkeypatch):
    blob=b'MZfixture';data=release(blob);data['assets'][0]['digest']=None
    monkeypatch.setattr(worker,'limited_read',lambda *args:json.dumps(data).encode())
    with pytest.raises(ValueError):worker.release_info('kimars/hanroro-desktop-widget',VERSION)
    data['assets'].append({'name':INSTALLER_ASSET+'.sha256','browser_download_url':data['assets'][0]['browser_download_url']+'.sha256'})
    monkeypatch.setattr(worker,'limited_read',lambda url,limit:json.dumps(data).encode() if 'api.github.com' in url else (hashlib.sha256(blob).hexdigest()+'  '+INSTALLER_ASSET).encode())
    assert worker.release_info('kimars/hanroro-desktop-widget',VERSION)['sha256']==hashlib.sha256(blob).hexdigest()


def test_installer_handoff_rechecks_download(tmp_path,monkeypatch):
    import os
    path=tmp_path/'app.exe';path.write_bytes(b'MZfixture');request=tmp_path/'install-request.json';request.write_text(json.dumps({'path':str(path),'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}));calls=[]
    monkeypatch.setattr(os,'startfile',lambda *args:calls.append(args),raising=False)
    assert install_update(request)==0 and calls==[(str(path),'open','/S /AUTOUPDATE')]
    path.write_bytes(b'MZmodified');assert install_update(request)==1 and len(calls)==1
    assert '검증' in json.loads(request.with_suffix('.result.json').read_text())['error']


def test_update_process_is_nonblocking_and_cancelable(tmp_path):
    from PySide6.QtTest import QTest
    entry=tmp_path/'worker.py';entry.write_text('import json,sys,time\nr=json.loads(sys.stdin.readline())\nprint(json.dumps({"status":"available","version":"9.0.0"}),flush=True)\ntime.sleep(10)\n')
    updater=Updater(tmp_path,entry);updater.check()
    for _ in range(50):
        QTest.qWait(10);time.sleep(.002)
        if updater.data['status']=='available':break
    assert updater.data['status']=='available' and updater.process
    updater.cancel();assert updater.process is None and updater.data['status']=='idle';updater.close()


def test_update_settings_and_restart_switch(tmp_path):
    from PySide6.QtWidgets import QApplication
    from backend import Bridge
    from state import Store
    from panels import Settings
    b=Bridge(Store(tmp_path),Path(__file__).resolve().parents[1]/'assets');p=Settings(b,QApplication.instance())
    try:
        p.show_section(9);assert p.stack.currentIndex()==9 and p.update_check.isEnabled() and not p.update_apply.isEnabled()
        b.updates.publish({'status':'available','version':'9.0.0','notes':'변경 사항'});assert p.update_apply.isEnabled() and p.update_notes.toPlainText()=='변경 사항'
        source=(Path(__file__).resolve().parents[1]/'distribution/installer/build_installer.py').read_text()
        assert '/AUTOUPDATE' in source and 'Function .onInstSuccess' in source
    finally:
        b.updates.close();b.media.close();b.telemetry_link.close();b.features_controller.close();b.writer.close();p.close();p.deleteLater()
