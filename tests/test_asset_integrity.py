from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'distribution'))
import pytest
from verify_assets import verify

def prepare(root):
    data=b'unchanged original asset';(root/'person.png').write_bytes(data)
    (root/'integrity.json').write_text(json.dumps({'files':[{'path':'person.png','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}))
    return data

def test_asset_manifest_accepts_exact_bytes(tmp_path):
    prepare(tmp_path);assert verify(tmp_path)==1

def test_asset_manifest_rejects_truncation_and_same_size_corruption(tmp_path):
    data=prepare(tmp_path);(tmp_path/'person.png').write_bytes(data[:-3])
    with pytest.raises(ValueError,match='size mismatch'):verify(tmp_path)
    (tmp_path/'person.png').write_bytes(data[:-1]+b'x')
    with pytest.raises(ValueError,match='SHA-256 mismatch'):verify(tmp_path)

def test_asset_manifest_cannot_escape_asset_directory(tmp_path):
    (tmp_path/'integrity.json').write_text(json.dumps({'files':[{'path':'../secret','size':5,'sha256':''}]}))
    with pytest.raises(ValueError,match='escapes'):verify(tmp_path)
