"""Full-desktop photo rendering, independent from record artwork."""
from pathlib import Path
import hashlib
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QImage,QImageReader,QPainter,QColor

def render_wallpaper(source,directory,theme='apricot',dim=0.,size=(1920,1080),fit='fill'):
    source=Path(source);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    signature=f'{source.resolve()}:{source.stat().st_mtime_ns if source.exists() else 0}:{theme}:{dim}:{size}:{fit}:desktop-v3'
    destination=directory/('wallpaper-'+hashlib.sha256(signature.encode()).hexdigest()[:16]+'.png')
    if destination.exists():return destination
    width,height=size;image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(QColor('#151719' if theme=='night' else '#e6e7e5'))
    reader=QImageReader(str(source));reader.setAutoTransform(True);photo=reader.read();painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if not photo.isNull():
        ratio=(min if fit=='fit' else max)(width/photo.width(),height/photo.height());w=photo.width()*ratio;h=photo.height()*ratio
        painter.drawImage(QRectF((width-w)/2,(height-h)/2,w,h),photo)
    if dim>0:painter.fillRect(image.rect(),QColor(0,0,0,round(dim*255)))
    painter.end()
    if not image.save(str(destination)):raise OSError('배경 이미지를 저장할 수 없습니다.')
    return destination
