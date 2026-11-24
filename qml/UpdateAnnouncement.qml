import QtQuick
import QtQuick.Controls
Item {
    id:root
    objectName:"updateAnnouncement"
    readonly property var notice:bridge.updateNotice
    readonly property bool busy:notice.phase==="downloading"||notice.phase==="ready"||notice.phase==="installing"
    signal regionChanged()
    property alias characterItem:character
    property alias bubbleItem:bubble
    readonly property bool characterReady:character.status===Image.Ready
    width:500;height:356
    scale:Math.min(1,(parent.width-24)/width,(parent.height-24)/height)
    transformOrigin:Item.BottomLeft
    visible:notice.visible
    opacity:visible?1:0
    property real entrance:visible?1:0
    Behavior on entrance {enabled:bridge.state.motion;NumberAnimation {duration:420;easing.type:Easing.OutCubic}}
    Item {
        id:content;anchors.fill:parent
        transform:Translate {y:(1-root.entrance)*48}
        opacity:root.entrance
        Image {id:character;objectName:"updateCharacter";x:0;y:65;width:226;height:290;source:"image://updatecharacter/character";sourceSize.width:452;fillMode:Image.PreserveAspectFit;asynchronous:false;mipmap:true;onStatusChanged:root.regionChanged()}
        Rectangle {
            id:bubble;objectName:"updateBubble";x:162;y:14;width:320;height:198;radius:22
            color:"#fffdf8";border.color:"#dce4de";border.width:1
            Rectangle {x:24;y:parent.height-9;width:18;height:18;rotation:45;color:bubble.color;z:-1;border.color:bubble.border.color}
            Column {
                x:22;y:22;width:276;spacing:10
                Text {objectName:"updateAnnouncementTitle";width:parent.width;text:root.notice.phase==="error"?"다시 해볼까?":root.busy?"업데이트 중이야!":"새 업데이트가 왔어!";color:"#263632";font.family:bridge.uiFont;font.pixelSize:23;font.weight:Font.Normal}
                Text {width:parent.width;height:24;text:root.notice.demo?"알림 미리보기":root.notice.waiting?"편집이 끝나면 시작할게":root.notice.phase==="downloading"?"다운로드 "+root.notice.progress+"%":root.notice.phase==="installing"?"설치 후 다시 만나요":root.notice.seconds>0?root.notice.version+" · "+root.notice.seconds+"초 뒤 자동 설치":root.notice.phase==="error"?"설정에서 오류를 확인해줘":root.notice.version+" 버전";color:"#718077";font.family:bridge.uiFont;font.pixelSize:14;elide:Text.ElideRight}
                Item {width:parent.width;height:5
                    Rectangle {anchors.fill:parent;radius:3;color:"#e5eee8"}
                    Rectangle {width:parent.width*(root.notice.phase==="downloading"?root.notice.progress/100:root.notice.seconds>0?(15-root.notice.seconds)/15:0);height:5;radius:3;color:bridge.state.accentColor||"#86b8d6";Behavior on width {NumberAnimation {duration:200}}}
                }
                Row {spacing:8
                    Button {id:install;objectName:"noticeUpdateNow";width:174;height:42;enabled:!root.busy;text:root.notice.demo?"업데이트 설정":root.notice.phase==="error"?"다시 시도":"지금 업데이트";onClicked:bridge.updateFromNotice();background:Rectangle {radius:12;color:install.down?"#334d43":"#263d34"} contentItem:Text {text:install.text;color:"white";font.family:bridge.uiFont;font.pixelSize:14;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}}
                    Button {id:later;objectName:"noticeDismiss";width:94;height:42;text:root.busy?"닫기":"나중에";onClicked:bridge.dismissUpdateNotice();background:Rectangle {radius:12;color:later.down?"#dce6de":"#edf2eb"} contentItem:Text {text:later.text;color:"#526459";font.family:bridge.uiFont;font.pixelSize:14;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}}
                }
            }
        }
    }
    onVisibleChanged:root.regionChanged()
    onEntranceChanged:root.regionChanged()
    onScaleChanged:root.regionChanged()
}
