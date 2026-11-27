"""Check the shipped application with legacy dock settings; do not alter Explorer."""
import json,sys,tempfile,os
from pathlib import Path
from types import SimpleNamespace
core=Path(sys.argv[1]).resolve();sys.path.insert(0,str(core));os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtWidgets import QApplication,QCheckBox
from main import Program
app=QApplication([])
with tempfile.TemporaryDirectory() as directory:
    data={'version':4,'macDock':True,'hideTaskbar':True,'winKeySearch':True,'dockAutoHide':True,'shellRevision':3,'memo':'유지'}
    Path(directory,'settings.json').write_text(json.dumps(data),encoding='utf-8')
    program=Program(app,SimpleNamespace(data_dir=directory,render=None,smoke_run=False,preview=True))
    try:
        app.processEvents()
        assert not any(program.store.data[k] for k in ('macDock','hideTaskbar','winKeySearch','dockAutoHide'))
        assert program.store.data['memo']=='유지'
        assert 'desktop_shell' not in sys.modules
        assert not (core/'HanroroShell.exe').exists()
        assert not any(w.windowTitle()=='한로로 독' for w in app.topLevelWidgets())
        card=program.preview.rootObject().findChild(__import__('PySide6.QtCore',fromlist=['QObject']).QObject,'launcherCard');assert card and card.isVisible()
        print('Removed dock: legacy settings disabled, no shell process/window/hooks bundled, original launcher visible.',flush=True)
    finally:program.shutdown()
