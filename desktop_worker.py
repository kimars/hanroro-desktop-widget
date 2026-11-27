"""Bounded shell IPC endpoint. Native shell extensions never run in the GUI process."""
import json,sys
from media_worker import stdio

def execute(request):
    action=request.get('action')
    if action=='resolve':
        from desktop_native import resolve_rows
        return resolve_rows(request.get('rows',[])[:64])
    if action=='windows':
        from shell_windows import visible_windows
        data=visible_windows();data['paths']=list(data['paths']);return data
    if action=='icons':
        from desktop_native import extract_icon
        rows=[]
        for r in request.get('rows',[])[:2]:
            try:png=extract_icon(r)
            except Exception:png=''
            rows.append({'key':r['key'],'png':png})
        return rows
    if action=='launch':
        from app_windows import toggle_or_launch,_shortcut_cache,_app_shortcuts
        row=request['row'];target=row['target']
        if target.startswith('app:') and row.get('path'):_app_shortcuts[target[4:].casefold()]=row['path']
        if row.get('path') and row.get('exe'):_shortcut_cache[row['path']]=row['exe']
        return {'status':toggle_or_launch(target)}
    raise ValueError('Unknown shell request')

def run():
    source=stdio('stdin',-10);out=stdio('stdout',-11)
    for line in source:
        try:
            if len(line)>1024*1024:raise ValueError('Request too large')
            request=json.loads(line);result={'id':request['id'],'action':request['action'],'data':execute(request)}
        except Exception as e:result={'id':locals().get('request',{}).get('id',0),'action':locals().get('request',{}).get('action',''),'error':str(e)[:300]}
        out.write(json.dumps(result,ensure_ascii=True)+'\n');out.flush()
    return 0


def inventory():
    out=stdio('stdout',-11)
    def emit(data):out.write(json.dumps(data,ensure_ascii=True)+'\n');out.flush()
    from app_catalog import collect_apps
    from taskbar_catalog import collect_taskbar
    from desktop_native import resolve_rows
    try:
        rows=collect_apps();emit({'phase':'catalog','rows':rows})
        pins=resolve_rows(collect_taskbar(rows));emit({'phase':'taskbar','rows':pins})
    except Exception as e:emit({'phase':'taskbar','rows':[],'error':str(e)[:300]})
    return 0


def search_once():
    from shell_search import indexed_files
    source=stdio('stdin',-10);out=stdio('stdout',-11)
    try:
        request=json.loads(source.readline(32768));rows=indexed_files(str(request.get('query',''))[:200],request.get('roots',[])[:3]);result={'id':request['id'],'data':rows}
    except Exception:result={'id':locals().get('request',{}).get('id',0),'data':[]}
    out.write(json.dumps(result,ensure_ascii=True)+'\n');out.flush();return 0
