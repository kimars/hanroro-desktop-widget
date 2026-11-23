from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_memo_composer_uses_custom_actions_not_native_buttons():
    qml = (ROOT / "qml" / "MemoCard.qml").read_text(encoding="utf-8")
    assert 'objectName: "memoEditButton"' in qml
    assert 'objectName: "memoEditor"' in qml
    assert 'Accessible.name: "취소"' in qml
    assert 'Accessible.name: "저장"' in qml
    assert re.search(r"(?m)^\s*Button\s*\{", qml) is None
    assert 'text: "취소"' in qml and 'text: "저장"' in qml


def test_task_tabs_are_rectangular_and_touch_the_paper_edge():
    qml = (ROOT / "qml" / "MemoCard.qml").read_text(encoding="utf-8")
    assert "width: 292" in qml
    assert "x: 291" in qml
    tabs = qml.split("// Rectangular paper tabs", 1)[1]
    assert "radius:" not in tabs
    assert "property int tabWidth:" in qml


def test_clock_wordmark_is_removed():
    qml = (ROOT / "qml" / "Scene.qml").read_text(encoding="utf-8")
    assert "HANRORO" not in qml
    assert "한로로" not in qml
    assert 'scene.pad(now.getHours())' in qml
