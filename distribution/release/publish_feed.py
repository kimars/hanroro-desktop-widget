"""Update the public feed only after the released installer and checksum are present."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from release_info import VERSION,UPDATE_REPOSITORY,INSTALLER_ASSET

def feed_for(release,installer,notes):
    assets=release.get('assets',[]);asset=next((a for a in assets if a.get('name')==INSTALLER_ASSET and a.get('state')=='uploaded'),None);sidecar=next((a for a in assets if a.get('name')==INSTALLER_ASSET+'.sha256' and a.get('state')=='uploaded'),None)
    if release.get('tag_name')!='v'+VERSION or not asset or not sidecar:raise ValueError('Release is not ready')
    digest=hashlib.sha256(installer.read_bytes()).hexdigest();expected='https://github.com/'+UPDATE_REPOSITORY+'/releases/download/v'+VERSION+'/'+INSTALLER_ASSET
    if asset['size']!=installer.stat().st_size or asset['browser_download_url']!=expected or (asset.get('digest') and asset['digest']!='sha256:'+digest):raise ValueError('Release integrity mismatch')
    return {'repository':UPDATE_REPOSITORY,'version':VERSION,'url':expected,'size':asset['size'],'sha256':digest,'notes':notes[:6000]}

def main():
    release=json.loads(subprocess.check_output(['gh','api','repos/'+UPDATE_REPOSITORY+'/releases/tags/v'+VERSION],text=True,encoding='utf-8'))
    feed=feed_for(release,ROOT/'release'/INSTALLER_ASSET,(ROOT/'distribution/release/notes.md').read_text(encoding='utf-8'))
    route='repos/'+UPDATE_REPOSITORY+'/contents/update-feed.json';old=subprocess.run(['gh','api',route],capture_output=True,text=True,encoding='utf-8')
    payload={'message':'Publish update feed for '+VERSION,'branch':'main','content':base64.b64encode(json.dumps(feed,ensure_ascii=False,indent=2).encode()).decode()}
    if old.returncode==0:payload['sha']=json.loads(old.stdout)['sha']
    request=ROOT/'release/feed-request.json';request.write_text(json.dumps(payload),encoding='utf-8')
    subprocess.run(['gh','api','--method','PUT',route,'--input',str(request)],check=True,stdout=subprocess.DEVNULL);print('Published update feed '+VERSION)
if __name__=='__main__':main()
