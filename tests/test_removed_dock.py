from pathlib import Path
from state import validate,Store
import json

def test_old_shell_settings_are_disabled_without_losing_user_data(tmp_path):
    data={'version':4,'shellRevision':3,'macDock':True,'hideTaskbar':True,'winKeySearch':True,'dockAutoHide':True,'memo':'유지할 메모','links':[{'title':'내 폴더','target':'special:documents','glyph':'folder'}]}
    (tmp_path/'settings.json').write_text(json.dumps(data))
    store=Store(tmp_path)
    assert not any(store.data[k] for k in ('macDock','hideTaskbar','winKeySearch','dockAutoHide'))
    assert store.data['memo']=='유지할 메모' and store.data['links'][0]['title']=='내 폴더'

def test_runtime_does_not_load_shell_or_capture_windows_key():
    root=Path(__file__).resolve().parents[1]
    main=(root/'main.py').read_text();panels=(root/'panels.py').read_text();scene=(root/'qml/Scene.qml').read_text()
    assert 'DesktopShell' not in main and '--shell-worker' not in main
    assert "card('독 · 검색')" not in panels
    assert 's.macDock' not in next(l for l in scene.splitlines() if 'LauncherCard {' in l)
