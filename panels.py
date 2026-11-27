from __future__ import annotations
import copy
from datetime import date
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QTimer,QSize
from PySide6.QtGui import QDesktopServices,QColor,QIcon,QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QLabel,QPushButton,
 QComboBox,QCheckBox,QSlider,QSpinBox,QDoubleSpinBox,QListWidget,QStackedWidget,QWidget,
 QFileDialog,QMessageBox,QPlainTextEdit,QLineEdit,QDialogButtonBox,QAbstractItemView,QScrollArea,QColorDialog,
 QProgressBar,QFrame,QGridLayout,QToolButton,QSizePolicy,QListWidgetItem,QTabWidget,QStyleFactory,QApplication)
from state import WIDGETS
from font_config import settings_font
from panel_ui import STYLE as PANEL_STYLE,ToggleSwitch,Stepper,AspectPreview,PhotoDelegate,ShortcutDelegate,UploadTile,card,label,icon,segment,thumbnail,choose_color,settings_style

STYLE=PANEL_STYLE
NAMES={'clock':'시계','photos':'사진','player':'음악','memo':'메모','calendar':'달력 · 일정','dock':'바로가기','visualizer':'오디오 비주얼라이저','system':'시스템 모니터','focus':'집중 타이머'}

def button(text,callback,primary=False):
    b=QPushButton(text);b.clicked.connect(callback)
    if primary:b.setObjectName('primary')
    return b

def heading(layout,title,sub=''):
    row=QHBoxLayout();left=QVBoxLayout();left.setSpacing(8);left.addWidget(label(title,'heading'))
    row.addLayout(left,1);layout.addLayout(row);layout.addSpacing(8)

def page(title,sub='',scroll=True):
    w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(26,12,8,6);v.setSpacing(16);heading(v,title,sub)
    if not scroll:return w,v
    content,body=card();area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.Shape.NoFrame);area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);area.setWidget(content);v.addWidget(area,1)
    return w,body

FileDropZone=UploadTile
QCheckBox=ToggleSwitch

class CalendarPickerDialog(QDialog):
    def __init__(self,value,parent=None):
        super().__init__(parent);self.setWindowTitle('날짜 선택');self.setModal(True);self.resize(330,340);self.selected=QDate(value);self.month=QDate(value.year(),value.month(),1);self.setStyleSheet(parent.window().styleSheet() if parent else STYLE)
        root=QVBoxLayout(self);root.setContentsMargins(18,18,18,18);root.setSpacing(12)
        header=QHBoxLayout();prev=QToolButton();prev.setObjectName('calendarNav');prev.setFixedSize(28,28);prev.setIcon(icon('chevron-left'));prev.clicked.connect(self.prev_month);header.addWidget(prev)
        self.month_label=QLabel();self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.month_label.setStyleSheet('font-size:17px;font-weight:650;');header.addWidget(self.month_label,1)
        nxt=QToolButton();nxt.setObjectName('calendarNav');nxt.setFixedSize(28,28);nxt.setIcon(icon('chevron-right'));nxt.clicked.connect(self.next_month);header.addWidget(nxt);root.addLayout(header)
        days=QGridLayout();days.setSpacing(4)
        for col,name in enumerate(['일','월','화','수','목','금','토']):
            label=QLabel(name);label.setAlignment(Qt.AlignmentFlag.AlignCenter);label.setStyleSheet('color:#7a8a8c;font-weight:600;');days.addWidget(label,0,col)
        self.day_buttons=[]
        for i in range(42):
            b=QPushButton('');b.setObjectName('day');b.setFixedSize(38,32);b.clicked.connect(lambda checked=False,idx=i:self.choose_day(idx));self.day_buttons.append(b);days.addWidget(b,1+i//7,i%7)
        root.addLayout(days)
        foot=QHBoxLayout();today=QPushButton('오늘');today.clicked.connect(self.choose_today);foot.addWidget(today);foot.addStretch();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);foot.addWidget(cancel);root.addLayout(foot)
        self.refresh()
    def refresh(self):
        self.month_label.setText(f'{self.month.year()}년 {self.month.month()}월')
        first=(self.month.dayOfWeek()%7);count=self.month.daysInMonth()
        for i,b in enumerate(self.day_buttons):
            day=i-first+1;valid=1<=day<=count;b.setVisible(valid)
            if valid:
                current=QDate(self.month.year(),self.month.month(),day);b.setText(str(day));b.setProperty('selected',current==self.selected);b.style().unpolish(b);b.style().polish(b)
    def prev_month(self):self.month=self.month.addMonths(-1);self.refresh()
    def next_month(self):self.month=self.month.addMonths(1);self.refresh()
    def choose_day(self,index):
        day=index-(self.month.dayOfWeek()%7)+1
        if 1<=day<=self.month.daysInMonth():self.selected=QDate(self.month.year(),self.month.month(),day);self.accept()
    def choose_today(self):self.selected=QDate.currentDate();self.accept()

class DatePickerButton(QPushButton):
    def __init__(self,value=None,parent=None):
        super().__init__(parent);self.value=QDate(value or QDate.currentDate());self.setText(self.value.toString('yyyy.MM.dd'));self.clicked.connect(self.pick)
    def pick(self):
        dialog=CalendarPickerDialog(self.value,self)
        if dialog.exec():self.value=dialog.selected;self.setText(self.value.toString('yyyy.MM.dd'))

class Settings(QDialog):
    def __init__(self,bridge,app):
        super().__init__();self.b=bridge;self.app=app;bridge._settings=self;app.setStyle(QStyleFactory.create('Fusion'))
        self.setFont(settings_font());self.setObjectName('settingsWindow');self.setWindowTitle('한로로 바탕화면 위젯');g=app.primaryScreen().availableGeometry()
        self.setMinimumSize(min(960,g.width()-24),min(640,g.height()-24));self.resize(min(1220,g.width()-48),min(840,g.height()-48));self.setStyleSheet(STYLE)
        self.task_state_timer=QTimer(self);self.task_state_timer.setSingleShot(True);self.task_state_timer.setInterval(300);self.task_state_timer.timeout.connect(self.b.refresh_state)
        root=QHBoxLayout(self);root.setContentsMargins(16,16,20,16);root.setSpacing(0)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(210);left=QVBoxLayout(side);left.setContentsMargins(15,24,15,18);left.setSpacing(14)
        self.nav=QListWidget();self.nav.setObjectName('navigation');self.nav.setIconSize(QSize(18,18));self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for text,glyph in [('시작 · 화면','home'),('배경','image'),('위젯','settings'),('바로가기','app'),('가구 · 사진','room'),('업데이트','download')]:self.nav.addItem(QListWidgetItem(icon(glyph,True),text))
        left.addWidget(self.nav,1);root.addWidget(side)
        self.stack=QStackedWidget();root.addWidget(self.stack,1)
        self.general();self.media();self.layout_page();self.music();self.shortcuts();self.notes();self.backups();self.extras();self.room();self.update_page()
        self.nav_routes=[0,1,2,4,8,9]
        self.nav.currentRowChanged.connect(lambda i:self.stack.setCurrentIndex(self.nav_routes[i]) if i>=0 else None);self.nav.setCurrentRow(0)
        self.b.stateChanged.connect(self.refresh_theme);self.b.mediaImported.connect(self.imported_background);self.refresh_theme()
    def imported_background(self):
        self.mode.blockSignals(True);self.mode.setCurrentIndex(1 if self.b.store.data['backgroundMode']=='video' else 0);self.mode.blockSignals(False)
        self.wallpaper_rotation.blockSignals(True);self.wallpaper_rotation.setChecked(self.b.store.data['wallpaperRotation']);self.wallpaper_rotation.blockSignals(False);self.refresh_wallpaper_list();self.refresh_wallpaper_preview()
    def refresh_theme(self):
        dark=self.b.store.data['theme']=='night'
        if getattr(self,'_dark_style',None)!=dark:self._dark_style=dark;self.setProperty('darkTheme',dark);self.setStyleSheet(settings_style(dark));self.refresh_theme_icons(dark)
    def refresh_theme_icons(self,dark):
        if hasattr(self,'icon_buttons'):
            for glyph,b in self.icon_buttons.items():b.setIcon(icon(glyph,dark))
        if hasattr(self,'link_list'):self.link_list.viewport().update()
    def open_page(self,index):
        self.nav.setCurrentRow(self.nav_routes.index(index) if index in self.nav_routes else -1)
        self.stack.setCurrentIndex(index)
    def add(self,w):self.stack.addWidget(w)
    def general(self):
        d=self.b.store.data;w,v=page('화면','배경과 위젯의 표시 방식을 설정합니다. 변경 사항은 자동 저장됩니다.')
        form=QFormLayout();form.setSpacing(18)
        self.theme=QCheckBox('다크 모드');self.theme.setChecked(d['theme']=='night');self.theme.toggled.connect(lambda active:self.b.set_option('theme','night' if active else 'apricot'));form.addRow(self.theme)
        self.mode=QComboBox();self.mode.addItems(['사진','영상']);self.mode.setCurrentIndex(1 if d['backgroundMode']=='video' else 0)
        self.mode.currentIndexChanged.connect(lambda i:self.b.set_option('backgroundMode',['image','video'][i]));form.addRow('배경',self.mode)
        screens=QComboBox();screens.addItems([s.name() for s in self.app.screens()]);idx=screens.findText(d['screen']);screens.setCurrentIndex(max(0,idx));screens.currentTextChanged.connect(self.change_screen);form.addRow('모니터',screens)
        dim=QSlider(Qt.Orientation.Horizontal);dim.setRange(0,85);dim.setValue(int(d['dim']*100));dim.valueChanged.connect(lambda n:self.b.set_option('dim',n/100));form.addRow('배경 어둡기',dim);v.addLayout(form)
        quick=QHBoxLayout();quick.addWidget(button('음악 연결',lambda:self.open_page(3)));quick.addWidget(button('데이터 백업',lambda:self.open_page(6)));v.addLayout(quick)
        reactive=QCheckBox('오디오 비주얼라이저');reactive.setChecked(d['audioReactive']);reactive.toggled.connect(lambda value:self.b.set_option('audioReactive',value));v.addWidget(reactive)
        motion=QCheckBox('애니메이션');motion.setChecked(d['motion']);motion.toggled.connect(lambda x:self.b.set_option('motion',x));v.addWidget(motion)
        auto=QCheckBox('Windows에 로그인하면 자동 실행');auto.setChecked(self.b.autostart_enabled());auto.setEnabled(__import__('sys').platform=='win32');auto.toggled.connect(self.autostart);v.addWidget(auto)
        hide=QCheckBox('적용 중 바탕화면 아이콘 숨기기');hide.setChecked(d['hideDesktopIcons']);hide.toggled.connect(lambda value:self.b.set_option('hideDesktopIcons',value));v.addWidget(hide)
        fonts=QComboBox();fonts.addItems(['둥근체','기본체','몽글체']);fonts.setCurrentIndex(['round','clean','soft'].index(d['fontPreset']));fonts.currentIndexChanged.connect(lambda i:self.b.set_option('fontPreset',['round','clean','soft'][i]));form2=QFormLayout();form2.addRow('글꼴',fonts);v.addLayout(form2)
        if __import__('os').environ.get('HANRORO_SKIP_CUSTOM_FONTS')=='1' or (self.b.store.directory/'font-loading.json').exists():
            note=QLabel('글꼴 호환 실행 중 · 기본 글꼴을 사용합니다.');note.setObjectName('sub');v.addWidget(note)
        v.addStretch();row=QHBoxLayout();row.addWidget(button('바탕화면에 적용',self.apply_desktop,True));row.addWidget(button('미리보기 창',self.b.previewMode));v.addLayout(row);v.addWidget(button('이전 Windows 배경 복원',self.b.restoreBackground));self.add(w)
    def apply_desktop(self):
        self.b.desktopMode()
        if self.b.desktop:self.hide()
    def change_screen(self,name):
        self.b.set_option('screen',name)
        if self.b.desktop:self.b.desktopMode()
    def autostart(self,enabled):
        try:self.b.set_autostart(enabled)
        except OSError as e:QMessageBox.warning(self,'자동 실행',str(e))
    def media(self):
        w,v=page('바탕화면 배경',scroll=False)
        quality=QComboBox();quality.addItems(['4K 고화질','화면 해상도']);quality.setCurrentIndex(0 if self.b.store.data.get('wallpaperQuality','4k')=='4k' else 1);quality.currentIndexChanged.connect(lambda i:self.b.set_option('wallpaperQuality','4k' if i==0 else 'native'));v.addWidget(quality)

        preview,pv=card();self.wallpaper_preview=AspectPreview();self.wallpaper_preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.wallpaper_preview.setMinimumSize(300,130);self.wallpaper_preview.setMaximumHeight(210);self.wallpaper_preview.setStyleSheet('background:#e7eeea;border-radius:12px;');pv.addWidget(self.wallpaper_preview,1)
        self.background_name=label('','sub');pv.addWidget(self.background_name);v.addWidget(preview,1)
        choices=QHBoxLayout();choices.addWidget(FileDropZone('바탕화면 사진 선택','',lambda paths:self.b.importBackground(paths,False),{'.jpg','.jpeg','.png','.webp','.bmp'},True));choices.addWidget(FileDropZone('바탕화면 영상 선택','',lambda paths:self.b.importBackground(paths,True),{'.mp4','.webm','.mov','.mkv'}));v.addLayout(choices)
        row=QHBoxLayout();row.addWidget(label('화면 맞춤'));self.wallpaper_fit=QComboBox();self.wallpaper_fit.addItems(['채우기','맞추기']);self.wallpaper_fit.setCurrentIndex(0 if self.b.store.data.get('wallpaperFit','fill')=='fill' else 1);self.wallpaper_fit.currentIndexChanged.connect(lambda i:self.change_wallpaper_fit(['fill','fit'][i]));row.addWidget(self.wallpaper_fit,1);row.addWidget(button('바탕화면에 적용',self.apply_desktop,True));v.addLayout(row)
        control=QHBoxLayout();self.wallpaper_rotation=ToggleSwitch('사진 순환');self.wallpaper_rotation.setChecked(self.b.store.data['wallpaperRotation']);self.wallpaper_rotation.toggled.connect(lambda enabled:self.b.set_option('wallpaperRotation',enabled));control.addWidget(self.wallpaper_rotation);control.addStretch();control.addWidget(button('위로',lambda:self.move_wallpaper(-1)));control.addWidget(button('아래로',lambda:self.move_wallpaper(1)));control.addWidget(button('삭제',self.remove_wallpaper));v.addLayout(control)
        self.wallpaper_list=QListWidget();self.wallpaper_list.setMinimumHeight(150);self.wallpaper_list.setSpacing(5);v.addWidget(self.wallpaper_list,1);self.refresh_wallpaper_list()
        self._background_preview_key=None;self.b.stateChanged.connect(self.refresh_wallpaper_preview);self.refresh_wallpaper_preview();self.add(w)
    def add_wallpaper_paths(self,paths):
        try:
            from PySide6.QtGui import QImageReader
            rows=self.b.store.data['wallpaperSlides']
            for path in paths:
                if len(rows)>=200:break
                if not QImageReader(str(path)).canRead():raise ValueError('읽을 수 없는 사진입니다: '+Path(path).name)
                saved=self.b.store.ingest(path)
                if not any(row['path']==saved for row in rows):rows.append({'path':saved,'seconds':30})
            if rows:self.b.store.data['imageBackground']=rows[-1]['path']
            self.b.store.data['backgroundMode']='image';self.mode.setCurrentIndex(0)
            self.b.store.data['wallpaperRotation']=len(rows)>1;self.wallpaper_rotation.setChecked(len(rows)>1)
            self.b.wallpaper_slides_changed();self.refresh_wallpaper_list()
        except (OSError,ValueError) as error:QMessageBox.warning(self,'사진 추가',str(error))
    def refresh_wallpaper_list(self):
        selected=self.wallpaper_list.currentRow();self.wallpaper_list.clear()
        for index,entry in enumerate(self.b.store.data['wallpaperSlides']):
            item=QListWidgetItem();item.setSizeHint(QSize(200,64));self.wallpaper_list.addItem(item)
            row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(10,4,10,4)
            image=QLabel();image.setPixmap(thumbnail(entry['path']).pixmap(48,48));image.setFixedSize(52,52);layout.addWidget(image)
            name=label(Path(entry['path']).name);name.setToolTip(entry['path']);layout.addWidget(name,1)
            seconds=Stepper();seconds.setDecimals(0);seconds.setRange(1,86400);seconds.setValue(entry['seconds']);seconds.valueChanged.connect(lambda value,i=index:self.wallpaper_duration(i,value));layout.addWidget(seconds);layout.addWidget(label('초'))
            self.wallpaper_list.setItemWidget(item,row)
        if self.wallpaper_list.count():self.wallpaper_list.setCurrentRow(max(0,min(selected,self.wallpaper_list.count()-1)))
    def wallpaper_duration(self,index,value):
        rows=self.b.store.data['wallpaperSlides']
        if 0<=index<len(rows):rows[index]['seconds']=max(1,min(86400,int(value)));self.b.set_slide_timer();self.b.changed()
    def move_wallpaper(self,offset):
        index=self.wallpaper_list.currentRow();rows=self.b.store.data['wallpaperSlides'];target=index+offset
        if 0<=index<len(rows) and 0<=target<len(rows):
            rows[index],rows[target]=rows[target],rows[index];self.b.wallpaper_slides_changed();self.refresh_wallpaper_list();self.wallpaper_list.setCurrentRow(target)
    def remove_wallpaper(self):
        index=self.wallpaper_list.currentRow();rows=self.b.store.data['wallpaperSlides']
        if 0<=index<len(rows):
            removed=rows.pop(index)
            if self.b.store.data['imageBackground']==removed['path']:self.b.store.data['imageBackground']=rows[0]['path'] if rows else ''
            self.b.wallpaper_slides_changed();self.refresh_wallpaper_list()
    def change_wallpaper_fit(self,fit):self.b.set_option('wallpaperFit',fit);self.refresh_wallpaper_preview()
    def refresh_wallpaper_preview(self):
        if not hasattr(self,'wallpaper_preview'):return
        data=self.b.store.data;key=(self.b.active_wallpaper(),data['videoBackground'],data['backgroundMode'],data.get('wallpaperFit','fill'),data['dim'],data['theme'])
        if key==self._background_preview_key:return
        self._background_preview_key=key
        pix=QPixmap(str(self.b.wallpaper_path()));self.wallpaper_preview.setPixmap(pix.scaled(800,350,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        path=data['videoBackground'] if data['backgroundMode']=='video' else self.b.active_wallpaper();self.background_name.setText(Path(path).name if path else '기본 배경')
    def use_photo_background(self):
        index=self.photo_list.currentRow()
        if 0<=index<len(self.b.store.data['photos']):self.set_background(self.b.store.data['photos'][index],False)

    def refresh_photos(self):
        if not hasattr(self,'photo_list'):return
        selected=self.photo_list.currentRow();self.photo_list.clear()
        for i,path in enumerate(self.b.store.data['photos']):
            image=thumbnail(path);size=image.actualSize(QSize(220,190));item=QListWidgetItem(image,'');item.setToolTip(Path(path).name);item.setSizeHint(QSize(max(40,size.width())+20,max(40,size.height())+20));self.photo_list.addItem(item)
        if self.photo_list.count():self.photo_list.setCurrentRow(max(0,min(selected,self.photo_list.count()-1)))

    def add_photos(self):
        paths,_=QFileDialog.getOpenFileNames(self,'사진 추가','','사진 (*.jpg *.jpeg *.png *.webp *.bmp)')
        self.add_photo_paths(paths)
    def add_photo_paths(self,paths):
        try:
            for p in paths:
                new=self.b.store.ingest(p)
                if new not in self.b.store.data['photos']:self.b.store.data['photos'].append(new)
            self.b.changed();self.b.photoChanged.emit();self.refresh_photos()
        except (OSError,ValueError) as e:QMessageBox.warning(self,'사진 추가',str(e))
    def remove_photos(self):
        for i in sorted([self.photo_list.row(it) for it in self.photo_list.selectedItems()],reverse=True):self.b.store.data['photos'].pop(i)
        self.b.changed();self.b.photoChanged.emit();self.refresh_photos()
    def choose_background(self,video):
        filters={'.mp4','.webm','.mov','.mkv'} if video else {'.jpg','.jpeg','.png','.webp','.bmp'}
        pattern=' '.join('*'+suffix for suffix in sorted(filters))
        p,_=QFileDialog.getOpenFileName(self,'배경 선택','',f'지원 파일 ({pattern})')
        if p:self.set_background(p,video)
    def set_background(self,path,video):
        try:
            self.b.store.data['videoBackground' if video else 'imageBackground']=self.b.store.ingest(path);
            if not video:self.b.store.data['wallpaperRotation']=False;self.wallpaper_rotation.setChecked(False)
            self.b.set_option('backgroundMode','video' if video else 'image');self.mode.setCurrentIndex(1 if video else 0)
        except (OSError,ValueError) as e:QMessageBox.warning(self,'배경',str(e))
    def layout_page(self):
        w,v=page('위젯',scroll=False);tabs=QTabWidget();v.addWidget(tabs,1)
        display=QWidget();dv=QVBoxLayout(display);dv.setContentsMargins(4,8,4,8);dv.setSpacing(14)
        row=QHBoxLayout();presets=QComboBox();presets.addItems(['왼쪽','오른쪽','하단']);presets.setCurrentIndex(['left','right','bottom'].index(self.b.store.data['layoutPreset']));presets.currentIndexChanged.connect(lambda i:self.b.applyLayout(['left','right','bottom'][i]));row.addWidget(presets);row.addWidget(button('바탕화면에서 배치',self.b.toggleEdit,True));dv.addLayout(row)
        form=QFormLayout();form.setSpacing(12);self.widget_checks={};self.widget_spins={};self.color_buttons={}
        for key in WIDGETS:
            if key in ('photos','visualizer'):continue
            check=QCheckBox(NAMES[key]);check.setChecked(self.b.store.data['widgets'][key]['visible']);check.toggled.connect(lambda value,k=key:self.visibility(k,value));self.widget_checks[key]=check
            row=QHBoxLayout();row.addWidget(check,1);spin=Stepper();spin.setRange(.45,1.8);spin.setSingleStep(.05);spin.setDecimals(2);spin.setValue(self.b.store.data['widgets'][key]['scale']);self.widget_spins[key]=spin;spin.valueChanged.connect(lambda value,k=key:self.b.scaleWidget(k,value));row.addWidget(spin)
            swatch=button('색',lambda _,k=key:self.widget_color(k));self.color_buttons[key]=swatch;row.addWidget(swatch);form.addRow(row)
        dv.addLayout(form);more=QHBoxLayout();more.addWidget(button('음악 연결',lambda:self.open_page(3)));more.addWidget(button('메모 · 일정',lambda:self.open_page(5)));more.addWidget(button('집중 타이머',lambda:self.open_page(7)));dv.addLayout(more);dv.addStretch();dv.addWidget(button('배치 초기화',self.reset_layout));tabs.addTab(display,'표시 · 배치')
        colors=QWidget();cv=QVBoxLayout(colors);cv.setSpacing(16);cv.addWidget(button('전체 위젯 색',self.global_color));cv.addWidget(button('강조 색',self.accent_color));opacity=QSlider(Qt.Orientation.Horizontal);opacity.setRange(35,100);opacity.setValue(round(self.b.store.data['widgetOpacity']*100));opacity.valueChanged.connect(lambda n:self.b.set_option('widgetOpacity',n/100));cv.addWidget(label('불투명도'));cv.addWidget(opacity);cv.addWidget(button('기본 색으로 복원',self.reset_colors));cv.addStretch();tabs.addTab(colors,'색상')
        lighting_box,lv=card('밤 조명');lighting=QCheckBox('밤 조명');lighting.setChecked(self.b.store.data['nightLighting']);lighting.toggled.connect(lambda enabled:self.b.set_option('nightLighting',enabled));lv.addWidget(lighting);lv.addStretch();tabs.addTab(lighting_box,'밤 조명');self.add(w)
    def global_color(self):
        color=choose_color(QColor(self.b.store.data['widgetColor'] or '#f2f7fb'),self,'위젯 색상')
        if color.isValid():self.b.set_option('widgetColor',color.name())
    def accent_color(self):
        color=choose_color(QColor(self.b.store.data['accentColor']),self,'강조 색상')
        if color.isValid():self.b.set_option('accentColor',color.name())
    def widget_color(self,key):
        color=choose_color(QColor(self.b.store.data['widgets'][key].get('color') or '#f2f7fb'),self,NAMES[key]+' 색상')
        if color.isValid():self.b.setWidgetColor(key,color.name())
    def reset_colors(self):
        self.b.store.data['widgetColor']='';self.b.store.data['accentColor']='#edb8b4'
        for row in self.b.store.data['widgets'].values():row['color']=''
        self.b.changed()
    def visibility(self,key,value):self.b.store.data['widgets'][key]['visible']=value;self.b.changed()
    def reset_layout(self):
        self.b.store.data['widgets']=copy.deepcopy(WIDGETS);self.b.changed()
        for k,c in self.widget_checks.items():
            c.blockSignals(True);c.setChecked(WIDGETS[k]['visible']);c.blockSignals(False)
            spin=self.widget_spins[k];spin.blockSignals(True);spin.setValue(WIDGETS[k]['scale']);spin.blockSignals(False)
    def music(self):
        w,v=page('음악 앱 연결')
        self.media_source=QComboBox();self.media_source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.media_source.setMinimumContentsLength(24);self.media_source.currentIndexChanged.connect(self.select_music_source)
        v.addWidget(self.media_source);v.addWidget(button('새로고침',self.b.media.refresh))
        now,nv=card('현재 곡');self.now_cover=QLabel();self.now_cover.setFixedSize(140,140);self.now_cover.setAlignment(Qt.AlignmentFlag.AlignCenter);nv.addWidget(self.now_cover)
        self.now_title=label('','cardTitle');self.now_artist=label('','sub');self.media_status=label('','sub');self.media_status.setWordWrap(True)
        nv.addWidget(self.now_title);nv.addWidget(self.now_artist);nv.addWidget(self.media_status);controls=QHBoxLayout()
        self.previous_music=button('이전 곡',self.b.previousTrack);self.toggle_music=button('재생',self.b.playPause,True);self.next_music=button('다음 곡',self.b.nextTrack)
        for control in [self.previous_music,self.toggle_music,self.next_music]:controls.addWidget(control)
        nv.addLayout(controls);v.addWidget(now);apps=QHBoxLayout();apps.addWidget(button('Spotify 열기',lambda:QDesktopServices.openUrl(QUrl('spotify:'))));apps.addWidget(button('SoundCloud 열기',lambda:QDesktopServices.openUrl(QUrl('https://soundcloud.com/'))));v.addLayout(apps);v.addStretch()
        self._music_choices=None;self._now_cover=None;self.b.musicChanged.connect(self.refresh_music);self.refresh_music();self.add(w)
    def select_music_source(self,index):
        source=self.media_source.itemData(index)
        if source is not None:self.b.select_media_source(source)
    def refresh_music(self):
        if not hasattr(self,'media_source'):return
        data=self.b.media.data;preferred=self.b.store.data.get('mediaSource','');choices=[('자동 선택','')]+[(r['name'],r['id']) for r in data['sessions']]
        if preferred and not any(value==preferred for _,value in choices):
            from media_worker import app_name
            choices.append((app_name(preferred)+' · 연결 대기',preferred))
        if (choices,preferred)!=self._music_choices:
            self.media_source.blockSignals(True);self.media_source.clear()
            for name,value in choices:self.media_source.addItem(name,value)
            self.media_source.setCurrentIndex(max(0,self.media_source.findData(preferred)));self.media_source.blockSignals(False);self._music_choices=(choices,preferred)
        self.now_title.setText(self.b.trackTitle);self.now_artist.setText(self.b.trackArtist);self.media_status.setText(data['error'] or (data['sourceName'] if data['connected'] else '음악 앱에서 먼저 재생하세요.'))
        if data['cover']!=self._now_cover:
            self._now_cover=data['cover'];pix=QPixmap(QUrl(data['cover']).toLocalFile()) if data['cover'] else QPixmap();self.now_cover.setPixmap(pix.scaled(140,140,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation) if not pix.isNull() else QPixmap());self.now_cover.setVisible(not pix.isNull())
        self.toggle_music.setText('일시정지' if self.b.playing else '재생');self.toggle_music.setEnabled(self.b.canPlayPause);self.next_music.setEnabled(self.b.canNext);self.previous_music.setEnabled(self.b.canPrevious)
    def shortcuts(self):
        self._loading_link=False
        w,v=page('바로가기','자주 쓰는 앱과 링크를 모아두세요. 선택한 버튼만 오른쪽에서 수정해요.',scroll=False)
        columns=QHBoxLayout();columns.setSpacing(16);library,lv=card('내 버튼');library.setMinimumWidth(230);library.setMaximumWidth(290)
        head=QHBoxLayout();self.link_count=label('','statusPill');head.addWidget(self.link_count);head.addStretch();head.addWidget(button('+ 새 버튼',self.new_link));lv.addLayout(head)
        self.link_search=QLineEdit();self.link_search.setPlaceholderText('버튼 검색');self.link_search.textChanged.connect(self.filter_links);lv.addWidget(self.link_search)
        self.link_list=QListWidget();self.link_list.setItemDelegate(ShortcutDelegate(self.link_list));self.link_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.link_list.setMouseTracking(True);lv.addWidget(self.link_list,1)
        moves=QHBoxLayout();moves.addWidget(button('↑',lambda:self.reorder_link(-1)));moves.addWidget(button('↓',lambda:self.reorder_link(1)));moves.addStretch();delete=button('삭제',self.delete_link);delete.setObjectName('danger');moves.addWidget(delete);lv.addLayout(moves);columns.addWidget(library,1)
        editor_widget=QWidget();ev=QVBoxLayout(editor_widget);ev.setContentsMargins(0,0,0,0);ev.setSpacing(12)
        self.link_preview_icon=QLabel(self);self.link_preview_title=QLabel(self);self.link_preview_type=QLabel(self)
        for hidden in (self.link_preview_icon,self.link_preview_title,self.link_preview_type):hidden.hide()
        content=QWidget();cv=QVBoxLayout(content);cv.setContentsMargins(0,0,0,0);cv.setSpacing(12)
        identity,iv=card('이름과 연결');self.link_title=QLineEdit();self.link_title.setPlaceholderText('버튼 이름');iv.addWidget(self.link_title)
        self.link_mode=segment(['앱','웹사이트','파일 · 폴더','기능'],self.switch_link_mode);iv.addWidget(self.link_mode)
        self.link_target=QLineEdit();self.link_target.setPlaceholderText('https://example.com');iv.addWidget(self.link_target)
        self.target_stack=QStackedWidget()
        apps=QWidget();av=QVBoxLayout(apps);av.setContentsMargins(0,0,0,0);av.setSpacing(8);av.addWidget(button('설치된 앱에서 선택',self.pick_app,True));app_drop=FileDropZone('앱 파일 놓기','EXE · LNK',self.set_link_paths,{'.exe','.lnk'});app_drop.setMinimumHeight(58);av.addWidget(app_drop);self.target_stack.addWidget(apps)
        web=QWidget();self.target_stack.addWidget(web)
        files=QWidget();fv=QVBoxLayout(files);fv.setContentsMargins(0,0,0,0);fr=QHBoxLayout();fr.addWidget(button('파일 선택',self.browse_link));fr.addWidget(button('폴더 선택',self.browse_folder));fv.addLayout(fr);fv.addWidget(FileDropZone('파일 놓기','파일을 놓거나 눌러서 선택',self.set_link_paths,set()));self.target_stack.addWidget(files)
        funcs=QWidget();fun=QVBoxLayout(funcs);fun.setContentsMargins(0,0,0,0);self.action_combo=QComboBox();self.action_combo.addItem('기능 선택…','')
        for text,target in [('설정','action:settings'),('메모','action:memo'),('일정','action:events'),('배경 변경','action:background'),('재생 앱 연결','action:music'),('위젯 편집','action:edit'),('버튼 관리','action:shortcuts'),('바탕화면 보기','action:desktop'),('휴지통','action:recyclebin'),('다운로드 폴더','special:downloads'),('문서 폴더','special:documents'),('음악 폴더','special:music')]:self.action_combo.addItem(text,target)
        self.action_combo.currentIndexChanged.connect(self.set_action);fun.addWidget(self.action_combo);self.target_stack.addWidget(funcs);iv.addWidget(self.target_stack);cv.addWidget(identity)
        looks,look=card('아이콘');self.link_glyph=QComboBox();glyphs=['home','camera','folder','music','globe','play','star','app','download','calendar','image','edit','plus','settings','trash'];self.link_glyph.addItems(glyphs);self.link_glyph.hide();self.link_icon='';self.icon_name=label('기본 아이콘','sub');self.icon_buttons={};grid=QGridLayout();grid.setSpacing(7)
        for i,glyph in enumerate(glyphs):
            b=QToolButton();b.setObjectName('iconChoice');b.setCheckable(True);b.setAutoExclusive(True);b.setFixedSize(36,36);b.setIcon(icon(glyph));b.setIconSize(QSize(19,19));b.setToolTip(glyph);b.clicked.connect(lambda checked=False,g=glyph:self.link_glyph.setCurrentText(g));self.icon_buttons[glyph]=b;grid.addWidget(b,i//7,i%7)
        look.addLayout(grid);ir=QHBoxLayout();ir.addWidget(self.icon_name,1);ir.addWidget(button('이미지로 변경',self.browse_icon));look.addLayout(ir);cv.addWidget(looks);cv.addStretch()
        form=QScrollArea();form.setFrameShape(QFrame.Shape.NoFrame);form.setWidgetResizable(True);form.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);form.setWidget(content);ev.addWidget(form,1)
        footer=QHBoxLayout();self.link_feedback=label('','sub');footer.addWidget(self.link_feedback,1);self.link_save=button('새 버튼 추가',self.submit_link,True);footer.addWidget(self.link_save);ev.addLayout(footer);columns.addWidget(editor_widget,2);v.addLayout(columns,1)
        self.link_glyph.currentTextChanged.connect(self.reset_link_icon);self.link_title.textChanged.connect(self.update_link_preview);self.link_target.textChanged.connect(self.update_link_preview);self.link_list.currentRowChanged.connect(self.select_link);self.refresh_links();self.new_link();self.add(w)
    def filter_links(self,text):
        for i in range(self.link_list.count()):self.link_list.item(i).setHidden(text.casefold() not in self.link_list.item(i).text().casefold())
    def switch_link_mode(self,index):
        if index!=self.target_stack.currentIndex():
            self.link_target.clear();self.action_combo.setCurrentIndex(0)
        self.set_link_mode(index);self.update_link_preview()
    def set_link_mode(self,index):
        self.target_stack.setCurrentIndex(index);self.link_target.setVisible(index==1)
        for i,b in enumerate(self.link_mode.buttons):b.setChecked(i==index)
    def new_link(self):
        self.link_list.setCurrentRow(-1);self.link_title.clear();self.link_target.clear();self.link_glyph.setCurrentText('home');self.link_icon='';self.icon_name.setText('기본 아이콘');self.link_feedback.clear();self.link_save.setText('새 버튼 추가');self.set_link_mode(0);self.update_link_preview()
    def submit_link(self):
        if self.link_list.currentRow()<0:self.add_link()
        else:self.save_link()
    def update_link_preview(self,*_):
        if not hasattr(self,'link_preview_title') or not hasattr(self,'link_glyph'):return
        self.link_preview_title.setText(self.link_title.text().strip() or '새 버튼');target=self.link_target.text().strip()
        kind='웹사이트' if target.startswith(('http:','https:')) else '앱' if target.startswith('app:') else '기능' if target.startswith(('action:','special:')) else '파일 · 폴더' if target else ''
        self.link_preview_type.setText(kind);self.link_preview_icon.setPixmap((QIcon(self.link_icon) if self.link_icon else icon(self.link_glyph.currentText())).pixmap(24,24))
        for key,b in self.icon_buttons.items():b.setChecked(key==self.link_glyph.currentText() and not self.link_icon)
        self.link_save.setEnabled(bool(self.link_title.text().strip() and target))

    def refresh_links(self):
        self.link_list.blockSignals(True);self.link_list.clear()
        for row in self.b.store.data['links']:
            target=row['target'];kind='웹사이트' if target.startswith(('http:','https:')) else '앱' if target.startswith('app:') else '기능' if target.startswith(('action:','special:')) else '파일 · 폴더'
            item=QListWidgetItem(QIcon(row['icon']) if row.get('icon') else icon(row.get('glyph','app')),row['title']);item.setData(Qt.ItemDataRole.UserRole,kind);item.setToolTip(target);self.link_list.addItem(item)
        self.link_list.blockSignals(False);self.link_count.setText(str(self.link_list.count())+' / 64');self.filter_links(self.link_search.text())

    def select_link(self,i):
        if not 0<=i<len(self.b.store.data['links']):return
        self._loading_link=True;r=self.b.store.data['links'][i];target=r['target'];self.link_title.setText(r['title']);self.link_target.setText(target);self.link_glyph.setCurrentText(r['glyph']);self.link_icon=r.get('icon','');self.icon_name.setText('사용자 이미지' if self.link_icon else '기본 아이콘');self._loading_link=False
        self.set_link_mode(1 if target.startswith(('http:','https:')) else 0 if target.startswith('app:') else 3 if target.startswith(('action:','special:')) else 2)
        self.action_combo.blockSignals(True);self.action_combo.setCurrentIndex(max(0,self.action_combo.findData(target)));self.action_combo.blockSignals(False)
        self.link_save.setText('변경 저장');self.link_feedback.clear();self.update_link_preview()

    def set_action(self,index):
        target=self.action_combo.itemData(index)
        if target:
            self.link_target.setText(target);self.link_title.setText(self.action_combo.itemText(index))
            if target=='action:recyclebin':self.link_glyph.setCurrentText('trash')
    def pick_app(self):
        from app_picker import AppPicker
        dialog=AppPicker(self)
        if dialog.exec() and dialog.selected:
            row=dialog.selected;self.link_title.setText(row['name']);self.link_target.setText(row.get('path') or row['target']);self.link_glyph.setCurrentText('app');self.link_icon='';self.icon_name.setText('기본 아이콘');self.set_link_mode(0);self.update_link_preview()
    def set_link_paths(self,paths):
        if not paths:return
        path=paths[0];self.link_target.setText(path);self.link_title.setText(Path(path).stem);self.link_glyph.setCurrentText('app');self.update_link_preview()
    def browse_link(self):
        p,_=QFileDialog.getOpenFileName(self,'파일 또는 바로가기 선택','','모든 파일 (*)')
        if p:self.link_target.setText(p);self.link_title.setText(Path(p).stem)
    def browse_folder(self):
        p=QFileDialog.getExistingDirectory(self,'폴더 선택')
        if p:self.link_target.setText(p);self.link_title.setText(Path(p).name);self.link_glyph.setCurrentText('folder')
    def reset_link_icon(self,*_):
        if self._loading_link:return
        self.link_icon='';self.icon_name.setText('기본 아이콘');self.update_link_preview()

    def set_icon_paths(self,paths):
        if not paths:return
        try:self.link_icon=self.b.store.ingest(paths[0]);self.icon_name.setText('사용자 이미지');self.update_link_preview()
        except OSError as error:QMessageBox.warning(self,'아이콘',str(error))
    def browse_icon(self):
        p,_=QFileDialog.getOpenFileName(self,'버튼 아이콘','','아이콘 (*.png *.jpg *.jpeg *.webp *.svg *.ico)')
        if p:
            try:self.link_icon=self.b.store.ingest(p);self.icon_name.setText('사용자 이미지');self.update_link_preview()
            except OSError as error:QMessageBox.warning(self,'아이콘',str(error))
    def link_data(self):return {'title':self.link_title.text().strip(),'target':self.link_target.text().strip(),'glyph':self.link_glyph.currentText(),'icon':self.link_icon}
    def add_link(self):
        r=self.link_data()
        if not r['title'] or not r['target']:self.link_feedback.setText('이름과 연결 대상을 선택하세요.');return
        if len(self.b.store.data['links'])>=64:QMessageBox.information(self,'버튼','최대 64개까지 추가할 수 있습니다.');return
        self.b.store.data['links'].append(r);self.b.changed();self.refresh_links();self.link_list.setCurrentRow(len(self.b.store.data['links'])-1);self.link_feedback.setText('버튼을 추가했어요.')
    def save_link(self):
        i=self.link_list.currentRow();r=self.link_data()
        if 0<=i<len(self.b.store.data['links']) and r['title'] and r['target']:self.b.store.data['links'][i]=r;self.b.changed();self.refresh_links();self.link_list.setCurrentRow(i);self.link_feedback.setText('저장했어요.')
    def delete_link(self):
        i=self.link_list.currentRow()
        if i>=0:self.b.store.data['links'].pop(i);self.b.changed();self.refresh_links();self.new_link()
    def reorder_link(self,step):
        i=self.link_list.currentRow();j=i+step;rows=self.b.store.data['links']
        if 0<=i<len(rows) and 0<=j<len(rows):rows[i],rows[j]=rows[j],rows[i];self.b.changed();self.refresh_links();self.link_list.setCurrentRow(j)
    def notes(self):
        w,root=page('메모 · 일정','메모, 할 일, 일정을 탭으로 나누어 관리하세요.',scroll=False)
        tabs=QTabWidget();root.addWidget(tabs,1)
        memo_page,v=card('바탕화면 메모');tabs.addTab(memo_page,'메모')
        memo_label=QLabel('메모');memo_label.setStyleSheet('font-size:16px;font-weight:650;');v.addWidget(memo_label)
        self.memo=QPlainTextEdit(self.b.store.data['memo']);self.memo.setPlaceholderText('바탕화면 메모에 표시할 내용을 적어주세요.');self.memo.setMinimumHeight(110);self.memo.textChanged.connect(lambda:self.b.set_option('memo',self.memo.toPlainText()));v.addWidget(self.memo)
        task_page,v=card('할 일과 상세 내용','할 일을 선택하면 내용을 수정할 수 있어요.');tabs.addTab(task_page,'할 일')
        task_label=QLabel('할 일');task_label.setStyleSheet('font-size:16px;font-weight:650;');v.addWidget(task_label)
        self.tasks=QListWidget();self.tasks.setMinimumHeight(110);self.refresh_tasks();v.addWidget(self.tasks)
        task_row=QHBoxLayout();self.task_title_input=QLineEdit();self.task_title_input.setPlaceholderText('할 일 제목');task_row.addWidget(self.task_title_input,1)
        task_row.addWidget(button('추가',self.add_task,True));task_row.addWidget(button('삭제',self.delete_task));v.addLayout(task_row)
        self.task_detail_input=QPlainTextEdit();self.task_detail_input.setPlaceholderText('선택한 할 일의 상세 내용');self.task_detail_input.setMinimumHeight(110);v.addWidget(self.task_detail_input)
        v.addWidget(FileDropZone('할 일 첨부 파일','클릭하거나 파일을 끌어놓으세요. (첨부 파일은 할 일별로 보관)',self.attach_task_files,{'.png','.jpg','.jpeg','.webp','.pdf','.txt','.docx','.xlsx','.mp4','.mp3'} ,True))
        event_page,v=card('다가오는 일정');tabs.addTab(event_page,'일정')
        event_label=QLabel('일정');event_label.setStyleSheet('font-size:16px;font-weight:650;');v.addWidget(event_label)
        self.events=QListWidget();self.events.setMinimumHeight(100);self.refresh_events();v.addWidget(self.events);self.events.itemDoubleClicked.connect(self.open_event_attachment)
        self.event_title=QLineEdit();self.event_title.setPlaceholderText('공연 · 기념일 이름')
        self.event_date=DatePickerButton(QDate.currentDate())
        row=QHBoxLayout();row.addWidget(self.event_title,1);row.addWidget(self.event_date);v.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('일정 추가',self.add_event,True));row.addWidget(button('선택 일정 삭제',self.delete_event));v.addLayout(row)
        self.event_attachment=''
        v.addWidget(FileDropZone('일정 첨부 파일','포스터 · 티켓 · 이미지 · PDF를 끌어놓거나 눌러서 선택',self.attach_event_files,{'.png','.jpg','.jpeg','.webp','.pdf','.txt'},False))
        self.add(w)
        self.tasks.currentRowChanged.connect(self.load_task_detail)
        self.task_detail_input.textChanged.connect(self.save_task_detail)
    def refresh_tasks(self):
        if not hasattr(self,'tasks'):return
        self.tasks.blockSignals(True);self.tasks.clear()
        for task in self.b.store.data['tasks']:
            self.tasks.addItem(('완료 · ' if task.get('done') else '')+(task.get('title') or task.get('text') or '할 일'))
        self.tasks.blockSignals(False)
    def add_task(self):
        title=self.task_title_input.text().strip()
        if not title:return
        self.b.addTask(title,self.task_detail_input.toPlainText());self.task_title_input.clear();self.task_detail_input.blockSignals(True);self.task_detail_input.clear();self.task_detail_input.blockSignals(False);self.refresh_tasks();self.tasks.setCurrentRow(self.b.store.data.get('selectedTask',-1))
    def load_task_detail(self,index):
        self.task_detail_input.blockSignals(True)
        task=self.b.store.data['tasks'][index] if 0<=index<len(self.b.store.data['tasks']) else {}
        self.task_detail_input.setPlainText(task.get('detail',''))
        self.task_detail_input.blockSignals(False)
        self.b.selectTask(index if index>=0 else -1)
    def save_task_detail(self):
        index=self.tasks.currentRow()
        if 0<=index<len(self.b.store.data['tasks']):
            self.b.store.data['tasks'][index]['detail']=self.task_detail_input.toPlainText()[:12000];self.b.debounce.start();self.b.invalidate_state();self.task_state_timer.start()
    def attach_task_files(self,paths):
        index=self.tasks.currentRow()
        if not 0<=index<len(self.b.store.data['tasks']):
            self.b.toast.emit('먼저 할 일을 선택하세요.');return
        try:
            task=self.b.store.data['tasks'][index];task.setdefault('attachments',[])
            for path in paths:
                stored=self.b.store.ingest(path)
                if stored not in task['attachments']:task['attachments'].append(stored)
            self.b.changed();self.b.toast.emit(f'{len(paths)}개 파일을 첨부했습니다.')
        except (OSError,ValueError) as error:QMessageBox.warning(self,'첨부 파일',str(error))
    def delete_task(self):
        index=self.tasks.currentRow()
        if 0<=index<len(self.b.store.data['tasks']):
            self.b.store.data['tasks'].pop(index);self.b.store.data['selectedTask']=-1;self.b.changed();self.refresh_tasks();self.task_detail_input.blockSignals(True);self.task_detail_input.clear();self.task_detail_input.blockSignals(False)
    def refresh_events(self):
        if not hasattr(self,'events'):return
        self.events.clear();self.events.addItems([r['date']+'  '+r['title'] for r in self.b.store.data['events']])
    def add_event(self):
        text=self.event_title.text().strip()
        if text:
            row={'title':text[:200],'date':self.event_date.value.toString('yyyy-MM-dd')}
            if self.event_attachment:row['attachment']=self.event_attachment
            self.b.store.data['events'].append(row);self.event_title.clear();self.event_attachment='';self.b.changed();self.refresh_events()
    def open_event_attachment(self,*_):
        index=self.events.currentRow()
        if 0<=index<len(self.b.store.data['events']):
            path=self.b.store.data['events'][index].get('attachment','')
            if path and Path(path).is_file():QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    def attach_event_files(self,paths):
        if not paths:return
        try:self.event_attachment=self.b.store.ingest(paths[0]);self.b.toast.emit('일정 첨부 파일을 준비했습니다.')
        except (OSError,ValueError) as error:QMessageBox.warning(self,'일정 첨부',str(error))
    def delete_event(self):
        i=self.events.currentRow()
        if i>=0:self.b.store.data['events'].pop(i);self.b.changed();self.refresh_events()
    def update_page(self):
        from release_info import VERSION
        w,v=page('업데이트');v.addWidget(label('현재 버전  '+VERSION,'heading'))
        self.update_status=label('','sub');self.update_status.setWordWrap(True);v.addWidget(self.update_status)
        self.update_notes=QPlainTextEdit();self.update_notes.setReadOnly(True);self.update_notes.setMaximumHeight(180);self.update_notes.setPlaceholderText('새 버전의 변경 내용');v.addWidget(self.update_notes)
        self.update_progress=QProgressBar();self.update_progress.setRange(0,100);v.addWidget(self.update_progress)
        row=QHBoxLayout();self.update_check=button('업데이트 확인',self.b.updates.check);row.addWidget(self.update_check);self.update_apply=button('업데이트',self.apply_update,True);row.addWidget(self.update_apply);self.update_cancel=button('취소',self.b.updates.cancel);row.addWidget(self.update_cancel);v.addLayout(row)
        self.update_auto_check=QCheckBox('새 버전 자동 확인');self.update_auto_check.setChecked(self.b.store.data['updatesAutoCheck']);self.update_auto_check.toggled.connect(lambda active:self.b.set_option('updatesAutoCheck',active));v.addWidget(self.update_auto_check)
        self.update_auto_install=QCheckBox('자동 다운로드 · 설치');self.update_auto_install.setChecked(self.b.store.data['updatesAutoInstall']);self.update_auto_install.setToolTip('알림 후 15초 뒤 설치합니다. 입력·배치 편집 중에는 기다립니다.');self.update_auto_install.toggled.connect(self.set_auto_install);self.update_auto_check.setEnabled(not self.update_auto_install.isChecked());v.addWidget(self.update_auto_install);v.addWidget(button('알림 미리보기',self.b.previewUpdateNotice));self.auto_diagnostic=label('','sub');self.auto_diagnostic.setWordWrap(True);v.addWidget(self.auto_diagnostic);v.addStretch();self.b.updates.changed.connect(self.refresh_update);self.refresh_update();self.add(w)
    def set_auto_install(self,active):
        self.b.set_option('updatesAutoInstall',active)
        self.update_auto_check.setEnabled(not active)
        if active:self.update_auto_check.setChecked(True)
    def apply_update(self):
        if self.b.updates.data['status']=='ready':self.b.updates.install()
        else:self.b.updates.download()
    def refresh_update(self):
        updater=self.b.updates
        self.auto_diagnostic.setText(('자동 확인 '+updater.auto_checked+'  '+(updater.auto_error or '완료')) if updater.auto_checked else ('자동 확인 대기 중' if self.b.store.data['updatesAutoCheck'] else '자동 확인 꺼짐'))
        data=self.b.updates.data;status=data['status'];busy=status in ('checking','downloading','installing')
        text={'idle':'새 버전을 확인할 수 있어요.','checking':'새 버전 확인 중…','current':'최신 버전입니다.','available':'새 버전 '+data.get('version','')+'이 있어요.','downloading':'업데이트 다운로드 중…','ready':'설치 준비가 끝났습니다.','installing':'설치 후 앱이 다시 실행됩니다.','error':data.get('message','업데이트 확인에 실패했습니다.')}
        self.update_status.setText(text.get(status,''));self.update_progress.setVisible(status in ('downloading','ready','installing'));self.update_progress.setValue(data.get('progress',0));
        if self.update_notes.toPlainText()!=data.get('notes',''):self.update_notes.setPlainText(data.get('notes',''))
        self.update_check.setEnabled(not busy);self.update_apply.setEnabled(status in ('available','ready'));self.update_cancel.setVisible(status=='downloading')
    def room(self):
        from room_items import CATALOG
        w,v=page('가구 · 사진');catalog=QTabWidget();catalog.setObjectName('furnitureCatalog')
        order=['desk','chair','sofa','armchair','coffee_table','side_table','bed','shelf','wardrobe','drawers','vinyl_rack','record_crate','lamp','pendant','string_lights','candle','plant','vase','books','mug','fan','speaker','rug','curtain','mirror']
        for group in ['가구','수납','조명','식물','소품','패브릭 · 벽']:
            tab=QWidget();grid=QGridLayout(tab);grid.setSpacing(8);index=0
            for kind in order:
                spec=CATALOG[kind]
                if spec['group']!=group:continue
                tile=QToolButton();tile.setText(spec['title']);tile.clicked.connect(lambda checked=False,k=kind:self.b.addFurniture(k));tile.setObjectName('addFurniture_'+kind);tile.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon);tile.setIcon(QIcon(str(self.b.assets/'furniture'/(kind+'.svg'))));tile.setIconSize(QSize(70,52));tile.setMinimumHeight(96);tile.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed);tile.setStyleSheet('QToolButton {background:#eaf0ed;border:1px solid #dbe6e1;border-radius:12px;padding:8px;color:#365852;} QToolButton:hover {background:#dae9e2;} QToolButton:pressed {background:#c9ded3;}');grid.addWidget(tile,index//3,index%3);index+=1
            grid.setRowStretch((index+2)//3,1);catalog.addTab(tab,'패브릭' if group=='패브릭 · 벽' else group)
        v.addWidget(catalog);v.addWidget(FileDropZone('사진 액자 추가','',self.b.add_room_photos,{'.jpg','.jpeg','.png','.webp','.bmp'}));v.addWidget(button('바탕화면에서 배치',self.edit_room,True))
        self.room_list=QListWidget();self.room_list.setMinimumHeight(150);self.room_list.currentRowChanged.connect(self.select_room_item);v.addWidget(self.room_list)
        self.room_controls=QWidget();form=QFormLayout(self.room_controls);form.setContentsMargins(0,0,0,0);form.setSpacing(12)
        self.room_scale=Stepper();self.room_scale.setRange(.25,2);self.room_scale.setDecimals(2);self.room_scale.setSingleStep(.1);self.room_scale.valueChanged.connect(lambda value:self.room_adjust('scale',value));form.addRow('크기',self.room_scale)
        self.room_rotation=Stepper();self.room_rotation.setRange(-180,180);self.room_rotation.setDecimals(0);self.room_rotation.setSingleStep(15);self.room_rotation.valueChanged.connect(lambda value:self.room_adjust('rotation',value));form.addRow('회전',self.room_rotation)
        order=QHBoxLayout();order.addWidget(button('위젯 앞으로',lambda:self.room_adjust('z',10)));order.addWidget(button('위젯 뒤로',lambda:self.room_adjust('z',-20)));order.addWidget(button('좌우 반전',lambda:self.room_action('flip')));form.addRow('겹침 순서',order)
        self.room_lock=QCheckBox('위치 고정');self.room_lock.toggled.connect(self.room_lock_changed);form.addRow('',self.room_lock)
        self.room_animation=QCheckBox('움직임');self.room_animation.toggled.connect(self.room_animation_changed);form.addRow('',self.room_animation)
        v.addWidget(self.room_controls);v.addWidget(button('선택 항목 삭제',lambda:self.room_action('delete')));self.b.decorationsChanged.connect(self.refresh_room);self.refresh_room();self.add(w)
    def edit_room(self):
        if not self.b.editMode:self.b.toggleEdit()
        self.hide()
    def selected_room_item(self):
        index=self.room_list.currentRow();rows=self.b.store.data['decorations'];return rows[index] if 0<=index<len(rows) else None
    def refresh_room(self):
        if not hasattr(self,'room_list'):return
        from room_items import CATALOG
        selected=self.room_list.currentItem();identity=selected.data(Qt.ItemDataRole.UserRole) if selected else '';self.room_list.blockSignals(True);self.room_list.clear()
        for row in self.b.store.data['decorations']:
            entry=QListWidgetItem(CATALOG[row['kind']]['title']+('  ·  고정' if row['locked'] else ''));entry.setData(Qt.ItemDataRole.UserRole,row['id']);self.room_list.addItem(entry)
        index=next((i for i,row in enumerate(self.b.store.data['decorations']) if row['id']==identity),len(self.b.store.data['decorations'])-1);self.room_list.setCurrentRow(index);self.room_list.blockSignals(False);self.select_room_item(index)
    def select_room_item(self,index):
        row=self.selected_room_item();self.room_controls.setEnabled(row is not None)
        from room_items import CATALOG
        self.room_animation.setVisible(bool(row and CATALOG[row['kind']].get('motion')))
        if row:
            self.room_animation.blockSignals(True);self.room_animation.setChecked(row.get('animate',True));self.room_animation.blockSignals(False)
            for control,key in [(self.room_scale,'scale'),(self.room_rotation,'rotation'),(self.room_lock,'locked')]:
                control.blockSignals(True)
                if key=='locked':control.setChecked(row[key])
                else:control.setValue(row[key]);control.setEnabled(not row['locked'])
                control.blockSignals(False)
    def room_adjust(self,field,value):
        row=self.selected_room_item()
        if row:self.b.adjustDecoration(row['id'],field,value)
    def room_step(self,field,delta):
        row=self.selected_room_item()
        if row:self.b.adjustDecoration(row['id'],field,row[field]+delta)
    def room_action(self,action):
        row=self.selected_room_item()
        if row:self.b.actionDecoration(row['id'],action)
    def room_animation_changed(self,active):
        row=self.selected_room_item()
        if row and row.get('animate',True)!=active:self.b.actionDecoration(row['id'],'animate')
    def room_lock_changed(self,locked):
        row=self.selected_room_item()
        if row and row['locked']!=locked:self.b.actionDecoration(row['id'],'lock')
    def extras(self):
        w,v=page('집중 타이머');tabs=QTabWidget();self.extras_tabs=tabs;v.addWidget(tabs)
        focus=QWidget();fv=QVBoxLayout(focus);fv.setContentsMargins(16,20,16,16);fv.setSpacing(18);tabs.addTab(focus,'집중 타이머')
        form=QFormLayout();form.setSpacing(16);t=self.b.store.data['focusTimer']
        self.focus_minutes=Stepper();self.focus_minutes.setRange(1,180);self.focus_minutes.setDecimals(0);self.focus_minutes.setSingleStep(1);self.focus_minutes.setValue(t['minutes']);self.focus_minutes.valueChanged.connect(lambda n:self.b.features_controller.set_duration(int(n)));form.addRow('시간 · 분',self.focus_minutes)
        self.alarm_mode=QComboBox();self.alarm_mode.addItems(['기본 알람음','내 파일']);self.alarm_mode.setCurrentIndex(1 if t['alarmMode']=='file' else 0);self.alarm_mode.currentIndexChanged.connect(lambda n:self.alarm_option('alarmMode','file' if n else 'bell'));form.addRow('알람 소리',self.alarm_mode)
        volume=QSlider(Qt.Orientation.Horizontal);volume.setRange(0,100);volume.setValue(round(t['alarmVolume']*100));volume.valueChanged.connect(lambda n:self.alarm_option('alarmVolume',n/100));form.addRow('알람 음량',volume);fv.addLayout(form)
        fv.addWidget(FileDropZone('알람 파일 선택','',self.set_alarm_file,{'.mp4','.mp3','.wav','.flac','.m4a','.ogg','.webm','.aac'}));self.alarm_file_name=label(Path(t['alarmFile']).name if t['alarmFile'] else '','sub');fv.addWidget(self.alarm_file_name)
        row=QHBoxLayout();row.addWidget(button('소리 듣기',self.b.features_controller.play_alarm));row.addWidget(button('소리 끄기',self.b.features_controller.stop_alarm));fv.addLayout(row)
        row=QHBoxLayout();row.addWidget(button('시작 · 일시정지',self.b.timerToggle,True));row.addWidget(button('초기화',self.b.timerReset));fv.addLayout(row)
        self.focus_status=label('','sub');fv.addWidget(self.focus_status);fv.addStretch();self.b.featureChanged.connect(self.refresh_focus)
        self.refresh_focus();self.add(w)
    def refresh_focus(self):
        if not hasattr(self,'focus_status'):return
        value=self.b.features_controller.snapshot();self.focus_status.setText(value['label']+('  ·  진행 중' if value['running'] else ''))
        self.focus_minutes.blockSignals(True);self.focus_minutes.setValue(value['minutes']);self.focus_minutes.blockSignals(False)
    def alarm_option(self,key,value):
        self.b.store.data['focusTimer'][key]=value;self.b.debounce.start()
    def set_alarm_file(self,paths):
        if not paths:return
        try:
            path=self.b.store.ingest(paths[0]);self.alarm_option('alarmFile',path);self.alarm_mode.setCurrentIndex(1);self.alarm_file_name.setText(Path(path).name)
        except (OSError,ValueError) as error:QMessageBox.warning(self,'알람 파일',str(error))
    def backups(self):
        w,v=page('저장 · 복원','위젯 배치와 미디어를 테마 파일로 저장합니다.')
        v.addWidget(button('테마 내보내기',self.export_scene,True));v.addWidget(button('테마 가져오기',self.import_scene));v.addWidget(button('설정 폴더 열기',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.b.store.directory)))))
        v.addStretch();v.addWidget(button('닫기',self.close));self.add(w)
    def export_scene(self):
        path,_=QFileDialog.getSaveFileName(self,'테마 보관','','한로로 테마 (*.hanroom)')
        if not path:return
        try:self.b.store.export_scene(path,self.b.assets);QMessageBox.information(self,'보관 완료','테마를 저장했습니다.')
        except (OSError,ValueError) as e:QMessageBox.warning(self,'보관 실패',str(e))
    def import_scene(self):
        path,_=QFileDialog.getOpenFileName(self,'테마 가져오기','','한로로 테마 (*.hanroom)')
        if not path:return
        if QMessageBox.question(self,'테마 가져오기','현재 배치와 설정을 가져온 테마로 바꾸시겠습니까?')!=QMessageBox.StandardButton.Yes:return
        try:
            self.b.store.import_scene(path);self.b.features_controller.reload();self.b.room_changed();self.b.media.select(self.b.store.data.get('mediaSource',''));self.b._photo_index=0;self.b.set_slide_timer();self.b.changed();self.b.photoChanged.emit();self.b.musicChanged.emit();self.close();self.deleteLater();self.b._settings=None
        except Exception as e:QMessageBox.warning(self,'가져오기 실패',str(e))
    def show_section(self,index):
        self.refresh_photos();self.refresh_music();self.refresh_tasks();self.refresh_events()
        self.memo.blockSignals(True);self.memo.setPlainText(self.b.store.data['memo']);self.memo.blockSignals(False)
        for key,check in self.widget_checks.items():
            check.blockSignals(True);check.setChecked(self.b.store.data['widgets'][key]['visible']);check.blockSignals(False)
            spin=self.widget_spins[key];spin.blockSignals(True);spin.setValue(self.b.store.data['widgets'][key]['scale']);spin.blockSignals(False)
        self.refresh_wallpaper_preview();self.refresh_room()
        if index==7:self.extras_tabs.setCurrentIndex(0)
        self.open_page(index);self.show();self.raise_();self.activateWindow()
