"""Restore the desktop icon list without opening the widget application."""
import os,sys
from pathlib import Path
from windows_desktop import DesktopHost,DesktopIcons,IS_WINDOWS

def restore():
    if not IS_WINDOWS:
        print('Windows only.');return 1
    directory=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Mars/HanroroDesktop'
    directory.mkdir(parents=True,exist_ok=True)
    DesktopIcons(DesktopHost(),directory).restore(force=True)
    print('Desktop icons restored.');return 0

if __name__=='__main__':sys.exit(restore())
