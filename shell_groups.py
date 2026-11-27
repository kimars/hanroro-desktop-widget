"""Canonical app groups shared by shortcuts, taskbar pins and window snapshots."""
import ntpath,os

def explorer(row):
    target=str(row.get('target','')).casefold();path=str(row.get('exe') or row.get('path') or target)
    return (row.get('class') in ('CabinetWClass','ExploreWClass') or ntpath.basename(path).casefold()=='explorer.exe' or target in ('app:microsoft.windows.explorer','app:explorer.exe') or target.startswith('special:') or bool(row.get('directory')))

def app_key(row):
    if explorer(row):return 'explorer'
    if row.get('group'):return str(row['group']).casefold()
    target=str(row.get('target','')).casefold();appid=str(row.get('app_id') or (target[4:] if target.startswith('app:') else ''))
    if appid:return 'app:'+appid
    path=str(row.get('exe') or row.get('path') or target)
    if ntpath.splitext(path)[1].casefold()=='.exe':return 'exe:'+ntpath.normcase(ntpath.normpath(path))
    return target

def same_app(a,b):
    if app_key(a)==app_key(b):return True
    aid=str(a.get('app_id') or (a.get('target','')[4:] if a.get('target','').startswith('app:') else ''))
    bid=str(b.get('app_id') or (b.get('target','')[4:] if b.get('target','').startswith('app:') else ''))
    if aid and bid and aid.casefold()!=bid.casefold():return False
    from desktop_native import matching_windows
    return bool(matching_windows(a,[b]) or matching_windows(b,[a]))

def compose(taskbar,running,shortcuts=()):
    result=[]
    for source in (taskbar,shortcuts,running):
        for value in source:
            row=dict(value);group=next((r for r in result if same_app(r,row)),None)
            if group is None:
                group=row;group['group']=app_key(row);group['shortcuts']=[];result.append(group)
            if explorer(row):
                group['name']='파일 탐색기';group['app_id']='Microsoft.Windows.Explorer';group['group']='explorer'
                # Use Explorer's original application icon, not a folder-specific image.
                group['exe']=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'explorer.exe');group.pop('glyph',None)
            if row.get('kind')=='shortcut':
                group['shortcuts'].append(dict(value))
                if 'index' not in group and not row['target'].startswith(('special:','action:','http')):group['index']=row['index']
            elif row.get('hwnd'):
                group.setdefault('hwnd',row['hwnd'])
                if not group.get('path'):group['path']=row.get('path','')
            for key in ('exe','child_exe','executables'):
                if not group.get(key) and row.get(key):group[key]=row[key]
    return result
