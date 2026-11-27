"""Read Explorer's app-button order, without alphabetical sorting or editing pins."""
import json,subprocess,sys,math,ntpath
from pathlib import Path

SNAPSHOT=r'''
[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type 'using System; using System.Runtime.InteropServices; public static class HanTaskbar { [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string c,string n); }'
$h=[HanTaskbar]::FindWindow('Shell_TrayWnd',$null)
if($h -eq [IntPtr]::Zero){throw 'Taskbar unavailable'}
$root=[System.Windows.Automation.AutomationElement]::FromHandle($h)
$condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
$rows=@();$ordinal=0
foreach($e in $all){try{
 $c=$e.Current;$id=[string]$c.AutomationId;$name=[string]$c.Name
 if($id.StartsWith('Appid: ')){
  $rows+=@{name=$name;appid=$id.Substring(7);ordinal=$ordinal;left=$c.BoundingRectangle.Left}
  $ordinal++
 }
}catch{}}
ConvertTo-Json -InputObject $rows -Compress
'''

def normalize_taskbar(rows,catalog):
    known={r['target'].casefold():r for r in catalog};result=[];seen=set()
    if rows and all(isinstance(r.get('left'),(int,float)) and math.isfinite(r['left']) for r in rows) and len({r['left'] for r in rows})==len(rows):rows=sorted(rows,key=lambda r:r['left'])
    # Provider order is the actual taskbar order. Never sort by translated display name.
    for raw in rows:
        ident=str(raw.get('appid','')).strip()
        if not ident or any(c in ident for c in '\r\n\0'):continue
        target=ident if ntpath.isabs(ident) and ntpath.splitext(ident)[1].lower() in ('.exe','.lnk') else 'app:'+ident
        if target.casefold() in seen:continue
        seen.add(target.casefold());match=known.get(target.casefold(),{})
        result.append({'name':match.get('name') or str(raw.get('name') or ident).split(' - ')[0][:160],'target':target,'path':match.get('path',''),'kind':'taskbar'})
    return result

def collect_taskbar(catalog,runner=subprocess.run):
    if sys.platform!='win32':return []
    result=runner(['powershell.exe','-NoProfile','-NonInteractive','-Command',SNAPSHOT],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=12,check=True,creationflags=0x08000000)
    rows=json.loads(result.stdout.lstrip('\ufeff') or '[]')
    if not isinstance(rows,list):raise ValueError('작업 표시줄 목록을 읽을 수 없습니다.')
    return normalize_taskbar(rows,catalog)


def group_windows(rows):
    grouped={}
    for row in rows:
        key=row['target'].casefold();grouped.setdefault(key,[]).append(row)
    return grouped


def dock_rows(taskbar,running):
    from desktop_native import matching_windows
    result=[dict(r) for r in taskbar];matched={int(w.get('hwnd',0)) for r in taskbar for w in matching_windows(r,running) if w.get('hwnd')};known={r['target'].casefold() for r in result}
    paths={str(r.get('path','')).casefold() for r in result if r.get('path')}
    for row in running:
        if row.get('hwnd') in matched:continue
        key=row['target'].casefold();path=str(row.get('path','')).casefold()
        if key not in known and (not path or path not in paths):result.append(dict(row));known.add(key)
    return result
