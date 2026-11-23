import threading
from PySide6.QtCore import QObject,Signal,Qt,QFileInfo
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QPushButton,QFileIconProvider,QProgressBar
from app_catalog import collect_apps
from panel_ui import STYLE

class Results(QObject):
    ready=Signal(list)

class AppPicker(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setStyleSheet(STYLE);self.setWindowTitle('앱 선택');self.resize(620,590);self.selected=None
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(14)
        title=QLabel('설치된 앱');title.setStyleSheet('font-size:24px;font-weight:600;');layout.addWidget(title)
        self.search=QLineEdit();self.search.setPlaceholderText('앱 이름 검색');self.search.textChanged.connect(self.filter);layout.addWidget(self.search)
        self.list=QListWidget();self.list.itemDoubleClicked.connect(self.choose);layout.addWidget(self.list,1)
        self.status=QLabel('Windows 앱 목록을 불러오는 중…');layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setMaximumHeight(4);self.progress.setTextVisible(False);layout.addWidget(self.progress)
        row=QHBoxLayout();row.addWidget(QPushButton('새로고침',clicked=self.reload));row.addStretch();row.addWidget(QPushButton('취소',clicked=self.reject));self.ok=QPushButton('선택',clicked=self.choose);self.ok.setObjectName('primary');self.ok.setEnabled(False);row.addWidget(self.ok);layout.addLayout(row)
        self.bus=Results(self);self.bus.ready.connect(self.populate);self.reload()
    def reload(self):
        self.progress.show();self.ok.setEnabled(False);self.status.setText('Windows 앱 목록을 불러오는 중…')
        bus=self.bus
        def work():
            data=collect_apps()
            try:bus.ready.emit(data)
            except RuntimeError:pass # Dialog was closed; no QThread lifetime to crash on.
        threading.Thread(target=work,daemon=True).start()
    def populate(self,rows):
        self.list.clear();provider=QFileIconProvider()
        for row in rows:
            item=QListWidgetItem(row['name']);item.setData(Qt.ItemDataRole.UserRole,row)
            if row['path']:item.setIcon(provider.icon(QFileInfo(row['path'])))
            self.list.addItem(item)
        self.progress.hide();self.ok.setEnabled(bool(rows));self.status.setText(f'{len(rows)}개 앱' if rows else '앱을 찾지 못했습니다. 파일 선택으로 실행 파일을 지정할 수 있습니다.');self.filter(self.search.text())
    def filter(self,text):
        query=text.casefold();first=None
        for i in range(self.list.count()):
            item=self.list.item(i);item.setHidden(query not in item.text().casefold())
            if first is None and not item.isHidden():first=item
        self.list.setCurrentItem(first);self.ok.setEnabled(first is not None)
    def choose(self,*_):
        item=self.list.currentItem()
        if item:self.selected=item.data(Qt.ItemDataRole.UserRole);self.accept()
