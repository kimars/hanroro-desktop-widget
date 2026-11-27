"""Shared desktop settings components. Draw controls consistently on every OS."""
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QVariantAnimation,Property,Signal,QRectF,QLocale
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QLinearGradient,QIcon,QPainterPath,QImageReader,QPixmap,QDoubleValidator
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QCheckBox,QDoubleSpinBox,QAbstractSpinBox,QStyledItemDelegate,QStyle,QListWidgetItem,QFileDialog,QDialog,QLineEdit,QGridLayout,QSlider)
ASSETS=Path(__file__).resolve().parent/'assets'
STYLE='''
QWidget {background:transparent;color:#26383c;font-size:13px;}
QDialog#settingsWindow {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #fff8ef,stop:0.55 #fffdf8,stop:1 #eef6ff);}
QDialog {background:#f4f7f5;}
QFrame#sidebar {background:qlineargradient(x1:0,y1:0,x2:0.5,y2:1,stop:0 #3c536b,stop:1 #496581);border:1px solid #405b5b;border-radius:22px;}
QLabel#sidebarTitle {color:white;font-size:25px;font-weight:500;}
QLabel#sidebarHint {color:#b7cac7;font-size:11px;}
QLabel#heading {font-size:29px;font-weight:500;color:#3c536b;}
QLabel#sub {color:#7b9295;font-size:12px;}
QLabel#cardTitle {font-size:15px;font-weight:500;color:#2d4245;}
QLabel#eyebrow {color:#678b89;font-size:11px;font-weight:500;}
QLabel#fieldLabel {color:#5e777a;font-size:12px;font-weight:400;}
QFrame#card {background:#ffffff;border:1px solid #dde7e3;border-radius:19px;}
QFrame#previewCard {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #eaf2ee,stop:1 #edf4f2);border:1px solid #d9e7e1;border-radius:16px;}
QLabel#statusPill {background:#e4eeea;color:#527b79;border-radius:12px;padding:6px 11px;font-size:11px;}
QPushButton,QToolButton {background:#fff0ed;color:#47686b;border:1px solid #dce7e2;border-radius:11px;padding:9px 14px;min-height:18px;font-weight:400;}
QPushButton:hover,QToolButton:hover {background:#dfeae5;color:#294f51;border-color:#b8d0c7;}
QPushButton:pressed,QToolButton:pressed {background:#d0e2da;}
QPushButton:focus,QToolButton:focus {border:1px solid #84aaa0;outline:none;}
QPushButton:disabled {color:#a5b6b1;background:#eff3f0;border-color:#e5ece7;}
QPushButton#primary {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #a66f78,stop:1 #7d5a68);color:white;border:1px solid #527873;font-weight:500;}
QPushButton#primary:hover {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #658d86,stop:1 #365a5a);border-color:#8aaba2;}
QPushButton#primary:pressed {background:#29484b;}
QPushButton#primary:disabled {background:#e6ede8;color:#a0b3aa;border:1px solid #dce7df;}
QPushButton#danger {color:#c57a8a;background:#fbf0f3;border-color:#f2e4e9;}
QPushButton#quiet {background:transparent;border-color:transparent;color:#829693;}
QPushButton[segment="true"] {background:transparent;border:0;color:#82958f;border-radius:9px;min-height:18px;padding:7px 12px;}
QPushButton[segment="true"]:checked {background:#dfece6;color:#426d67;}
QToolButton#iconChoice {background:#f0f5f1;border:1px solid transparent;border-radius:10px;padding:9px;}
QToolButton#iconChoice:checked {background:#d7e9df;border-color:#82a897;}
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:#fffdf8;color:#354c4d;border:1px solid #dce6e0;border-radius:10px;padding:9px 12px;selection-background-color:#bbd8cb;selection-color:#2e5652;}
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus {border-color:#89ad9c;background:#fff;}
QComboBox {min-height:19px;padding-right:30px;}
QComboBox::drop-down {width:28px;border:0;background:transparent;}
QComboBox::down-arrow {image:url(__CHEVRON__);width:13px;height:13px;}
QComboBox QAbstractItemView {background:white;color:#4f7170;border:1px solid #dce7e0;selection-background-color:#e2eee7;selection-color:#3e6a61;padding:7px;outline:none;}
QScrollArea {background:transparent;border:none;}
QScrollBar:vertical {background:transparent;width:7px;margin:3px 0;}
QScrollBar::handle:vertical {background:#c1d3ca;border-radius:3px;min-height:42px;}
QScrollBar::handle:vertical:hover {background:#8bad9d;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0px;width:0px;border:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
QScrollBar:horizontal {height:0px;border:0;}
QListWidget {background:transparent;border:0;outline:none;padding:3px;}
QListWidget::item {padding:9px;border-radius:11px;color:#6b8381;}
QListWidget::item:selected {background:#e2eee7;color:#426f61;}
QListWidget#navigation {padding:0;}
QListWidget#navigation::item {height:31px;margin:3px 0;padding:9px 14px;color:#c1d2cb;border-radius:12px;}
QListWidget#navigation::item:selected {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #63877b,stop:1 #4b6b66);color:white;font-weight:500;}
QListWidget#navigation::item:hover:!selected {background:#3d5957;}
QListWidget#photos::item {border:1px solid transparent;padding:9px;}
QListWidget#photos::item:selected {border-color:#84ab98;background:#e8f2eb;}
QSlider::groove:horizontal {height:5px;background:#e1eae4;border-radius:2px;}
QSlider::sub-page:horizontal {background:#7ca38d;border-radius:2px;}
QSlider::handle:horizontal {background:white;border:3px solid #769d89;width:11px;height:11px;margin:-6px 0;border-radius:8px;}
QTabWidget::pane {border:0;background:transparent;}
QTabBar::tab {background:transparent;color:#82978d;padding:10px 25px;margin:0 5px 12px 0;border-radius:11px;}
QTabBar::tab:selected {background:#deebe2;color:#426b58;font-weight:500;}
QFrame#dropZone {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #f6f9f5,stop:1 #edf4ef);border:1px dashed #b5d0bf;border-radius:14px;}
QFrame#dropZone[dragging="true"] {background:#e0eee4;border:1px solid #85ab92;}
QLabel#dropTitle {color:#59816c;font-size:13px;font-weight:500;}
QLabel#dropHint {color:#8ba296;font-size:11px;}
QToolButton#calendarNav {padding:0;min-height:0;min-width:0;border:0;background:transparent;border-radius:8px;}
QToolButton#calendarNav:hover {background:#e1ece5;}
QPushButton#day {padding:3px;min-width:24px;border:0;background:transparent;}
QPushButton#day[selected="true"] {background:#e1ece5;color:#527b61;}
QToolTip {background:#2d4442;color:#f3f8f4;border:1px solid #48635c;border-radius:8px;padding:7px;}
'''.replace('__CHEVRON__',(ASSETS/'ui/chevron-down.svg').as_posix())

def icon(name,light=False):return QIcon(str(ASSETS/'icons'/('light' if light else 'dark')/(name+'.svg')))

def label(text,kind='fieldLabel'):
    w=QLabel(text);w.setObjectName(kind);return w

def card(title='',hint=''):
    w=QFrame();w.setObjectName('card');v=QVBoxLayout(w);v.setContentsMargins(20,18,20,18);v.setSpacing(12)
    if title:v.addWidget(label(title,'cardTitle'))
    return w,v

def segment(labels,callback,index=0):
    w=QWidget();h=QHBoxLayout(w);h.setContentsMargins(0,0,0,0);h.setSpacing(3);buttons=[]
    for i,text in enumerate(labels):
        b=QPushButton(text);b.setProperty('segment',True);b.setCheckable(True);b.setAutoExclusive(True);b.setChecked(i==index);b.clicked.connect(lambda checked=False,j=i:callback(j));h.addWidget(b);buttons.append(b)
    w.buttons=buttons;return w

class ToggleSwitch(QCheckBox):
    def __init__(self,text='',parent=None):
        super().__init__(text,parent);self._position=0.;self.animation=QVariantAnimation(self);self.animation.setDuration(150);self.animation.valueChanged.connect(self.update_position);self.toggled.connect(self.animate);self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFixedHeight(38)
    def sizeHint(self):return QSize(self.fontMetrics().horizontalAdvance(self.text())+64,38)
    def update_position(self,value):self._position=float(value);self.update()
    def animate(self,checked):
        self.animation.stop();self.animation.setStartValue(self._position);self.animation.setEndValue(1. if checked else 0.);self.animation.start()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setOpacity(1. if self.isEnabled() else .45)
        value=self._position;track=QColor('#739c86') if value>.5 else QColor('#d6e2da');p.setPen(Qt.PenStyle.NoPen);p.setBrush(track);p.drawRoundedRect(QRectF(0,7,40,24),12,12)
        p.setBrush(QColor('white'));p.drawEllipse(QRectF(3+16*value,10,18,18));p.setPen(self.palette().color(self.foregroundRole()));p.drawText(QRectF(52,0,self.width()-52,38),Qt.AlignmentFlag.AlignVCenter,self.text())
    def hitButton(self,pos):return self.rect().contains(pos)

class NumberField(QLineEdit):
    valueChanged=Signal(float)
    def __init__(self):
        super().__init__();self._value=0.;self._min=0.;self._max=99.;self._step=1.;self._decimals=2
        self.setAlignment(Qt.AlignmentFlag.AlignCenter);self.setFixedSize(86,38)
        self.validator_=QDoubleValidator(self);self.validator_.setLocale(QLocale.c());self.validator_.setNotation(QDoubleValidator.Notation.StandardNotation);self.setValidator(self.validator_)
        self.editingFinished.connect(self.commit);self.setValue(0)
    def setRange(self,a,b):self._min=a;self._max=b;self.validator_.setRange(a,b,self._decimals);self.setValue(self._value)
    def setSingleStep(self,value):self._step=value
    def setDecimals(self,value):self._decimals=value;self.validator_.setDecimals(value);self.setValue(self._value)
    def setValue(self,value):
        value=round(max(self._min,min(self._max,float(value))),self._decimals);changed=value!=self._value;self._value=value;self.setText(f'{value:.{self._decimals}f}')
        if changed:self.valueChanged.emit(value)
    def value(self):return self._value
    def commit(self):
        try:self.setValue(float(self.text()))
        except ValueError:self.setValue(self._value)
    def stepDown(self):self.commit();self.setValue(self._value-self._step)
    def stepUp(self):self.commit();self.setValue(self._value+self._step)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Up:self.stepUp();event.accept()
        elif event.key()==Qt.Key.Key_Down:self.stepDown();event.accept()
        else:super().keyPressEvent(event)

class Stepper(QWidget):
    valueChanged=Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedWidth(158);h=QHBoxLayout(self);h.setContentsMargins(0,0,0,0);h.setSpacing(4)
        self.number=NumberField();minus=QPushButton('−');plus=QPushButton('+')
        for b in [minus,plus]:b.setFixedSize(32,38);b.setStyleSheet('padding:0;');b.setCursor(Qt.CursorShape.PointingHandCursor)
        minus.clicked.connect(self.number.stepDown);plus.clicked.connect(self.number.stepUp);h.addWidget(minus);h.addWidget(self.number);h.addWidget(plus);self.number.valueChanged.connect(self.valueChanged)
    def setRange(self,a,b):self.number.setRange(a,b)
    def setSingleStep(self,value):self.number.setSingleStep(value)
    def setDecimals(self,value):self.number.setDecimals(value)
    def setValue(self,value):self.number.setValue(value)
    def value(self):return self.number.value()

class ShortcutDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(210,68)
    def paint(self,p,option,index):
        dark=bool(self.parent().window().property('darkTheme'));selected=bool(option.state&QStyle.StateFlag.State_Selected);hovered=bool(option.state&QStyle.StateFlag.State_MouseOver);p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);r=QRectF(option.rect).adjusted(1,2,-1,-2)
        p.setPen(QPen(QColor('#688f7d' if dark else '#bad5c4') if selected else QColor('#3a5148' if dark else '#e7eee8')));p.setBrush(QColor('#395b4d' if dark else '#e2eee5') if selected else QColor('#30483d' if dark else '#f6f9f5') if hovered else QColor('#263831' if dark else '#ffffff'));p.drawRoundedRect(r,12,12)
        tile=QRectF(r.x()+12,r.y()+13,36,36);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#d6e8db') if selected else QColor('#e9f1e9'));p.drawRoundedRect(tile,10,10)
        value=index.data(Qt.ItemDataRole.DecorationRole)
        if value:value.paint(p,int(tile.x()+8),int(tile.y()+8),20,20)
        font=QFont(option.font);font.setPixelSize(13);font.setBold(selected);p.setFont(font);p.setPen(QColor('#e3f0e8' if dark else '#4a725b') if selected else QColor('#c1d7c8' if dark else '#486454'));tx=r.x()+60;p.drawText(QRectF(tx,r.y()+10,r.width()-70,23),Qt.AlignmentFlag.AlignVCenter,p.fontMetrics().elidedText(index.data() or '',Qt.TextElideMode.ElideRight,int(r.width()-70)))
        font.setPixelSize(10);font.setBold(False);p.setFont(font);p.setPen(QColor('#8da492'));p.drawText(QRectF(tx,r.y()+33,r.width()-70,18),Qt.AlignmentFlag.AlignVCenter,index.data(Qt.ItemDataRole.UserRole) or '');p.restore()

def thumbnail(path):
    reader=QImageReader(str(path));reader.setAutoTransform(True)
    size=reader.size()
    if size.isValid():reader.setScaledSize(size.scaled(440,380,Qt.AspectRatioMode.KeepAspectRatio))
    pixmap=QPixmap.fromImage(reader.read())
    return QIcon(pixmap)

class PhotoDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return index.data(Qt.ItemDataRole.SizeHintRole) or QSize(160,180)
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r=QRectF(option.rect).adjusted(2,2,-2,-2)
        if option.state & QStyle.StateFlag.State_Selected:
            p.setBrush(QColor('#e2eee5'));p.setPen(QPen(QColor('#84ab98')));p.drawRoundedRect(r,12,12)
        ico=index.data(Qt.ItemDataRole.DecorationRole)
        if ico and not ico.isNull():
            pix=ico.pixmap(QSize(440,380));area=r.adjusted(7,7,-7,-7);size=pix.size().scaled(int(area.width()),int(area.height()),Qt.AspectRatioMode.KeepAspectRatio)
            dest=QRectF(area.center().x()-size.width()/2,area.center().y()-size.height()/2,size.width(),size.height())
            clip=QPainterPath();clip.addRoundedRect(dest,8,8);p.setClipPath(clip);p.drawPixmap(dest,pix,QRectF(pix.rect()))
        p.restore()

class UploadTile(QFrame):
    def __init__(self,title,hint,callback,filters,multiple=False,parent=None):
        super().__init__(parent);self.callback=callback;self.filters=filters;self.multiple=multiple;self.setObjectName('dropZone');self.setAcceptDrops(True);self.setCursor(Qt.CursorShape.PointingHandCursor);self.setMinimumHeight(92);self.setProperty('dragging',False)
        v=QHBoxLayout(self);v.setContentsMargins(17,12,17,12);v.setSpacing(13);mark=QLabel();mark.setPixmap(icon('plus').pixmap(22,22));mark.setFixedSize(38,38);mark.setStyleSheet('background:#dfece0;border-radius:12px;');mark.setAlignment(Qt.AlignmentFlag.AlignCenter);v.addWidget(mark)
        texts=QVBoxLayout();texts.setSpacing(5);self.title=label(title,'dropTitle');self.title.setWordWrap(True);self.hint=label(hint,'dropHint');self.hint.setWordWrap(True);texts.addWidget(self.title);self.hint.hide();v.addLayout(texts,1)
        for child in [mark,self.title,self.hint]:child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def valid_paths(self,paths):return [str(Path(p)) for p in paths if Path(p).is_file() and (not self.filters or Path(p).suffix.lower() in self.filters)]
    def open_picker(self):
        pattern=' '.join('*'+x for x in sorted(self.filters)) if self.filters else '*'
        if self.multiple:paths,_=QFileDialog.getOpenFileNames(self,'파일 선택','',f'지원 파일 ({pattern});;모든 파일 (*)')
        else:
            path,_=QFileDialog.getOpenFileName(self,'파일 선택','',f'지원 파일 ({pattern});;모든 파일 (*)');paths=[path] if path else []
        paths=self.valid_paths(paths)
        if paths:self.callback(paths)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.open_picker();event.accept()
        else:super().mousePressEvent(event)
    def _highlight(self,active):self.setProperty('dragging',active);self.style().unpolish(self);self.style().polish(self)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and self.valid_paths([u.toLocalFile() for u in event.mimeData().urls()]):self._highlight(True);event.acceptProposedAction()
    def dragLeaveEvent(self,event):self._highlight(False)
    def dropEvent(self,event):
        self._highlight(False);paths=self.valid_paths([u.toLocalFile() for u in event.mimeData().urls()]);paths=paths if self.multiple else paths[:1]
        if paths:self.callback(paths);event.acceptProposedAction()

class AspectPreview(QLabel):
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#e7eeea'));p.drawRoundedRect(QRectF(self.rect()),12,12)
        pix=self.pixmap()
        if pix is not None and not pix.isNull():
            size=pix.size().scaled(max(1,self.width()-16),max(1,self.height()-16),Qt.AspectRatioMode.KeepAspectRatio);dest=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height());p.drawPixmap(dest,pix,QRectF(pix.rect()))

class ColorPlane(QWidget):
    colorChanged=Signal(QColor)
    def __init__(self,color,parent=None):
        super().__init__(parent);self.hue=max(0,color.hsvHue());self.sat=color.hsvSaturationF();self.val=color.valueF();self.setMinimumSize(250,160);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.setCursor(Qt.CursorShape.CrossCursor)
    def color(self):return QColor.fromHsvF(self.hue/359.,self.sat,self.val)
    def setColor(self,color):
        self.hue=max(0,color.hsvHue())
        self.sat=color.hsvSaturationF();self.val=color.valueF();self.update();self.colorChanged.emit(self.color())
    def setHue(self,value):self.hue=value;self.update();self.colorChanged.emit(self.color())
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);r=QRectF(self.rect()).adjusted(1,1,-1,-1);clip=QPainterPath();clip.addRoundedRect(r,8,8);p.setClipPath(clip);p.fillRect(r,QColor.fromHsv(self.hue,255,255));white=QLinearGradient(r.left(),0,r.right(),0);white.setColorAt(0,QColor('white'));white.setColorAt(1,QColor(255,255,255,0));p.fillRect(r,white);black=QLinearGradient(0,r.top(),0,r.bottom());black.setColorAt(0,QColor(0,0,0,0));black.setColorAt(1,QColor('black'));p.fillRect(r,black)
        x=r.left()+r.width()*self.sat;y=r.top()+r.height()*(1-self.val);p.setClipping(False);p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#ffffff'),2));p.drawEllipse(QRectF(x-5,y-5,10,10));p.setPen(QPen(QColor('#344742'),1));p.drawEllipse(QRectF(x-6,y-6,12,12))
    def pick(self,pos):
        self.sat=max(0.,min(1.,(pos.x()-1)/max(1,self.width()-2)));self.val=1-max(0.,min(1.,(pos.y()-1)/max(1,self.height()-2)));self.update();self.colorChanged.emit(self.color())
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.setFocus();self.pick(event.position())
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MouseButton.LeftButton:self.pick(event.position())
    def keyPressEvent(self,event):
        step=.01
        if event.key()==Qt.Key.Key_Left:self.sat=max(0,self.sat-step)
        elif event.key()==Qt.Key.Key_Right:self.sat=min(1,self.sat+step)
        elif event.key()==Qt.Key.Key_Up:self.val=min(1,self.val+step)
        elif event.key()==Qt.Key.Key_Down:self.val=max(0,self.val-step)
        else:return super().keyPressEvent(event)
        self.update();self.colorChanged.emit(self.color())

class PaletteDialog(QDialog):
    def __init__(self,color,parent=None,title='색상 선택'):
        super().__init__(parent);from font_config import settings_font;self.setFont(settings_font());self.setWindowTitle(title);self.setStyleSheet(parent.styleSheet() if parent else STYLE);self.setFixedSize(370,540);self.selected=QColor(color);v=QVBoxLayout(self);v.setContentsMargins(22,22,22,22);v.setSpacing(14);v.addWidget(label(title,'cardTitle'));grid=QGridLayout();grid.setSpacing(7)
        self.plane=ColorPlane(color);self.hue=HueWheel(max(0,color.hsvHue()));self.hue.hueChanged.connect(self.plane.setHue);self.plane.colorChanged.connect(self.changed_color)
        for i,value in enumerate(['#f2f7fb','#e1ece5','#dce9fa','#d8ece7','#fae2e5','#f8eaca','#ffffff','#c2b0e1','#95acd7','#89b7ad','#d3a3b4','#d2bd90','#263543','#39334c','#242436','#4f4370','#705d82','#a086d7']):
            b=QPushButton();b.setFixedSize(42,27);b.setStyleSheet(f'background:{value};border:1px solid #d2dfd7;border-radius:7px;');b.clicked.connect(lambda checked=False,c=value:self.select_swatch(QColor(c)));grid.addWidget(b,i//6,i%6)
        v.addLayout(grid);field=QHBoxLayout();field.setSpacing(12);field.addWidget(self.plane,1);v.addWidget(self.hue);v.addLayout(field,1);self.preview=QFrame();self.preview.setFixedHeight(25);v.addWidget(self.preview)
        h=QHBoxLayout();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);ok=QPushButton('선택');ok.setObjectName('primary');ok.clicked.connect(self.accept);h.addStretch();h.addWidget(cancel);h.addWidget(ok);v.addLayout(h);self.changed_color(color)
    def changed_color(self,color):self.selected=QColor(color);self.preview.setStyleSheet(f'background:{color.name()};border:1px solid #b6c9bd;border-radius:7px;')
    def select_swatch(self,color):self.hue.blockSignals(True);self.hue.hue=max(0,color.hsvHue());self.hue.update();self.hue.blockSignals(False);self.plane.setColor(color)

def choose_color(color,parent,title):
    dialog=PaletteDialog(color,parent,title);return dialog.selected if dialog.exec() else QColor()

DARK_OVERRIDES='''
QWidget {color:#dae7e3;}
QDialog#settingsWindow,QDialog {background:#182325;}
QFrame#card {background:#223033;border-color:#344649;}
QFrame#previewCard,QFrame#dropZone {background:#293a3c;border-color:#46615d;}
QLabel#heading,QLabel#cardTitle {color:#e7f0ec;}
QLabel#fieldLabel,QLabel#sub,QLabel#dropTitle {color:#a9c2b9;}
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:#1c292c;color:#dfebe5;border-color:#415854;selection-background-color:#527b70;selection-color:white;}
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus {background:#263638;border-color:#8eb9a6;}
QComboBox QAbstractItemView {background:#223033;color:#dfebe5;selection-background-color:#44665d;selection-color:white;}
QPushButton,QToolButton {background:#304440;color:#dfebe5;border-color:#48625a;}
QPushButton:hover,QToolButton:hover {background:#405c51;color:white;}
QPushButton:disabled {background:#273432;color:#83978f;}
QPushButton#primary {background:#7fae9b;color:#152b25;border-color:#91bfad;}
QPushButton#primary:hover {background:#9dc7b6;color:#152b25;}
QPushButton#primary:disabled {background:#293e35;color:#849d90;border-color:#3f584c;}
QPushButton[segment="true"] {color:#a6bbb3;background:transparent;}
QPushButton[segment="true"]:checked {background:#46685c;color:white;}
QListWidget::item {color:#bbcdc5;}
QListWidget::item:selected,QTabBar::tab:selected {background:#3d5d51;color:#e5f1eb;}
QLabel#statusPill {background:#365046;color:#c4dfd0;}
QToolButton#iconChoice {background:#293c34;}
QToolButton#iconChoice:checked {background:#527665;border-color:#a3c5b0;}
QScrollBar::handle:vertical {background:#526b61;}
'''
def settings_style(dark=False):return STYLE+(DARK_OVERRIDES if dark else '')

class HueWheel(QWidget):
    hueChanged=Signal(int)
    def __init__(self,hue=0,parent=None):
        super().__init__(parent);self.hue=hue;self.setFixedHeight(126);self.setCursor(Qt.CursorShape.CrossCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def setValue(self,value):self.hue=max(0,min(359,int(value)));self.update();self.hueChanged.emit(self.hue)
    def paintEvent(self,event):
        from PySide6.QtGui import QConicalGradient
        import math
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);c=self.rect().center();g=QConicalGradient(c,0)
        for i in range(13):g.setColorAt(i/12,QColor.fromHsv(round(i/12*359),255,255))
        p.setPen(QPen(g,22));p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(c,48,48)
        a=self.hue/359*math.tau;p.setPen(QPen(QColor('white'),3));p.drawEllipse(QRectF(c.x()+48*math.cos(a)-7,c.y()-48*math.sin(a)-7,14,14))
    def pick(self,pos):
        import math
        c=self.rect().center();self.hue=round((math.atan2(c.y()-pos.y(),pos.x()-c.x())/math.tau%1)*359);self.update();self.hueChanged.emit(self.hue)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:self.pick(e.position())
    def mouseMoveEvent(self,e):
        if e.buttons()&Qt.MouseButton.LeftButton:self.pick(e.position())
    def keyPressEvent(self,e):
        if e.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):self.hue=(self.hue+(1 if e.key()==Qt.Key.Key_Right else -1))%360;self.update();self.hueChanged.emit(self.hue)
        else:super().keyPressEvent(e)
