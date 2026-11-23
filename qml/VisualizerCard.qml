import QtQuick
WidgetFrame {
    id:root;widgetKey:"visualizer";title:"오디오";width:340;height:112
    property bool moving:true
    readonly property var metrics:bridge.telemetry
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;rounding:22}
    Text {x:22;y:17;text:"오디오";color:root.cardPalette.muted;font.family:bridge.uiFont;font.pixelSize:12}
    Text {x:94;y:18;width:223;text:root.metrics.audioStatus||root.metrics.error||root.metrics.device||"스피커 출력";elide:Text.ElideRight;color:root.cardPalette.muted;opacity:.7;font.family:bridge.uiFont;font.pixelSize:10;horizontalAlignment:Text.AlignRight}
    Row {x:22;y:44;spacing:4;height:45
        Repeater {model:32
            Rectangle {required property int index;width:5.4;height:3+(root.moving?(root.metrics.levels[index]||0):0)*41;anchors.verticalCenter:parent.verticalCenter;radius:2.7;color:root.cardPalette.accent;opacity:.4+(index/32)*.6
                Behavior on height {NumberAnimation {duration:90;easing.type:Easing.OutCubic}}
            }
        }
    }
}
