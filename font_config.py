"""Use known font names; never enumerate the Windows font database on startup."""
import logging,os,sys
from pathlib import Path

_loaded={}

def configure_windows_fonts(environment=None,platform=None):
    env=os.environ if environment is None else environment
    platform=sys.platform if platform is None else platform
    if platform=='win32' and not env.get('QT_QPA_PLATFORM'):
        # Qt 6.8+ supports the legacy GDI font database explicitly.
        env['QT_QPA_PLATFORM']='windows:fontengine=gdi'

def ui_family(preset='round'):
    fallback='Malgun Gothic' if sys.platform=='win32' else 'sans-serif'
    return _loaded.get(preset,fallback)

def register_fonts(directory,database,skip=False,marker=None):
    _loaded.clear()
    if skip:
        logging.info('Fonts: custom loading skipped; using system font')
        return {}
    marker=Path(marker) if marker else None
    if marker and marker.exists():
        logging.warning('Fonts: interrupted prior font load; skipping custom fonts. marker=%s',marker)
        return {}
    # Only the three small TTFs are needed. Old Noto CJK OTFs may still exist
    # after an overwrite update, so an explicit allowlist is essential.
    fonts=[('NanumSquareRoundR.ttf','round'),('NanumSquareRoundB.ttf','round'),('Jua-Regular.ttf','soft')]
    try:
        for name,preset in fonts:
            path=Path(directory)/name
            if not path.is_file():continue
            if marker:marker.write_text(name,encoding='utf-8')
            logging.info('Fonts: registering %s (%s bytes)',name,path.stat().st_size)
            ident=database.addApplicationFont(str(path))
            if ident>=0:
                families=database.applicationFontFamilies(ident)
                if families and preset not in _loaded:_loaded[preset]=families[0]
                logging.info('Fonts: registered %s id=%s family=%s',name,ident,list(families))
            else:logging.warning('Fonts: rejected %s; using system fallback',name)
            if marker:marker.unlink(missing_ok=True)
    except Exception:
        logging.exception('Fonts: registration failed; keeping system fallback')
        if marker:marker.unlink(missing_ok=True)
    return dict(_loaded)


def settings_font(platform=None):
    """Use a real system face for small QWidget labels; avoid synthetic custom bold."""
    from PySide6.QtGui import QFont
    platform=sys.platform if platform is None else platform
    font=QFont('Malgun Gothic' if platform=='win32' else ui_family('round'),10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font
