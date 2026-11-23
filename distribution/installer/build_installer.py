"""Build a single per-user NSIS setup executable from the tested portable folder."""
import argparse,hashlib,json,os,subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from release_info import VERSION
ROOT=Path(__file__).resolve().parent
APP='한로로 바탕화면 위젯';EXE=APP+'.exe'
REG=r'Software\Mars\HanroroWidgetInstaller'
UNINSTALL=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\MarsHanroroWidget'

def nsis(value):return str(value).replace('$','$$').replace('"','$\\"')

def build_script(payload,output,work,target='amd64-unicode'):
    payload=Path(payload).resolve();output=Path(output).resolve();work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
    required=[payload/EXE,payload/'_internal/main.py',payload/'_internal/pythonw.exe',ROOT/'CloseHanroro.exe']
    if not all(p.is_file() for p in required):raise ValueError('Portable application or shutdown helper is missing.')
    files=sorted(p for p in payload.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'))
    manifest={'name':APP,'version':VERSION,'installer_target':target,'publisher':'마스','authenticode_signed':False,'data_retained_on_uninstall':True,'files':[{'path':p.relative_to(payload).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files]}
    marker=work/'installation-manifest.json';marker.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Every removal is enumerated: do not recursively delete an arbitrary install directory.
    dirs={Path('.')}
    for p in files:
        dirs.update(p.relative_to(payload).parents)
    install=[];last=None
    for p in files:
        rel=p.relative_to(payload);parent=str(rel.parent).replace('/','\\')
        if parent!=last:install.append('SetOutPath "$INSTDIR'+('' if parent=='.' else '\\'+nsis(parent))+'"');last=parent
        install.append(f'File "/oname={nsis(rel.name)}" "{nsis(p)}"')
    remove=[f'Delete "$INSTDIR\\{nsis(str(p.relative_to(payload)).replace(chr(47),chr(92)))}"' for p in files]
    for d in sorted(dirs,key=lambda p:len(p.parts),reverse=True):
        rel=str(d).replace('/','\\');prefix='$INSTDIR'+('' if rel=='.' else '\\'+nsis(rel))
        remove.extend([f'Delete "{prefix}\\__pycache__\\*.pyc"',f'RMDir "{prefix}\\__pycache__"',f'RMDir "{prefix}"'])
    script=f'''Unicode true
Target {target}
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "StrFunc.nsh"
!include "FileFunc.nsh"
Var AutoUpdate
${{UnStrStr}}
Name "{APP}"
OutFile "{nsis(output)}"
InstallDir "$LOCALAPPDATA\\Programs\\HanroroWidget"
InstallDirRegKey HKCU "{REG}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID zlib
CRCCheck on
ShowInstDetails nevershow
ShowUninstDetails nevershow
BrandingText "마스"
Icon "{nsis(payload/'_internal/assets/icon.ico')}"
UninstallIcon "{nsis(payload/'_internal/assets/icon.ico')}"
VIProductVersion "{VERSION}.0"
VIAddVersionKey /LANG=1042 "ProductName" "{APP} 설치"
VIAddVersionKey /LANG=1042 "CompanyName" "마스"
VIAddVersionKey /LANG=1042 "FileDescription" "{APP} 설치 프로그램"
VIAddVersionKey /LANG=1042 "FileVersion" "{VERSION}.0"
VIAddVersionKey /LANG=1042 "LegalCopyright" "Copyright 마스"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "{APP} 설치"
!define MUI_WELCOMEPAGE_TEXT "현재 사용자 계정에 설치합니다.$\\r$\\n기존 메모와 설정은 유지됩니다."
!define MUI_FINISHPAGE_TITLE "설치 완료"
!define MUI_FINISHPAGE_RUN "$INSTDIR\\{EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "{APP} 실행"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Korean"
Function .onInit
  ${{GetParameters}} $0
  ClearErrors
  ${{GetOptions}} $0 "/AUTOUPDATE" $1
  ${{IfNot}} ${{Errors}}
    StrCpy $AutoUpdate 1
  ${{EndIf}}
  SetShellVarContext current
  SetRegView 64
  ${{IfNot}} ${{RunningX64}}
    MessageBox MB_OK|MB_ICONSTOP "Windows 64비트 환경이 필요합니다." /SD IDOK
    Abort
  ${{EndIf}}
  ${{IfNot}} ${{AtLeastWin10}}
    MessageBox MB_OK|MB_ICONSTOP "Windows 10 이상이 필요합니다." /SD IDOK
    Abort
  ${{EndIf}}
  System::Call 'kernel32::CreateMutexW(p 0, i 0, w "Local\\MarsHanroroWidgetSetup") p .r0 ?e'
  Pop $1
  ${{If}} $1 = 183
    MessageBox MB_OK|MB_ICONEXCLAMATION "다른 설치 또는 제거 작업을 먼저 마쳐주세요." /SD IDOK
    Abort
  ${{EndIf}}
FunctionEnd
Function un.onInit
  System::Call 'kernel32::CreateMutexW(p 0, i 0, w "Local\\MarsHanroroWidgetSetup") p .r0 ?e'
  Pop $1
  ${{If}} $1 = 183
    MessageBox MB_OK|MB_ICONEXCLAMATION "다른 설치 또는 제거 작업을 먼저 마쳐주세요." /SD IDOK
    Abort
  ${{EndIf}}
  SetShellVarContext current
  SetRegView 64
  IfFileExists "$INSTDIR\\installation-manifest.json" un_init_ok 0
    MessageBox MB_OK|MB_ICONSTOP "설치 정보를 찾을 수 없습니다." /SD IDOK
    Abort
  un_init_ok:
FunctionEnd
Section "프로그램" SEC_APP
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=CloseHanroro.exe "{nsis(ROOT/'CloseHanroro.exe')}"
  ClearErrors
  ExecWait '$\\"$PLUGINSDIR\\CloseHanroro.exe$\\"' $0
  ${{If}} ${{Errors}}
    MessageBox MB_OK|MB_ICONSTOP "앱 종료 도구를 실행하지 못했습니다. 설치 또는 제거를 중단합니다." /SD IDOK
    Abort
  ${{EndIf}}
  ${{If}} $0 != 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "위젯을 트레이에서 종료한 뒤 다시 설치해주세요." /SD IDOK
    Abort
  ${{EndIf}}
  Sleep 400
{chr(10).join('  '+line for line in install)}
  SetOutPath "$INSTDIR"
  File /oname=installation-manifest.json "{nsis(marker)}"
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKCU "{REG}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "{UNINSTALL}" "DisplayName" "{APP}"
  WriteRegStr HKCU "{UNINSTALL}" "DisplayVersion" "{VERSION}"
  WriteRegStr HKCU "{UNINSTALL}" "Publisher" "마스"
  WriteRegStr HKCU "{UNINSTALL}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "{UNINSTALL}" "DisplayIcon" "$INSTDIR\\{EXE}"
  WriteRegStr HKCU "{UNINSTALL}" "UninstallString" '$\\"$INSTDIR\\Uninstall.exe$\\"'
  WriteRegStr HKCU "{UNINSTALL}" "QuietUninstallString" '$\\"$INSTDIR\\Uninstall.exe$\\" /S'
  WriteRegDWORD HKCU "{UNINSTALL}" "EstimatedSize" {sum(p.stat().st_size for p in files)//1024}
  WriteRegDWORD HKCU "{UNINSTALL}" "NoModify" 1
  WriteRegDWORD HKCU "{UNINSTALL}" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\\{APP}"
  CreateShortcut "$SMPROGRAMS\\{APP}\\{APP}.lnk" "$INSTDIR\\{EXE}"
  CreateShortcut "$SMPROGRAMS\\{APP}\\제거.lnk" "$INSTDIR\\Uninstall.exe"
  CreateShortcut "$DESKTOP\\{APP}.lnk" "$INSTDIR\\{EXE}"
  ReadRegStr $0 HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "HanroroDesktop"
  ${{If}} $0 != ""
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "HanroroDesktop" '$\\"$INSTDIR\\{EXE}$\\"'
  ${{EndIf}}
SectionEnd
Function .onInstSuccess
  ${{If}} $AutoUpdate = 1
    ExecShell "open" "$INSTDIR\\{EXE}"
  ${{EndIf}}
FunctionEnd
Section "Uninstall"
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=CloseHanroro.exe "{nsis(ROOT/'CloseHanroro.exe')}"
  ClearErrors
  ExecWait '$\\"$PLUGINSDIR\\CloseHanroro.exe$\\"' $0
  ${{If}} ${{Errors}}
    MessageBox MB_OK|MB_ICONSTOP "앱 종료 도구를 실행하지 못했습니다. 설치 또는 제거를 중단합니다." /SD IDOK
    Abort
  ${{EndIf}}
  ${{If}} $0 != 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "위젯을 종료한 뒤 다시 제거해주세요." /SD IDOK
    Abort
  ${{EndIf}}
  Sleep 400
  IfFileExists "$INSTDIR\\_internal\\pythonw.exe" 0 +2
    ExecWait '$\\"$INSTDIR\\_internal\\pythonw.exe$\\" $\\"$INSTDIR\\_internal\\recover_desktop.py$\\"' $0
  ReadRegStr $0 HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "HanroroDesktop"
  ${{UnStrStr}} $1 $0 "$INSTDIR\\"
  ${{If}} $1 != ""
    DeleteRegValue HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "HanroroDesktop"
  ${{EndIf}}
  Delete "$DESKTOP\\{APP}.lnk"
  Delete "$SMPROGRAMS\\{APP}\\{APP}.lnk"
  Delete "$SMPROGRAMS\\{APP}\\제거.lnk"
  RMDir "$SMPROGRAMS\\{APP}"
  DeleteRegKey HKCU "{UNINSTALL}"
  DeleteRegKey HKCU "{REG}"
  Delete "$INSTDIR\\_internal\\app.log"
  Delete "$INSTDIR\\_internal\\startup-error.log"
  Delete "$INSTDIR\\installation-manifest.json"
  Delete "$INSTDIR\\Uninstall.exe"
{chr(10).join('  '+line for line in remove)}
SectionEnd
'''
    path=work/'HanroroWidget.nsi';path.write_text(script,encoding='utf-8-sig');return path,manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);parser.add_argument('--output',required=True);parser.add_argument('--work',required=True);parser.add_argument('--makensis',default='makensis');parser.add_argument('--nsis-dir');args=parser.parse_args()
    # Official Windows NSIS packages may ship only the x86 bootstrap. It installs
    # the same x64 application, uses the 64-bit registry view and rejects 32-bit OSes.
    compiler_root=Path(args.nsis_dir) if args.nsis_dir else Path(args.makensis).resolve().parent
    target='amd64-unicode' if os.name!='nt' or (compiler_root/'Stubs/zlib-amd64-unicode').is_file() else 'x86-unicode'
    script,manifest=build_script(args.payload,args.output,args.work,target);env=os.environ.copy()
    if args.nsis_dir:env['NSISDIR']=str(Path(args.nsis_dir).resolve())
    subprocess.run([args.makensis,'-V2',str(script)],env=env,check=True)
    print('Installer:',args.output);print('Bundled files:',len(manifest['files']))
if __name__=='__main__':main()
