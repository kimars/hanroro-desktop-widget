import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import font_config as fonts

@pytest.fixture(autouse=True)
def preserve_registry():
    old=dict(fonts._loaded)
    yield
    fonts._loaded.clear();fonts._loaded.update(old)


def test_windows_defaults_to_compatible_font_database():
    env={};fonts.configure_windows_fonts(env,'win32')
    assert env['QT_QPA_PLATFORM']=='windows:fontengine=gdi'
    env={'QT_QPA_PLATFORM':'offscreen'};fonts.configure_windows_fonts(env,'win32')
    assert env['QT_QPA_PLATFORM']=='offscreen'
    env={};fonts.configure_windows_fonts(env,'linux');assert env=={}


def test_only_small_bundled_ttf_fonts_are_registered_without_global_scan(tmp_path):
    for name in ['NanumSquareRoundR.ttf','NanumSquareRoundB.ttf','Jua-Regular.ttf','NotoSansKR-Regular.otf','unknown.ttf']:(tmp_path/name).touch()
    loaded=[]
    class DB:
        @staticmethod
        def families():raise AssertionError('Global font enumeration must not run')
        @staticmethod
        def addApplicationFont(path):loaded.append(Path(path).name);return len(loaded)
        @staticmethod
        def applicationFontFamilies(ident):return ['NanumSquareRound' if ident<3 else 'Jua']
    result=fonts.register_fonts(tmp_path,DB,marker=tmp_path/'font-loading.json')
    assert loaded==['NanumSquareRoundR.ttf','NanumSquareRoundB.ttf','Jua-Regular.ttf']
    assert result=={'round':'NanumSquareRound','soft':'Jua'}
    assert fonts.ui_family('round')=='NanumSquareRound' and not (tmp_path/'font-loading.json').exists()


def test_safe_mode_never_calls_font_registration(tmp_path):
    class DB:
        @staticmethod
        def addApplicationFont(*_):raise AssertionError('Safe mode cannot load custom fonts')
    assert fonts.register_fonts(tmp_path,DB,skip=True)=={}
    assert fonts.ui_family('round') in ('Malgun Gothic','sans-serif')


def test_interrupted_font_loading_is_bypassed_on_next_start(tmp_path):
    marker=tmp_path/'font-loading.json';marker.write_text('interrupted.ttf')
    class DB:
        @staticmethod
        def addApplicationFont(*_):raise AssertionError('Interrupted registration must be skipped')
    assert fonts.register_fonts(tmp_path,DB,marker=marker)=={}
    assert marker.exists()
