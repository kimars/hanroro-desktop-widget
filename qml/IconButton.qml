import QtQuick
import QtQuick.Controls
Item {
    id:root
    property string icon:"settings"
    property string label:""
    property color ink:"#273a4a"
    property color fill:"transparent"
    property real iconSize:20
    property bool circle:true
    property bool selected:false
    signal clicked()
    width:40;height:40
    Accessible.role:Accessible.Button;Accessible.name:label
    scale:area.pressed?.92:area.containsMouse?1.045:1
    Behavior on scale {NumberAnimation {duration:bridge.state.motion?150:0;easing.type:Easing.OutCubic}}
    Rectangle {anchors.fill:parent;radius:root.circle?width/2:12;antialiasing:true;color:area.containsMouse?Qt.rgba(root.ink.r,root.ink.g,root.ink.b,.12):root.fill;border.color:root.selected?bridge.state.accentColor:"transparent"
        Behavior on color {ColorAnimation {duration:bridge.state.motion?140:0}}
    }
    Icon {name:root.icon;ink:root.ink;width:root.iconSize;height:root.iconSize;anchors.centerIn:parent}
    MouseArea {id:area;anchors.fill:parent;hoverEnabled:true;cursorShape:Qt.PointingHandCursor;onClicked:root.clicked()}
    ToolTip.visible:area.containsMouse&&label.length>0;ToolTip.text:label;ToolTip.delay:450
}
