"""Bounded searches: cached installed apps, indexed files, then local-folder fallback."""
import json,subprocess,sys,os
from pathlib import Path

def rank_apps(rows,query,limit=24):
    q=query.casefold().strip();hits=[r for r in rows if not q or q in r['name'].casefold()]
    return (sorted(hits,key=lambda r:r['name'].casefold()) if not q else sorted(hits,key=lambda r:(not r['name'].casefold().startswith(q),len(r['name']),r['name'].casefold())))[:limit]

def local_files(query,roots,limit=12):
    q=query.casefold().strip();out=[];visited=0
    if len(q)<2:return out
    for root in roots:
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    visited+=1
                    if visited>2500:return out
                    if q in entry.name.casefold() and not entry.name.startswith('.'):
                        out.append({'name':entry.name,'target':entry.path,'path':entry.path,'kind':'file'})
                        if len(out)>=limit:return out
        except OSError:continue
    return out

def indexed_files(query,roots):
    if len(query.strip())<2:return []
    if sys.platform=='win32':
        # Query text is a JSON PowerShell argument and a quoted SQL literal, never command syntax.
        escaped=query.replace("'","''").replace('[','[[]').replace('%','[%]').replace('_','[_]')[:120]
        sql="SELECT TOP 12 System.ItemNameDisplay,System.ItemPathDisplay FROM SYSTEMINDEX WHERE System.FileName LIKE '%"+escaped+"%'"
        import base64
        encoded=base64.b64encode(sql.encode('utf-8')).decode('ascii')
        script="[Console]::OutputEncoding=[Text.UTF8Encoding]::new();$c=New-Object -ComObject ADODB.Connection;$c.Open(\"Provider=Search.CollatorDSO;Extended Properties='Application=Windows';\");$q=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"'));$r=$c.Execute($q);$a=@();while(!$r.EOF){$a+=@{name=[string]$r.Fields.Item(0).Value;path=[string]$r.Fields.Item(1).Value};$r.MoveNext()};$r.Close();$c.Close();ConvertTo-Json -InputObject $a -Compress"
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',timeout=3,creationflags=0x08000000,check=True)
            rows=json.loads(result.stdout.lstrip('\ufeff') or '[]')
            if isinstance(rows,list):
                valid=[{'name':str(r['name'])[:200],'target':str(r['path']),'path':str(r['path']),'kind':'file'} for r in rows[:12] if r.get('path') and Path(str(r['path'])).exists()]
                if valid:return valid
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):pass
    return local_files(query,roots)
