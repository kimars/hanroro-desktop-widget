from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from update_artwork import UpdateArtworkProvider

def test_artwork_provider_returns_decoded_scaled_transparent_image():
    path=Path(__file__).resolve().parents[1]/'assets/ui/update-character.png'
    provider=UpdateArtworkProvider(path);native=QSize()
    image=provider.requestImage('character',native,QSize(452,0))
    assert not image.isNull() and image.width()==452 and native.width()==1122
    assert image.format()==QImage.Format_ARGB32_Premultiplied
    assert image.pixelColor(0,0).alpha()==0
    assert any(image.pixelColor(x,y).alpha()>0 for x in range(30,image.width(),30) for y in range(30,image.height(),30))

def test_missing_artwork_is_detected(tmp_path):
    provider=UpdateArtworkProvider(tmp_path/'missing.png')
    assert provider.image.isNull()
