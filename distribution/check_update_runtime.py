"""Exercise the packaged automatic worker against the actual public distribution endpoint."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from release_info import UPDATE_REPOSITORY
from update_worker import trusted_url

def check(runtime,entry,directory):
    request={'action':'probe','repository':UPDATE_REPOSITORY,'current':'0.0.0','directory':str(directory)}
    result=subprocess.run([str(runtime),str(entry),'--update-worker'],input=json.dumps(request)+'\n',capture_output=True,text=True,encoding='utf-8',timeout=75)
    lines=[]
    for line in result.stdout.splitlines():
        try:lines.append(json.loads(line))
        except ValueError:continue
    if result.returncode or not lines or lines[-1].get('status')!='available':raise RuntimeError('Packaged automatic update probe failed: '+str(lines[-1] if lines else result.stderr[-500:]))
    data=lines[-1];trusted_url(data['url'])
    if len(data.get('sha256',''))!=64:raise RuntimeError('Missing installer checksum')
    print('Packaged automatic update probe passed: version='+data['version']+' channel='+data.get('channel','unknown'),flush=True)
if __name__=='__main__':check(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
