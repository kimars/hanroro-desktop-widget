"""Decoded update artwork, supplied directly to each Qt Quick engine."""
from functools import lru_cache
from pathlib import Path
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

@lru_cache(maxsize=2)
def artwork(path,modified):
    try:
        image=QImage.fromData(Path(path).read_bytes(),'PNG')
    except OSError:
        logging.exception('Update character file could not be read: %s',path)
        return QImage()
    if image.isNull():logging.error('Update character PNG could not be decoded: %s',path)
    # A fixed premultiplied format is suitable for both D3D and software rendering.
    return image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

class UpdateArtworkProvider(QQuickImageProvider):
    def __init__(self,path):
        super().__init__(QQuickImageProvider.ImageType.Image)
        path=Path(path);self.image=artwork(str(path.resolve()),path.stat().st_mtime_ns if path.is_file() else 0)
        logging.info('Update character loaded: %s (%sx%s)',path,self.image.width(),self.image.height())
    def requestImage(self,identity,size,requested):
        image=self.image
        if size is not None:size.setWidth(image.width());size.setHeight(image.height())
        if requested.width()>0 and not image.isNull():
            image=image.scaledToWidth(requested.width(),Qt.TransformationMode.SmoothTransformation)
        return image
