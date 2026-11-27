"""Live DWM window thumbnails. No screenshot polling or copied window contents."""
import ctypes,sys
from ctypes import wintypes as w
class PROPERTIES(ctypes.Structure):
    _fields_=[('flags',w.DWORD),('destination',w.RECT),('source',w.RECT),('opacity',w.BYTE),('visible',w.BOOL),('client',w.BOOL)]
class WindowPreviews:
    def __init__(self):
        self.handles=[];self.dwm=None
        if sys.platform=='win32':
            self.dwm=ctypes.WinDLL('dwmapi');self.dwm.DwmRegisterThumbnail.argtypes=[w.HWND,w.HWND,ctypes.POINTER(w.HANDLE)];self.dwm.DwmRegisterThumbnail.restype=ctypes.c_int32;self.dwm.DwmUpdateThumbnailProperties.argtypes=[w.HANDLE,ctypes.POINTER(PROPERTIES)];self.dwm.DwmUpdateThumbnailProperties.restype=ctypes.c_int32;self.dwm.DwmUnregisterThumbnail.argtypes=[w.HANDLE];self.dwm.DwmQueryThumbnailSourceSize.argtypes=[w.HANDLE,ctypes.POINTER(w.SIZE)]
    def add(self,destination,source,rect,dpr=1.):
        if not self.dwm:return False
        handle=w.HANDLE()
        if self.dwm.DwmRegisterThumbnail(int(destination),int(source),ctypes.byref(handle))<0:return False
        self.handles.append(handle);size=w.SIZE();self.dwm.DwmQueryThumbnailSourceSize(handle,ctypes.byref(size))
        x,y,width,height=rect
        if size.cx>0 and size.cy>0:
            scale=min(width/size.cx,height/size.cy);neww=size.cx*scale;newh=size.cy*scale;x+=(width-neww)/2;y+=(height-newh)/2;width,height=neww,newh
        p=PROPERTIES();p.flags=1|4|8|16;p.destination=w.RECT(round(x*dpr),round(y*dpr),round((x+width)*dpr),round((y+height)*dpr));p.opacity=255;p.visible=True;p.client=False
        if self.dwm.DwmUpdateThumbnailProperties(handle,ctypes.byref(p))<0:self.dwm.DwmUnregisterThumbnail(handle);self.handles.pop();return False
        return True
    def close(self):
        if self.dwm:
            for handle in self.handles:self.dwm.DwmUnregisterThumbnail(handle)
        self.handles=[]
