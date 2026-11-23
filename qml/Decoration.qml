import QtQuick
import QtQuick.Controls
Item {
    id:root
    objectName:"decoration-"+item.id
    required property var item
    property bool editing:bridge.editMode&&!item.locked
    property bool selected:false
    property bool moving:false
    readonly property bool motionActive:moving&&item.animate&&item.motion!==""
    readonly property real swayAmount:item.motion==="cord"?2.5:item.motion==="leaves"?.85:1.1
    signal regionChanged()
    signal selectRequested(string identity)
    x:item.x;y:item.y;width:item.width;height:item.height;scale:item.scale;rotation:item.rotation
    onItemChanged:if(!dragger.drag.active){x=item.x;y=item.y}
    transformOrigin:Item.TopLeft
    z:(editing&&selected)?300:item.z
    onXChanged:if(dragger.drag.active)regionChanged()
    onYChanged:if(dragger.drag.active)regionChanged()
    Item {anchors.fill:parent
        transform:Scale {origin.x:root.width/2;xScale:root.item.flipped?-1:1}
        Image {anchors.fill:parent;visible:root.item.kind!=="photo";source:visible?bridge.state.assetUrl+"furniture/"+root.item.kind+(root.item.motion?"-base":"")+".svg":"";sourceSize.width:root.width*2;sourceSize.height:root.height*2;asynchronous:true;mipmap:true;fillMode:Image.PreserveAspectFit}
        Item {id:motionLayer;objectName:"furnitureMotionLayer";anchors.fill:parent;visible:!!root.item.motion
            Item {id:motionPivot;x:root.width*(root.item.pivotX||0);y:root.height*(root.item.pivotY||0);width:0;height:0
                Image {x:-motionPivot.x;y:-motionPivot.y;width:root.width;height:root.height;source:root.item.motion?bridge.state.assetUrl+"furniture/"+root.item.kind+"-moving.svg":"";sourceSize.width:root.width*2;sourceSize.height:root.height*2;asynchronous:true;mipmap:true;fillMode:Image.PreserveAspectFit}
            }
            SequentialAnimation {running:root.motionActive&&["sway","cord","leaves"].indexOf(root.item.motion)>=0;loops:Animation.Infinite
                RotationAnimator {target:motionPivot;from:-root.swayAmount;to:root.swayAmount;duration:2600;easing.type:Easing.InOutSine}
                RotationAnimator {target:motionPivot;from:root.swayAmount;to:-root.swayAmount;duration:2600;easing.type:Easing.InOutSine}
                onStopped:motionPivot.rotation=0
            }
            RotationAnimator {target:motionPivot;from:0;to:360;duration:900;running:root.motionActive&&root.item.motion==="spin";loops:Animation.Infinite;onStopped:motionPivot.rotation=0}
            SequentialAnimation {running:root.motionActive&&["flame","glow"].indexOf(root.item.motion)>=0;loops:Animation.Infinite
                OpacityAnimator {target:motionLayer;from:1;to:.68;duration:root.item.motion==="flame"?420:1800;easing.type:Easing.InOutSine}
                OpacityAnimator {target:motionLayer;from:.68;to:1;duration:root.item.motion==="flame"?610:1800;easing.type:Easing.InOutSine}
                onStopped:motionLayer.opacity=1
            }
        }
        Rectangle {visible:root.item.kind==="photo";anchors.fill:parent;color:"#fbf9f2";border.color:"#e4dfd3";radius:2
            Rectangle {x:5;y:5;width:parent.width;height:parent.height;color:"#19000000";z:-1;radius:2}
            Image {anchors.fill:parent;anchors.margins:12;anchors.bottomMargin:30;source:root.item.imageUrl||"";fillMode:Image.PreserveAspectFit;asynchronous:true;autoTransform:true;sourceSize.width:Math.ceil(width*2);sourceSize.height:Math.ceil(height*2);mipmap:true}
        }
    }
    Rectangle {anchors.fill:parent;visible:root.editing;color:"transparent";border.width:1;border.color:root.selected?bridge.state.accentColor:"#7091a6b5";radius:3}
    MouseArea {id:dragger;anchors.fill:parent;enabled:root.editing;cursorShape:Qt.SizeAllCursor;drag.target:root;drag.threshold:3;drag.minimumX:0;drag.maximumX:Math.max(0,1600-root.width*root.scale);drag.minimumY:40;drag.maximumY:Math.max(40,900-root.height*root.scale)
        onPressed:root.selectRequested(root.item.id)
        onReleased:{bridge.moveDecoration(root.item.id,root.x,root.y);root.regionChanged()}
    }
    Rectangle {visible:root.editing&&root.selected;x:0;y:-40;width:272;height:34;radius:12;color:"#f0263a4a";z:500
        Row {spacing:0
            IconButton {width:34;height:34;icon:"minus";ink:"#edf6ff";label:"작게";onClicked:bridge.adjustDecoration(root.item.id,"scale",root.item.scale-.1)}
            IconButton {width:34;height:34;icon:"plus";ink:"#edf6ff";label:"크게";onClicked:bridge.adjustDecoration(root.item.id,"scale",root.item.scale+.1)}
            IconButton {width:34;height:34;icon:"reset";ink:"#edf6ff";label:"회전";onClicked:bridge.adjustDecoration(root.item.id,"rotation",root.item.rotation>=165?-180:root.item.rotation+15)}
            IconButton {width:34;height:34;icon:"arrow";ink:"#edf6ff";label:"좌우 반전";onClicked:bridge.actionDecoration(root.item.id,"flip")}
            IconButton {width:34;height:34;icon:"plus";ink:"#edf6ff";label:"앞으로";onClicked:bridge.adjustDecoration(root.item.id,"z",root.item.z+1)}
            IconButton {width:34;height:34;icon:"minus";ink:"#edf6ff";label:"뒤로";onClicked:bridge.adjustDecoration(root.item.id,"z",root.item.z-1)}
            IconButton {width:34;height:34;icon:"check";ink:"#edf6ff";label:"고정";onClicked:bridge.actionDecoration(root.item.id,"lock")}
            IconButton {width:34;height:34;icon:"trash";ink:"#edf6ff";label:"삭제";onClicked:bridge.actionDecoration(root.item.id,"delete")}
        }
    }
}
