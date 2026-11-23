import QtQuick
WidgetFrame {
    id:root;widgetKey:"focus";title:"집중 타이머";width:340;height:250
    readonly property var timer:bridge.features
    readonly property color accent:cardPalette.accent
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;rounding:24;focused:root.timer.ringing}
    Row {x:22;y:16;spacing:7
        Repeater {model:[{name:"집중",key:"focus"},{name:"휴식",key:"break"}]
            Rectangle {required property var modelData;width:56;height:28;radius:14;color:root.timer.phase===modelData.key?root.cardPalette.accent:"transparent";opacity:root.timer.phase===modelData.key?1:.65
                Text {anchors.centerIn:parent;text:parent.modelData.name;color:root.cardPalette.ink;font.family:bridge.uiFont;font.pixelSize:11}
                MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:bridge.timerPhase(parent.modelData.key)}
            }
        }
    }
    IconButton {x:282;y:14;width:36;height:32;icon:"settings";label:"타이머 설정";ink:root.cardPalette.muted;onClicked:bridge.manageFocus()}
    Text {anchors.horizontalCenter:parent.horizontalCenter;y:68;text:root.timer.label;font.family:bridge.clockFont;font.pixelSize:64;font.weight:Font.Light;font.letterSpacing:-2;color:root.cardPalette.ink}
    Rectangle {x:38;y:151;width:264;height:3;radius:2;color:Qt.rgba(root.accent.r,root.accent.g,root.accent.b,.2)
        Rectangle {width:parent.width*(root.timer.progress||0);height:3;radius:2;color:root.cardPalette.accent;Behavior on width {NumberAnimation {duration:250}}}
    }
    Row {anchors.horizontalCenter:parent.horizontalCenter;y:180;spacing:14
        IconButton {width:46;height:46;icon:"reset";label:"처음부터";ink:root.cardPalette.muted;onClicked:bridge.timerReset()}
        Rectangle {width:148;height:46;radius:23;color:root.cardPalette.accent
            Text {anchors.centerIn:parent;text:root.timer.ringing?"알람 끄기":root.timer.running?"일시정지":"시작";color:root.cardPalette.ink;font.family:bridge.uiFont;font.pixelSize:13;font.bold:true}
            MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:bridge.timerToggle()}
        }
    }
}
