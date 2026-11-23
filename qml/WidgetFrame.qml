import QtQuick
Item {
    id:root
    property string widgetKey:""
    property string title:""
    property var cfg:bridge.state.widgets[widgetKey]||({x:0,y:0,scale:1,visible:true,color:""})
    property var cardPalette:bridge.state.appearance[widgetKey]||({surface:"#f2f7fb",ink:"#233441",muted:"#657b8c",dark:false})
    property bool colorOpen:false
    property bool entered:false
    x:cfg.x;y:cfg.y;scale:cfg.scale;visible:cfg.visible
    transformOrigin:Item.TopLeft
    opacity:entered?1:0
    z:dragger.drag.active||colorOpen?200:1
    Behavior on opacity {NumberAnimation {duration:bridge.state.motion?240:0;easing.type:Easing.OutCubic}}
    Behavior on x {enabled:!bridge.editMode&&!dragger.drag.active;NumberAnimation {duration:bridge.state.motion?190:0;easing.type:Easing.OutCubic}}
    Behavior on y {enabled:!bridge.editMode&&!dragger.drag.active;NumberAnimation {duration:bridge.state.motion?190:0;easing.type:Easing.OutCubic}}
    Behavior on scale {NumberAnimation {duration:bridge.state.motion?180:0;easing.type:Easing.OutCubic}}
    Component.onCompleted:Qt.callLater(function(){entered=true})
    function syncPosition(){if(!dragger.drag.active){let row=bridge.widgetLayout(widgetKey);x=row.x;y=row.y;scale=row.scale}}
    Connections {target:bridge;function onStateChanged(){root.syncPosition()} function onLayoutChanged(){root.syncPosition()}}
    Rectangle {id:handle;visible:bridge.editMode;x:-2;y:-36;width:Math.max(root.width+4,220);height:32;radius:10;color:"#ee263a4a";border.color:"#779cb3"
        Text {x:12;anchors.verticalCenter:parent.verticalCenter;text:root.title;font.family:bridge.uiFont;font.pixelSize:12;color:"#edf6ff"}
        MouseArea {id:dragger;anchors.fill:parent;anchors.rightMargin:104;cursorShape:Qt.SizeAllCursor;drag.target:root;drag.axis:Drag.XAndYAxis;drag.minimumX:0;drag.maximumX:Math.max(0,1600-root.width*root.scale);drag.minimumY:40;drag.maximumY:Math.max(40,900-root.height*root.scale);onPositionChanged:if(drag.active)bridge.layoutActivity()
            onReleased:{bridge.moveWidget(root.widgetKey,root.x,root.y)}}
        Row {anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;spacing:0
            IconButton {width:32;height:30;icon:"minus";ink:"#edf6ff";label:"작게";onClicked:bridge.scaleWidget(root.widgetKey,root.scale-.05)}
            IconButton {width:32;height:30;icon:"plus";ink:"#edf6ff";label:"크게";onClicked:bridge.scaleWidget(root.widgetKey,root.scale+.05)}
            IconButton {width:32;height:30;icon:"close";ink:"#edf6ff";label:"숨기기";onClicked:bridge.hideWidget(root.widgetKey)}
        }
    }
    Rectangle {anchors.fill:parent;anchors.margins:-3;visible:bridge.editMode;color:"transparent";radius:25;border.color:bridge.state.accentColor;enabled:false;z:500}
    MouseArea {anchors.fill:parent;z:900;acceptedButtons:Qt.RightButton;onClicked:root.colorOpen=!root.colorOpen}
    Rectangle {visible:root.colorOpen;z:1000;x:Math.max(0,root.width-216);y:8;width:208;height:132;radius:16;color:"#f2263a4a";border.color:"#7398ad"
        Text {x:14;y:11;text:"위젯 색상";font.family:bridge.uiFont;font.pixelSize:12;color:"#edf6ff"}
        IconButton {x:171;y:2;width:32;height:32;icon:"close";ink:"#edf6ff";onClicked:root.colorOpen=false}
        Grid {x:14;y:37;columns:4;spacing:9
            Repeater {model:['#edf5fc','#e8f2ed','#f7e7e6','#ede7f7','#fff1db','#253343','#162431','#638da8']
                Rectangle {required property string modelData;width:37;height:26;radius:8;color:modelData;border.color:"#559eb9ce";MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:{bridge.setWidgetColor(root.widgetKey,parent.modelData);root.colorOpen=false}}}
            }
        }
        Text {x:14;y:109;text:"기본 색상으로";font.family:bridge.uiFont;font.pixelSize:11;color:"#bedcf1";MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:{bridge.setWidgetColor(root.widgetKey,'');root.colorOpen=false}}}
    }
}
