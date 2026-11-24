"""Nonblocking, bounded weather requests. Coordinates are approximate and not persisted."""
import json, math
from urllib.parse import urlencode
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

def coordinates(data):
    lat,lon=float(data['latitude']),float(data['longitude'])
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid coordinates')
    return round(lat,2),round(lon,2)

def condition(code):
    if code==0:return '맑음','clear'
    if code in (1,2,3):return '구름','cloud'
    if code in (45,48):return '안개','fog'
    if code in (71,73,75,77,85,86):return '눈','snow'
    if code in (95,96,99):return '뇌우','storm'
    if code in (51,53,55,56,57,61,63,65,66,67,80,81,82):return '비','rain'
    return '흐림','cloud'

class WeatherLink(QObject):
    changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.manager=None;self.reply=None;self.generation=0;self.enabled=False;self.city=''
        self.data={'status':'off','city':'','temperature':'—','condition':'','kind':'cloud','isDay':True,'updated':''}
        self.timer=QTimer(self);self.timer.setInterval(20*60*1000);self.timer.timeout.connect(self.refresh)
    def configure(self,enabled,city=''):
        if self.enabled==enabled and self.city==city:return
        self.enabled=enabled;self.city=city;self.generation+=1
        if self.reply:self.reply.abort()
        if enabled:self.timer.start();self.refresh()
        else:self.timer.stop();self.data['status']='off';self.changed.emit()
    def request(self,url,callback,token):
        req=QNetworkRequest(QUrl(url));req.setTransferTimeout(10000);req.setRawHeader(b'User-Agent',b'HanroroWidget/1.6')
        if self.manager is None:self.manager=QNetworkAccessManager(self)
        reply=self.manager.get(req);self.reply=reply
        def done():
            try:
                if token!=self.generation or not self.enabled:return
                if reply.error()!=QNetworkReply.NetworkError.NoError:raise ValueError('Network unavailable')
                raw=bytes(reply.readAll())
                if len(raw)>200000:raise ValueError('Response too large')
                callback(json.loads(raw))
            except (ValueError,KeyError,TypeError,OverflowError,IndexError,IndexError):
                if token==self.generation:self.data['status']='error';self.changed.emit()
            finally:
                if self.reply is reply:self.reply=None
                reply.deleteLater()
        reply.finished.connect(done)
    def refresh(self):
        if not self.enabled or self.reply:return
        self.data['status']='loading';self.changed.emit();token=self.generation
        if self.city:
            def found(data):
                row=data['results'][0];self.forecast(row,token)
            self.request('https://geocoding-api.open-meteo.com/v1/search?'+urlencode({'name':self.city,'count':1,'language':'ko'}),found,token)
        else:self.request('https://ipapi.co/json/',lambda row:self.forecast(row,token),token)
    def forecast(self,row,token):
        lat,lon=coordinates(row);city=str(row.get('name') or row.get('city') or row.get('region') or '현재 위치')[:80]
        def received(data):
            from datetime import datetime
            current=data['current'];temp=float(current['temperature_2m'])
            if not math.isfinite(temp) or not -100<temp<80:raise ValueError('Invalid temperature')
            title,kind=condition(int(current['weather_code']))
            self.data={'status':'ready','city':city,'temperature':str(round(temp)),'condition':title,'kind':kind,'isDay':bool(current['is_day']),'updated':datetime.now().strftime('%H:%M')};self.changed.emit()
        self.request('https://api.open-meteo.com/v1/forecast?'+urlencode({'latitude':lat,'longitude':lon,'current':'temperature_2m,weather_code,is_day','timezone':'auto'}),received,token)
    def close(self):
        self.enabled=False;self.generation+=1;self.timer.stop()
        if self.reply:self.reply.abort()
