"""Refuse to build a release from truncated or modified bundled artwork."""
from pathlib import Path
import hashlib,json,sys

def verify(directory):
    root=Path(directory).resolve();manifest=json.loads((root/'integrity.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        target=(root/row['path']).resolve()
        if not target.is_relative_to(root):raise ValueError('Asset path escapes its directory')
        if not target.is_file() or target.stat().st_size!=row['size']:raise ValueError('Asset size mismatch: '+row['path'])
        digest=hashlib.sha256()
        with target.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        if digest.hexdigest()!=row['sha256']:raise ValueError('Asset SHA-256 mismatch: '+row['path'])
    return len(manifest['files'])

if __name__=='__main__':print('Verified bundled assets:',verify(sys.argv[1]))
