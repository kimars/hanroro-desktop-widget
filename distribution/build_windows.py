"""Reproducible per-user runtime and installer build on Windows CI."""
from pathlib import Path
import hashlib,subprocess,sys,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build-ci';RUNTIME=WORK/'python';PAYLOAD=WORK/'HanroroWidget'
if sys.platform!='win32':raise SystemExit('Windows build required')
required=[ROOT/'assets/loop.mp4',*[ROOT/'assets/photos'/('photo'+str(i)+'.jpg') for i in [1,2,3,4,6]]]
if not all(p.is_file() for p in required):raise SystemExit('Bundled photo/video assets are pending public distribution approval.')
WORK.mkdir(exist_ok=True);RUNTIME.mkdir(exist_ok=True)
archive=WORK/'python-embed.zip'
urllib.request.urlretrieve('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',archive)
if hashlib.sha256(archive.read_bytes()).hexdigest()!='4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3':raise ValueError('Python runtime checksum mismatch')
with zipfile.ZipFile(archive) as z:z.extractall(RUNTIME)
(RUNTIME/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\nimport site\n')
subprocess.run([sys.executable,'-m','pip','install','--only-binary=:all:','--target',str(RUNTIME/'Lib/site-packages'),'-r',str(ROOT/'requirements.txt')],check=True)
launcher=ROOT/'distribution/launcher'
subprocess.run(['rc','/nologo','/fo',str(WORK/'launcher.res'),'launcher.rc'],cwd=launcher,check=True)
subprocess.run(['cl','/nologo','/utf-8','/O2','launcher.c',str(WORK/'launcher.res'),'user32.lib','/Fe:'+str(WORK/'HanroroWidget.exe'),'/link','/SUBSYSTEM:WINDOWS'],cwd=launcher,check=True)
subprocess.run(['cl','/nologo','/utf-8','/O2','close_widget.c','user32.lib','advapi32.lib','shell32.lib','ole32.lib','uuid.lib','bcrypt.lib','/Fe:CloseHanroro.exe','/link','/SUBSYSTEM:WINDOWS'],cwd=ROOT/'distribution/installer',check=True)
subprocess.run([sys.executable,str(ROOT/'distribution/package_runtime.py'),'--runtime',str(RUNTIME),'--output',str(PAYLOAD),'--launcher',str(WORK/'HanroroWidget.exe')],check=True)
output=ROOT/'release/HanroroWidget_Setup_x64.exe';output.parent.mkdir(exist_ok=True)
subprocess.run([sys.executable,str(ROOT/'distribution/installer/build_installer.py'),'--payload',str(PAYLOAD),'--output',str(output),'--work',str(WORK/'nsis'),'--makensis',r'C:\Program Files (x86)\NSIS\makensis.exe'],check=True)
subprocess.run([sys.executable,str(ROOT/'distribution/release/publish.py'),'--installer',str(output)],check=True)
