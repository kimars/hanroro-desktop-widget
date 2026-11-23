import QtQuick
Item {
    property color fill:"#eef4f9"
    property color stroke:"#44ffffff"
    property real rounding:24
    property bool focused:false
    Rectangle {x:0;y:5;width:parent.width;height:parent.height;radius:parent.rounding;antialiasing:true;color:"#12091420"}
    Rectangle {anchors.fill:parent;radius:parent.rounding;antialiasing:true;color:parent.fill;border.width:parent.focused?2:1;border.color:parent.focused?bridge.state.accentColor:parent.stroke
        Behavior on color {ColorAnimation {duration:bridge.state.motion?180:0}}
        Behavior on border.color {ColorAnimation {duration:160}}
    }
}
