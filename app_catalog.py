"""Windows Start menu/AppUserModelID inventory. Never interpolates names into commands."""
from pathlib import Path
import json,os,subprocess,sys

SCRIPT=r'''[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress'''

def collect_apps(runner=subprocess.run,environment=None,force=False):
    if sys.platform!='win32' and not force:return []
    env=os.environ if environment is None else environment
    rows=[]
    try:
        result=runner(['powershell.exe','-NoProfile','-NonInteractive','-Command',SCRIPT],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,check=True,creationflags=0x08000000 if sys.platform=='win32' else 0)
        data=json.loads(result.stdout.lstrip('\ufeff') or '[]')
        if isinstance(data,dict):data=[data]
        if not isinstance(data,list):data=[]
        for row in data:
            if not isinstance(row,dict):continue
            name=str(row.get('Name','')).strip();ident=str(row.get('AppID','')).strip()
            if name and ident and not any(c in ident for c in '\r\n\0'):
                rows.append({'name':name,'target':'app:'+ident,'path':''})
    except (OSError,ValueError,subprocess.SubprocessError):pass
    # Older/disabled PowerShell installations can still use Start menu shortcuts.
    existing={r['name'].casefold() for r in rows};named={r['name'].casefold():r for r in rows}
    for base in (env.get('APPDATA'),env.get('PROGRAMDATA')):
        if not base:continue
        root=Path(base)/'Microsoft/Windows/Start Menu/Programs'
        try:
            for file in root.rglob('*.lnk'):
                if file.stem.casefold() in named:named[file.stem.casefold()]['path']=str(file)
                if file.stem.casefold() not in existing:
                    rows.append({'name':file.stem,'target':str(file),'path':str(file)});existing.add(file.stem.casefold())
        except OSError:continue
    from app_windows import register_app_shortcuts
    register_app_shortcuts(rows)
    return sorted({r['target']:r for r in rows}.values(),key=lambda r:r['name'].casefold())

def app_shell_target(identifier):
    if not identifier or len(identifier)>2048 or any(c in identifier for c in '\r\n\0'):raise ValueError('올바른 앱 식별자가 아닙니다.')
    return 'shell:AppsFolder\\'+identifier
