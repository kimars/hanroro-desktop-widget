"""Prepare release checksum; publish only when --publish is explicitly requested."""
import argparse,hashlib,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from release_info import VERSION,UPDATE_REPOSITORY,INSTALLER_ASSET

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--installer',required=True);parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    installer=Path(args.installer).resolve()
    if installer.name!=INSTALLER_ASSET or not installer.is_file():raise SystemExit('Use the built '+INSTALLER_ASSET)
    checksum=installer.with_name(installer.name+'.sha256');digest=hashlib.sha256()
    with installer.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):digest.update(block)
    checksum.write_text(digest.hexdigest()+'  '+installer.name+'\n',encoding='ascii')
    print('Version:',VERSION);print('Repository:',UPDATE_REPOSITORY);print('Installer:',installer);print('Checksum:',checksum)
    if args.publish:
        # GitHub CLI uses the owner's existing login; credentials never enter the app.
        account=subprocess.check_output(['gh','api','user','--jq','.login'],text=True).strip()
        if account.casefold()!=UPDATE_REPOSITORY.split('/')[0].casefold():raise SystemExit('Sign in to the repository owner account before publishing.')
        subprocess.run(['gh','release','create','v'+VERSION,str(installer),str(checksum),'--repo',UPDATE_REPOSITORY,'--title','한로로 바탕화면 위젯 '+VERSION,'--notes','앱의 설정 → 업데이트에서 새 버전을 설치할 수 있습니다.','--latest'],check=True)
if __name__=='__main__':main()
