"""Isolated Windows wallpaper calls. A stalled shell must not block the UI."""
import json,sys,traceback
from pathlib import Path
from types import SimpleNamespace

def run(request_file):
    request=Path(request_file);result=request.with_suffix('.result.json')
    try:
        from windows_desktop import DesktopHost,IS_WINDOWS
        if not IS_WINDOWS:raise OSError('Windows wallpaper operations require Windows')
        data=json.loads(request.read_text('utf-8'));host=DesktopHost()
        if data['operation']=='apply':
            screen=SimpleNamespace(name=lambda:data['screen'])
            host.apply_static_wallpaper(data['path'],screen,data['directory'])
        elif data['operation']=='restore':host.restore_static_wallpaper(data['directory'])
        else:raise ValueError('Unknown wallpaper operation')
        answer={'ok':True,'detail':''};code=0
    except Exception:
        answer={'ok':False,'detail':traceback.format_exc()};code=1
    result.write_text(json.dumps(answer,ensure_ascii=False),encoding='utf-8')
    return code

if __name__=='__main__':sys.exit(run(sys.argv[1]))
