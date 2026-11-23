import QtQuick
WidgetFrame {
    id:root;widgetKey:"system";title:"시스템";width:340;height:190
    readonly property var metrics:bridge.telemetry
    readonly property color accent:cardPalette.accent
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;rounding:22}
    Text {x:22;y:18;text:"시스템";color:root.cardPalette.ink;font.family:bridge.uiFont;font.pixelSize:13}
    Text {x:110;y:20;width:207;text:root.metrics.gpuName||root.metrics.error;elide:Text.ElideRight;horizontalAlignment:Text.AlignRight;color:root.cardPalette.muted;font.family:bridge.uiFont;font.pixelSize:10}
    Column {x:22;y:49;spacing:15
        Repeater {model:[{name:"CPU",key:"cpu",detail:""},{name:"RAM",key:"ram",detail:root.metrics.ramTotal?Number(root.metrics.ramUsed).toFixed(1)+" / "+Number(root.metrics.ramTotal).toFixed(1)+" GB":""},{name:"GPU",key:"gpu",detail:root.metrics.gpuTotal?Number(root.metrics.gpuUsed).toFixed(1)+" / "+Number(root.metrics.gpuTotal).toFixed(1)+" GB":""}]
            Item {required property var modelData;width:296;height:29
                readonly property var value:root.metrics[modelData.key]
                Text {text:modelData.name;color:root.cardPalette.muted;font.family:bridge.uiFont;font.pixelSize:11}
                Text {x:48;text:modelData.detail;color:root.cardPalette.muted;font.family:bridge.uiFont;font.pixelSize:10}
                Text {anchors.right:parent.right;text:parent.value===null||parent.value===undefined?"—":Math.round(parent.value)+"%";color:root.cardPalette.ink;font.family:bridge.uiFont;font.pixelSize:13;font.bold:true}
                Rectangle {y:23;width:296;height:4;radius:2;color:Qt.rgba(root.accent.r,root.accent.g,root.accent.b,.16)
                    Rectangle {height:4;width:parent.width*Math.max(0,Math.min(100,parent.parent.value||0))/100;radius:2;color:root.cardPalette.accent;Behavior on width {NumberAnimation {duration:380;easing.type:Easing.OutCubic}}}
                }
            }
        }
    }
}
