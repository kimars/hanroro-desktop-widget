"""Windows shell metadata/icon extraction. Called only in a killable helper process."""
import base64,ctypes,hashlib,ntpath,os,re,sys,uuid
from pathlib import Path

def norm(value):return ntpath.normcase(ntpath.normpath(os.path.expandvars(str(value)))) if value else ''

def matching_windows(row,windows):
    from shell_groups import explorer
    if explorer(row):return [w for w in windows if explorer(w)]
    target=str(row.get('target','')).casefold();appid=target[4:] if target.startswith('app:') else ''
    exact=[w for w in windows if appid and str(w.get('app_id','')).casefold()==appid]
    if exact:return exact
    paths={norm(p) for p in row.get('executables',[]) if p}
    for key in ('exe','path'):
        value=row.get(key,'')
        if ntpath.splitext(str(value))[1].lower()=='.exe':paths.add(norm(value))
    if not appid and ntpath.splitext(target)[1].lower()=='.exe':paths.add(norm(target))
    found=[w for w in windows if norm(w.get('path')) in paths or str(w.get('target','')).casefold()==target]
    if found:return found
    child=str(row.get('child_exe','')).casefold()
    return [w for w in windows if child and ntpath.basename(w.get('path','')).casefold()==child]


def _com():
    ole=ctypes.WinDLL('ole32',use_last_error=True);ole.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_uint];ole.CoInitializeEx.restype=ctypes.c_int32;ole.CoUninitialize.argtypes=[]
    return ole,ole.CoInitializeEx(None,2)>=0

def _guid(value):return (ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le)
def _call(obj,index,result,*args):
    table=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(result,ctypes.c_void_p,*args)(table[index])
def _release(obj):
    if obj.value:_call(obj,2,ctypes.c_uint)(obj)


def shortcut(path):
    if sys.platform!='win32' or not str(path).lower().endswith('.lnk'):return {'exe':str(path) if str(path).lower().endswith('.exe') else ''}
    ole,initialized=_com();obj=ctypes.c_void_p();persist=ctypes.c_void_p()
    try:
        create=ole.CoCreateInstance;create.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)];create.restype=ctypes.c_int32
        if create(_guid('00021401-0000-0000-c000-000000000046'),None,1,_guid('000214f9-0000-0000-c000-000000000046'),ctypes.byref(obj))<0:return {'exe':''}
        if _call(obj,0,ctypes.c_int32,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(obj,_guid('0000010b-0000-0000-c000-000000000046'),ctypes.byref(persist))<0:return {'exe':''}
        if _call(persist,5,ctypes.c_int32,ctypes.c_wchar_p,ctypes.c_uint)(persist,str(path),0)<0:return {'exe':''}
        target=ctypes.create_unicode_buffer(32768);arguments=ctypes.create_unicode_buffer(32768)
        _call(obj,3,ctypes.c_int32,ctypes.c_wchar_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint)(obj,target,len(target),None,4)
        _call(obj,10,ctypes.c_int32,ctypes.c_wchar_p,ctypes.c_int)(obj,arguments,len(arguments))
        child=re.search(r'--processStart(?:=|\s+)["\']?([^"\'\s]+\.exe)',arguments.value,re.I)
        return {'exe':os.path.expandvars(target.value),'child_exe':ntpath.basename(child.group(1)) if child else ''}
    finally:
        _release(persist);_release(obj)
        if initialized:ole.CoUninitialize()


def resolve_rows(rows):
    result=[];cache={}
    for row in rows:
        out=dict(row);path=str(out.get('path') or (out.get('target') if not str(out.get('target','')).startswith('app:') else '') or '')
        if path:
            if path not in cache:cache[path]=shortcut(path)
            out.update({k:v for k,v in cache[path].items() if v})
        out['directory']=bool(out.get('directory') or (path and Path(path).is_dir()))
        out['executables']=[out['exe']] if out.get('exe') else list(out.get('executables',[]));result.append(out)
    return result


def _png(image):
    from PySide6.QtCore import QBuffer,QByteArray,QIODevice
    if image.isNull():return ''
    image=image.scaled(128,128,__import__('PySide6.QtCore',fromlist=['Qt']).Qt.KeepAspectRatio,__import__('PySide6.QtCore',fromlist=['Qt']).Qt.SmoothTransformation)
    buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return base64.b64encode(bytes(buffer.data())).decode('ascii')


def _bitmap(bitmap):
    from ctypes import wintypes
    from PySide6.QtGui import QImage
    class BITMAP(ctypes.Structure):_fields_=[('type',wintypes.LONG),('width',wintypes.LONG),('height',wintypes.LONG),('stride',wintypes.LONG),('planes',wintypes.WORD),('bitsPixel',wintypes.WORD),('bits',ctypes.c_void_p)]
    class HEADER(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),('planes',wintypes.WORD),('bitCount',wintypes.WORD),('compression',wintypes.DWORD),('sizeImage',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),('used',wintypes.DWORD),('important',wintypes.DWORD)]
    g=ctypes.WinDLL('gdi32');g.GetObjectW.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p];g.CreateCompatibleDC.argtypes=[wintypes.HDC];g.CreateCompatibleDC.restype=wintypes.HDC;g.DeleteDC.argtypes=[wintypes.HDC];g.GetDIBits.argtypes=[wintypes.HDC,wintypes.HBITMAP,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]
    info=BITMAP()
    if not g.GetObjectW(bitmap,ctypes.sizeof(info),ctypes.byref(info)) or not 0<info.width<=512 or not 0<abs(info.height)<=512:return QImage()
    h=abs(info.height);header=HEADER(ctypes.sizeof(HEADER),info.width,-h,1,32,0,0,0,0,0,0);data=ctypes.create_string_buffer(info.width*h*4);dc=g.CreateCompatibleDC(None)
    try:
        if not g.GetDIBits(dc,bitmap,0,h,data,ctypes.byref(header),0):return QImage()
        raw=bytearray(data.raw)
        if not any(raw[3::4]):raw[3::4]=b'\xff'*(info.width*h)
        return QImage(bytes(raw),info.width,h,info.width*4,QImage.Format_ARGB32_Premultiplied).copy()
    finally:g.DeleteDC(dc)


def _shell_image(source):
    from ctypes import wintypes
    from PySide6.QtGui import QImage
    class SIZE(ctypes.Structure):_fields_=[('cx',ctypes.c_int),('cy',ctypes.c_int)]
    obj=ctypes.c_void_p();bitmap=wintypes.HBITMAP();shell=ctypes.WinDLL('shell32');g=ctypes.WinDLL('gdi32');g.DeleteObject.argtypes=[wintypes.HANDLE]
    fn=shell.SHCreateItemFromParsingName;fn.argtypes=[ctypes.c_wchar_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)];fn.restype=ctypes.c_int32
    try:
        if fn(source,None,_guid('bcc18b79-ba16-442f-80c4-8a59c30c463b'),ctypes.byref(obj))<0:return QImage()
        if _call(obj,3,ctypes.c_int32,SIZE,ctypes.c_uint,ctypes.POINTER(wintypes.HBITMAP))(obj,SIZE(128,128),5,ctypes.byref(bitmap))<0:return QImage()
        return _bitmap(bitmap)
    finally:
        if bitmap:g.DeleteObject(bitmap)
        _release(obj)


def _window_image(hwnd):
    from ctypes import wintypes
    from PySide6.QtGui import QImage
    u=ctypes.WinDLL('user32');u.SendMessageTimeoutW.argtypes=[wintypes.HWND,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_size_t)];u.CopyIcon.argtypes=[wintypes.HICON];u.CopyIcon.restype=wintypes.HICON;u.DestroyIcon.argtypes=[wintypes.HICON]
    handle=ctypes.c_size_t();u.SendMessageTimeoutW(hwnd,0x7f,1,0,2,80,ctypes.byref(handle))
    if not handle.value:
        get=getattr(u,'GetClassLongPtrW',u.GetClassLongW);get.argtypes=[wintypes.HWND,ctypes.c_int];get.restype=ctypes.c_size_t;handle.value=get(hwnd,-14)
    if not handle.value:return QImage()
    copied=u.CopyIcon(handle.value)
    if not copied:return QImage()
    try:
        if hasattr(QImage,'fromHICON'):
            try:return QImage.fromHICON(int(copied))
            except TypeError:pass
        return _draw_icon(copied)
    finally:u.DestroyIcon(copied)


def _draw_icon(handle):
    # PySide's fromHICON binding varies by wheel. The two-background conversion
    # preserves alpha for both modern 32-bit icons and classic monochrome masks.
    from ctypes import wintypes
    from PySide6.QtGui import QImage
    class HEADER(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),('planes',wintypes.WORD),('bitCount',wintypes.WORD),('compression',wintypes.DWORD),('sizeImage',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),('used',wintypes.DWORD),('important',wintypes.DWORD)]
    g=ctypes.WinDLL('gdi32');u=ctypes.WinDLL('user32');g.CreateCompatibleDC.argtypes=[wintypes.HDC];g.CreateCompatibleDC.restype=wintypes.HDC;g.CreateDIBSection.argtypes=[wintypes.HDC,ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),wintypes.HANDLE,wintypes.DWORD];g.CreateDIBSection.restype=wintypes.HBITMAP;g.SelectObject.argtypes=[wintypes.HDC,wintypes.HANDLE];g.SelectObject.restype=wintypes.HANDLE;g.DeleteObject.argtypes=[wintypes.HANDLE];g.DeleteDC.argtypes=[wintypes.HDC];u.DrawIconEx.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int,wintypes.HICON,ctypes.c_int,ctypes.c_int,ctypes.c_uint,wintypes.HBRUSH,ctypes.c_uint]
    size=64;header=HEADER(ctypes.sizeof(HEADER),size,-size,1,32,0,0,0,0,0,0);layers=[]
    for value in (0,255):
        dc=g.CreateCompatibleDC(None);bits=ctypes.c_void_p();bitmap=g.CreateDIBSection(dc,ctypes.byref(header),0,ctypes.byref(bits),None,0)
        if not bitmap:g.DeleteDC(dc);return QImage()
        previous=g.SelectObject(dc,bitmap)
        try:
            ctypes.memset(bits,value,size*size*4)
            if not u.DrawIconEx(dc,0,0,handle,size,size,0,None,3):return QImage()
            layers.append(ctypes.string_at(bits,size*size*4))
        finally:g.SelectObject(dc,previous);g.DeleteObject(bitmap);g.DeleteDC(dc)
    raw=bytearray(layers[0]);white=layers[1]
    for i in range(0,len(raw),4):raw[i+3]=255-max(white[i+j]-raw[i+j] for j in range(3))
    return QImage(bytes(raw),size,size,size*4,QImage.Format_ARGB32_Premultiplied).copy()


def extract_icon(row):
    if sys.platform!='win32':return ''
    ole,initialized=_com()
    try:
        target=str(row.get('target',''));sources=[]
        if target.startswith('app:'):sources.append('shell:AppsFolder\\'+target[4:])
        for value in (row.get('exe'),row.get('path'),target if not target.startswith('app:') else None):
            if value and value not in sources and Path(value).exists():sources.append(str(value))
        for source in sources:
            image=_shell_image(source)
            if not image.isNull():return _png(image)
        if row.get('hwnd'):
            image=_window_image(int(row['hwnd']))
            if not image.isNull():return _png(image)
        return ''
    finally:
        if initialized:ole.CoUninitialize()
