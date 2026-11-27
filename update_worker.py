"""Public GitHub release checks/downloads. Network and hashing never run in the GUI."""
import hashlib,json,os,re,sys,time
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from media_worker import stdio
from release_info import INSTALLER_ASSET
MAX_INSTALLER=1024**3
HOSTS=('raw.githubusercontent.com','github.com','api.github.com','objects.githubusercontent.com','release-assets.githubusercontent.com')

def version_tuple(text):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',str(text))
    if not match:raise ValueError('올바른 버전 번호가 아닙니다.')
    return tuple(int(n) for n in match.groups())

def trusted_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.hostname not in HOSTS:raise ValueError('허용되지 않은 업데이트 주소입니다.')
    return url

class SecureRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        trusted_url(newurl)
        result=super().redirect_request(request,fp,code,msg,headers,newurl)
        if result is not None and request.get_method()=='HEAD':result.method='HEAD'
        return result

def open_url(url):
    trusted_url(url)
    return build_opener(SecureRedirect()).open(Request(url,headers={'User-Agent':'HanroroDesktopWidget-Updater','Accept':'application/vnd.github+json' if url.startswith('https://api.github.com/') else 'application/octet-stream'}),timeout=30)

def limited_read(url,limit):
    with open_url(url) as response:
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('업데이트 응답이 너무 큽니다.')
    return data

def validate_feed(data,repository,current):
    if not isinstance(data,dict) or data.get('repository')!=repository:raise ValueError('배포 저장소가 다릅니다.')
    version=str(data.get('version',''));version_tuple(version)
    if version_tuple(version)<=version_tuple(current):return {'status':'current','version':current,'channel':'feed'}
    url=str(data.get('url',''));expected='https://github.com/'+repository+'/releases/download/v'+version+'/'+INSTALLER_ASSET
    if url!=expected:raise ValueError('설치 파일 주소가 올바르지 않습니다.')
    trusted_url(url);size=int(data.get('size',0));digest=str(data.get('sha256',''))
    if not 1<=size<=MAX_INSTALLER or not re.fullmatch('[0-9a-fA-F]{64}',digest):raise ValueError('설치 파일 검증 정보가 올바르지 않습니다.')
    return {'status':'available','version':version,'url':url,'size':size,'sha256':digest.lower(),'notes':str(data.get('notes',''))[:6000],'channel':'feed'}

def probe(repository,current):
    result=release_info(repository,current)
    return {'status':'unchanged','channel':result.get('channel','api')} if result['status']=='current' else result

def release_info(repository,current):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('업데이트 저장소가 설정되지 않았습니다.')
    try:
        feed=json.loads(limited_read('https://raw.githubusercontent.com/'+repository+'/main/update-feed.json?minute='+str(int(time.time()//60)),32768))
        return validate_feed(feed,repository,current)
    except (OSError,ValueError,KeyError,TypeError):pass
    try:data=json.loads(limited_read('https://api.github.com/repos/'+repository+'/releases/latest',1024**2))
    except HTTPError as error:
        if error.code==404:return {'status':'current','version':current,'message':'아직 새 업데이트가 없습니다.'}
        if error.code in (403,429):raise ValueError('잠시 후 업데이트를 다시 확인해주세요.') from error
        raise
    if data.get('draft') or data.get('prerelease'):return {'status':'current','version':current}
    version=str(data.get('tag_name','')).removeprefix('v');version_tuple(version)
    if version_tuple(version)<=version_tuple(current):return {'status':'current','version':current}
    assets=data.get('assets',[]);asset=next((a for a in assets if a.get('name')==INSTALLER_ASSET and a.get('state')=='uploaded'),None)
    if not asset:raise ValueError('새 버전의 설치 파일이 아직 준비되지 않았습니다.')
    prefix='https://github.com/'+repository+'/releases/download/'
    url=asset.get('browser_download_url','');trusted_url(url)
    if not url.startswith(prefix):raise ValueError('배포 저장소와 설치 파일 주소가 다릅니다.')
    size=int(asset.get('size',0))
    if not 1<=size<=MAX_INSTALLER:raise ValueError('업데이트 파일 크기가 올바르지 않습니다.')
    digest=str(asset.get('digest') or '')
    if digest.startswith('sha256:'):digest=digest[7:]
    else:
        sidecar=next((a for a in assets if a.get('name')==INSTALLER_ASSET+'.sha256'),None)
        checksum_url=sidecar.get('browser_download_url','') if sidecar else ''
        if not checksum_url.startswith(prefix):raise ValueError('업데이트 파일 검증 정보가 없습니다.')
        digest=limited_read(checksum_url,1024).decode('ascii').split()[0]
    if not re.fullmatch('[0-9a-fA-F]{64}',digest):raise ValueError('업데이트 파일 검증 정보가 올바르지 않습니다.')
    return {'status':'available','version':version,'url':url,'size':size,'sha256':digest.lower(),'notes':str(data.get('body') or '')[:6000],'channel':'api'}

def download(repository,current,directory,emit):
    # Re-fetch trusted release metadata; do not accept a file URL from a UI command.
    info=release_info(repository,current)
    if info['status']!='available':raise ValueError('현재 설치할 새 업데이트가 없습니다.')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    target=directory/('HanroroWidget-'+info['version']+'.exe');partial=target.with_suffix('.part')
    digest=hashlib.sha256();count=0;first=b'';last=0
    try:
        with open_url(info['url']) as response,partial.open('wb') as output:
            while True:
                block=response.read(256*1024)
                if not block:break
                if not first:first=block[:2]
                count+=len(block)
                if count>info['size'] or count>MAX_INSTALLER:raise ValueError('업데이트 파일 크기가 예상과 다릅니다.')
                output.write(block);digest.update(block)
                if time.monotonic()-last>.1:last=time.monotonic();emit({'status':'downloading','progress':min(99,round(count/info['size']*100)),'version':info['version']})
            output.flush();os.fsync(output.fileno())
        if count!=info['size'] or first!=b'MZ' or digest.hexdigest()!=info['sha256']:raise ValueError('업데이트 파일 검증에 실패했습니다. 다시 받아주세요.')
        os.replace(partial,target)
        if sys.platform=='win32':
            # Preserve the normal Windows downloaded-file security check.
            with open(str(target)+':Zone.Identifier','w',encoding='utf-8') as zone:zone.write('[ZoneTransfer]\nZoneId=3\nHostUrl=https://github.com/\n')
        return {**info,'status':'ready','path':str(target),'progress':100}
    finally:partial.unlink(missing_ok=True)

def run():
    out=stdio('stdout',-11)
    def emit(data):out.write(json.dumps(data,ensure_ascii=True)+'\n');out.flush()
    try:
        request=json.loads(stdio('stdin',-10).readline(8192))
        if request['action']=='probe':result=probe(request['repository'],request['current'])
        elif request['action']=='check':result=release_info(request['repository'],request['current'])
        elif request['action']=='download':result=download(request['repository'],request['current'],request['directory'],emit)
        else:raise ValueError('알 수 없는 업데이트 요청입니다.')
        emit(result);return 0
    except Exception as error:emit({'status':'error','message':str(error)[:300] or '업데이트 연결에 실패했습니다.'});return 1
if __name__=='__main__':sys.exit(run())
