"""Ask this application, and only this application, to exit normally."""
import hashlib,sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QStandardPaths
from PySide6.QtNetwork import QLocalSocket

def stop():
    app=QCoreApplication(sys.argv);app.setOrganizationName('Mars');app.setApplicationName('HanroroDesktop')
    directory=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    channel='hanroro-'+hashlib.sha256(str(directory).encode()).hexdigest()[:16]
    socket=QLocalSocket();socket.connectToServer(channel)
    if not socket.waitForConnected(600):
        from recover_desktop import restore
        restore();print('Hanroro Desktop is not running.');return 0
    socket.write(b'quit');socket.waitForBytesWritten(1000)
    if not socket.waitForDisconnected(5000):
        print('The app is not responding. Run force_stop.bat from this same folder.');return 1
    print('Hanroro Desktop stopped.');return 0

if __name__=='__main__':sys.exit(stop())
