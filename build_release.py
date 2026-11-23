"""Build a Windows portable application and its distributable ZIP."""
from pathlib import Path
import importlib.metadata,json,shutil,subprocess,sys,zipfile

ROOT=Path(__file__).resolve().parent
PROJECTIONS=['winrt','winrt.windows.foundation','winrt.windows.foundation.collections','winrt.windows.media','winrt.windows.media.control','winrt.windows.storage.streams']

def command():
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','HanroroWidget','--version-file',str(ROOT/'windows_version_info.py'),'--icon',str(ROOT/'assets/icon.ico'),'--add-data',str(ROOT/'assets')+';assets','--add-data',str(ROOT/'qml')+';qml','--hidden-import','PySide6.QtQuickControls2','--hidden-import','PySide6.QtMultimedia','--hidden-import','PySide6.QtSvg']
    # WinRT 3.x uses several distribution packages in one namespace. Collect the
    # namespace, its dynamically imported projections and binary extensions.
    for module in PROJECTIONS+['numpy','psutil','pyaudiowpatch','pynvml']:args+=['--collect-all',module]
    args+=[str(ROOT/'main.py')];return args

def collect_licenses(destination):
    destination.mkdir(exist_ok=True)
    for package in ['numpy','psutil','PyAudioWPatch','nvidia-ml-py','PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','winrt-runtime','winrt-Windows.Foundation','winrt-Windows.Foundation.Collections','winrt-Windows.Media','winrt-Windows.Media.Control','winrt-Windows.Storage.Streams']:
        distribution=importlib.metadata.distribution(package)
        for file in distribution.files or []:
            if any(part.lower() in ('licenses','license','copying') or part.lower().startswith(('license.','copying.')) for part in file.parts):
                path=Path(distribution.locate_file(file))
                if path.is_file():
                    target=destination/package/str(file).replace('..','_');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)

def main():
    if sys.platform!='win32':raise SystemExit('Build this Windows app on a Windows PC.')
    if not (3,11)<=sys.version_info[:2]<(3,15):raise SystemExit('Use Python 3.11 through 3.14 (64-bit).')
    # Fail before a long build if media support is missing.
    import winrt.windows.media.control,winrt.windows.storage.streams
    subprocess.run(command(),cwd=ROOT,check=True)
    folder=ROOT/'dist/HanroroWidget'
    for name in ['THIRD_PARTY.md']:shutil.copy2(ROOT/name,folder/name)
    collect_licenses(folder/'licenses')
    (folder/'build-info.json').write_text(json.dumps({'python':sys.version,'packages':{name:importlib.metadata.version(name) for name in ['PySide6','pyinstaller','winrt-runtime','winrt-Windows.Media.Control']}},indent=2),encoding='utf-8')
    release=ROOT/'release';release.mkdir(exist_ok=True)
    archive=release/'HanroroWidget_Windows.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():z.write(path,Path(folder.name)/path.relative_to(folder))
    print('EXE:',folder/'HanroroWidget.exe');print('Share:',archive)

if __name__=='__main__':main()
