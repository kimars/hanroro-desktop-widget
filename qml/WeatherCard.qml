import QtQuick
WidgetFrame {
    id:root;widgetKey:"weather";title:"날씨 창문";width:280;height:320
    property bool moving:false
    readonly property var weather:bridge.weather
    readonly property bool night:weather.status==="ready"?!weather.isDay:scene.nightActive
    readonly property bool wet:["rain","storm","snow"].indexOf(weather.kind)>=0
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;rounding:28}
    Rectangle {id:glass;x:15;y:15;width:250;height:218;radius:92;clip:true;border.width:7;border.color:root.cardPalette.solid
        gradient:Gradient {GradientStop {position:0;color:root.night?"#182b48":root.wet?"#7898aa":"#72b7d0"} GradientStop {position:1;color:root.night?"#50617b":"#e4e8d2"}}
        Rectangle {x:160;y:35;width:42;height:42;radius:21;color:root.night?"#f0e7c9":"#ffe5a5";opacity:.95}
        Repeater {model:root.weather.kind==="cloud"||root.wet?3:1
            Rectangle {required property int index;x:20+index*76;y:72+index*11;width:95;height:30;radius:15;color:root.night?"#526780":"#e3edee";opacity:.8}
        }
        Rectangle {x:-20;y:165;width:190;height:100;radius:70;color:root.night?"#293e4a":"#6f9991";rotation:12}
        Rectangle {x:90;y:177;width:190;height:90;radius:60;color:root.night?"#243641":"#567e7a";rotation:-15}
        Repeater {model:root.wet?22:0
            Rectangle {id:drop;required property int index;x:10+(index*47)%230;y:20+(index*31)%190;width:root.weather.kind==="snow"?4:1;height:root.weather.kind==="snow"?4:13;radius:2;color:"#dceaf3";opacity:.75
                NumberAnimation on y {from:-20;to:220;duration:root.weather.kind==="snow"?5000+drop.index*90:1000+drop.index*35;loops:Animation.Infinite;running:root.moving&&root.visible}
            }
        }
        Rectangle {x:122;width:6;height:218;color:root.cardPalette.solid}
        Rectangle {y:128;width:250;height:5;color:root.cardPalette.solid}
        Rectangle {x:13;y:20;width:24;height:170;rotation:12;color:"#18ffffff"}
    }
    Text {x:22;y:244;width:150;elide:Text.ElideRight;text:root.weather.city||"날씨 창문";font.family:bridge.uiFont;font.pixelSize:14;color:root.cardPalette.ink}
    Text {x:22;y:270;text:root.weather.status==="ready"?root.weather.condition:root.weather.status==="loading"?"날씨 불러오는 중":root.weather.status==="error"?"연결 확인 필요":"날씨 연결";font.family:bridge.uiFont;font.pixelSize:12;color:root.cardPalette.muted}
    Text {anchors.right:parent.right;anchors.rightMargin:22;y:247;text:root.weather.temperature+"°";font.family:bridge.uiFont;font.pixelSize:34;color:root.cardPalette.ink}
    MouseArea {anchors.fill:parent;enabled:!bridge.editMode;cursorShape:Qt.PointingHandCursor;onClicked:bridge.refreshWeather()}
}
