import copy, math
import pytest
from urllib.parse import parse_qs,urlparse
from PySide6.QtCore import Qt,QPoint,QObject
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QSlider
from state import Store,validate
from weather_link import WeatherLink,coordinates,condition

def test_coordinates_and_weather_codes():
    assert coordinates({'latitude':37.5665,'longitude':126.978})==(37.57,126.98)
    for value in (float('nan'),float('inf'),91):
        with pytest.raises(ValueError):coordinates({'latitude':value,'longitude':0})
    assert condition(75)==('눈','snow') and condition(95)[1]=='storm' and condition(61)[1]=='rain'

def test_auto_location_then_forecast_and_city_override(qt_application):
    w=WeatherLink();calls=[]
    w.request=lambda url,callback,token:calls.append((url,callback,token))
    w.configure(True)
    assert calls[0][0]=='https://ipapi.co/json/'
    calls[0][1]({'latitude':37.5665,'longitude':126.978,'city':'Seoul'})
    query=parse_qs(urlparse(calls[-1][0]).query)
    assert query['latitude']==['37.57'] and 'is_day' in query['current'][0]
    calls[-1][1]({'current':{'temperature_2m':12.5,'weather_code':75,'is_day':0}})
    assert w.data['city']=='Seoul' and w.data['kind']=='snow' and not w.data['isDay']
    w.configure(True,'부산');assert 'geocoding-api.open-meteo.com' in calls[-1][0]
    calls[-1][1]({'results':[{'latitude':35.1,'longitude':129.0,'name':'부산'}]})
    assert 'latitude=35.1' in calls[-1][0]
    w.configure(False);assert not w.timer.isActive() and w.data['status']=='off';w.close()

def test_dark_theme_preserves_custom_colors_and_switches_player(tmp_path,qt_application):
    from backend import Bridge
    from pathlib import Path
    b=Bridge(Store(tmp_path),Path(__file__).resolve().parents[1]/'assets')
    b.store.data['widgets']['memo']['color']='#fad1d9';b.set_option('theme','night')
    assert b.appearance()['memo']['solid']=='#fad1d9'
    assert b.appearance()['player']['dark'] and b.appearance()['calendar']['dark']
    b.set_option('widgetColor','#bde0cd');assert b.appearance()['calendar']['solid']=='#bde0cd'
    b.set_option('nightLighting',True);b.persist();restored=Store(tmp_path)
    assert restored.data['nightLighting'] and restored.data['widgets']['memo']['color']=='#fad1d9'
    b.writer.close();b.media.close();b.weather_link.close();b.telemetry_link.close();b.features_controller.close();b.update_prompt.close();b.updates.close()

def test_palette_wheel_has_no_slider_and_mouse_changes_hue(qt_application):
    from panel_ui import PaletteDialog
    d=PaletteDialog(QColor('#00ff00'));d.show();QTest.qWait(20)
    assert not d.findChildren(QSlider)
    QTest.mouseClick(d.hue,Qt.LeftButton,pos=QPoint(d.hue.width()//2+48,d.hue.height()//2))
    assert d.plane.hue<10 or d.plane.hue>350
    d.close();d.deleteLater();QTest.qWait(10)
