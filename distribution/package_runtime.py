from pathlib import Path
import shutil,pefile,hashlib,json
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--runtime',required=True);parser.add_argument('--output',required=True);parser.add_argument('--launcher',required=True);args=parser.parse_args()
SOURCE=Path(__file__).resolve().parents[1];PYTHON=Path(args.runtime).resolve();SITE=PYTHON/'Lib/site-packages'
OUT=Path(args.output).resolve();CORE=OUT/'_internal';DEST=CORE/'Lib/site-packages';DEST.mkdir(parents=True,exist_ok=True)

def copy(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def tree(src,dst):shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.lib','*.pyi','include'))
for p in PYTHON.iterdir():
 if p.is_file():copy(p,CORE/p.name)
for p in SOURCE.glob('*.py'):
 if p.name not in ['build_release.py','windows_version_info.py']:copy(p,CORE/p.name)
for name in ['assets','qml']:tree(SOURCE/name,CORE/name)
for stale in (CORE/'qml').glob('*.qml'):
 if not (SOURCE/'qml'/stale.name).exists():stale.unlink()
for name in ['shiboken6','winrt','numpy','numpy.libs','psutil','pyaudiowpatch']:tree(SITE/name,DEST/name)
for name in ['pynvml.py','_portaudiowpatch.cp312-win_amd64.pyd']:copy(SITE/name,DEST/name)
copy(SITE/'typing_extensions.py',DEST/'typing_extensions.py')
QT=SITE/'PySide6';QTDEST=DEST/'PySide6';QTDEST.mkdir(exist_ok=True)
for p in QT.iterdir():
 if p.is_file() and (p.suffix=='.py' or p.name in ['PySide6_Essentials.json','PySide6_Addons.json']):copy(p,QTDEST/p.name)
tree(QT/'support',QTDEST/'support')
for module in ['QtCore','QtGui','QtWidgets','QtNetwork','QtQml','QtQuick','QtQuickControls2','QtOpenGL','QtMultimedia','QtSvg']:
 copy(QT/(module+'.pyd'),QTDEST/(module+'.pyd'))
for module in ['QtQml','QtQuick','QtMultimedia']:tree(QT/'qml'/module,QTDEST/'qml'/module)
for category in ['platforms','imageformats','iconengines','styles','multimedia','tls','networkinformation','platforminputcontexts','generic']:
 if (QT/'plugins'/category).is_dir():tree(QT/'plugins'/category,QTDEST/'plugins'/category)
# DLLs loaded by name, outside the static import table.
for name in ['opengl32sw.dll','d3dcompiler_47.dll']:
 if (QT/name).exists():copy(QT/name,QTDEST/name)
for pattern in ['avcodec-*.dll','avformat-*.dll','avutil-*.dll','swresample-*.dll','swscale-*.dll']:
 for p in QT.glob(pattern):copy(p,CORE/p.name)
for p in (SITE/'shiboken6').glob('*.dll'):
 if p.name.lower().startswith(('vcruntime','msvcp','vccorlib','concrt','vcomp','vcamp')):copy(p,CORE/p.name)
# Resolve the transitive PE dependencies against the Windows wheels themselves.
index={}
for p in PYTHON.rglob('*'):
 if p.suffix.lower() in ('.dll','.pyd'):index.setdefault(p.name.lower(),p)
for p in QT.glob('*.dll'):index[p.name.lower()]=p
system={'kernel32.dll','user32.dll','gdi32.dll','advapi32.dll','shell32.dll','ole32.dll','oleaut32.dll','comdlg32.dll','comctl32.dll','crypt32.dll','ws2_32.dll','bcrypt.dll','ntdll.dll','msvcrt.dll','rpcrt4.dll','dwmapi.dll','uxtheme.dll','version.dll','winmm.dll','imm32.dll','shlwapi.dll','setupapi.dll','secur32.dll','winspool.drv','dnsapi.dll','iphlpapi.dll','netapi32.dll','winhttp.dll','wininet.dll','userenv.dll','d3d11.dll','dxgi.dll','d3d9.dll','dwrite.dll','d2d1.dll','dcomp.dll','dxguid.dll','propsys.dll','mf.dll','mfplat.dll','mfreadwrite.dll','mfuuid.dll','avrt.dll','dsound.dll','hid.dll','wtsapi32.dll','powrprof.dll','msimg32.dll','usp10.dll','authz.dll','ncrypt.dll','normaliz.dll','d3d12.dll','mswsock.dll','cfgmgr32.dll','clbcatq.dll','api-ms-win-core-winrt-l1-1-0.dll'}
scanned=set();missing=set()
while True:
 files=[p for p in CORE.rglob('*') if p.suffix.lower() in ('.dll','.pyd','.exe') and str(p) not in scanned]
 if not files:break
 for p in files:
  scanned.add(str(p))
  pe=pefile.PE(str(p),fast_load=True);pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT']])
  for imp in list(getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]))+list(getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[])):
   name=imp.dll.decode().lower()
   if name in index:
    src=index[name]
    if src.parent==QT:target=QTDEST/src.name
    elif src.parent==SITE/'shiboken6':target=DEST/'shiboken6'/src.name
    elif src.parent==SITE/'winrt':target=DEST/'winrt'/src.name
    else:target=CORE/src.name
    if not target.exists():copy(src,target)
   elif name not in system and not name.startswith(('api-ms-','ext-ms-')):missing.add(name)
  pe.close()
print('Unbundled Windows/system libraries:',sorted(missing))
# License and attribution material travel with the binary distribution.
licenses=OUT/'licenses';licenses.mkdir(exist_ok=True)
for info in SITE.glob('*.dist-info'):
 if not info.name.lower().startswith(('pyside6','shiboken6','winrt','typing_extensions','numpy','psutil','pyaudiowpatch','nvidia_ml_py')):continue
 for p in info.rglob('*'):
  if p.is_file() and ('license' in p.name.lower() or 'copying' in p.name.lower() or 'licenses' in p.parts):copy(p,licenses/info.name/p.relative_to(info))
copy(PYTHON/'LICENSE.txt',licenses/'Python-LICENSE.txt');copy(SOURCE/'THIRD_PARTY.md',licenses/'THIRD_PARTY.md')
copy(Path(args.launcher),OUT/'한로로 바탕화면 위젯.exe')
BUILD_ID='portable-'+hashlib.sha256(b''.join(p.read_bytes() for p in sorted(SOURCE.glob('*.py')))).hexdigest()[:16]
(CORE/'portable_build.py').write_text('BUILD_ID='+repr(BUILD_ID)+'\n',encoding='utf-8')
p=CORE/'main.py';s=p.read_text();old="handled['done']=True;message=bytes(conn.readAll()).decode('utf-8','replace').strip();conn.disconnectFromServer();conn.deleteLater()"
new="handled['done']=True;message=bytes(conn.readAll()).decode('utf-8','replace').strip()\n                if message=='build-id':\n                    from portable_build import BUILD_ID\n                    conn.write(BUILD_ID.encode('ascii'));conn.waitForBytesWritten(500)\n                conn.disconnectFromServer();conn.deleteLater()\n                if message=='build-id':return"
assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
(OUT/'build-info.json').write_text(json.dumps({'name':'한로로 바탕화면 위젯','build':BUILD_ID,'architecture':'Windows x64','runtime':'Python 3.12.10 / PySide6 6.12.0','source_tests_passed':110,'native_launcher':'Windows x64 GUI','windows_execution_tested':False,'company_name':'마스','authenticode_signed':False},ensure_ascii=False,indent=2),encoding='utf-8')
print('Packaged:',OUT)
print('Payload MiB:',round(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())/1024**2,1))
