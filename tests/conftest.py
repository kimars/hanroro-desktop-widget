"""Keep one QApplication alive for all Qt test modules."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_AUDIO_BACKEND','pulseaudio')
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope='session',autouse=True)
def qt_application():
    app=QApplication.instance() or QApplication([])
    yield app
