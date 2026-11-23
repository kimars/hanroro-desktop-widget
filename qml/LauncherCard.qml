import QtQuick
WidgetFrame {
    id:root;widgetKey:"dock";title:"바로가기";width:652;height:164
    property int page:0
    readonly property int pages:Math.max(1,Math.ceil(bridge.state.links.length/8))
    onPagesChanged:page=Math.min(page,pages-1)
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface}
    Text {x:20;y:17;text:"바로가기";font.family:bridge.uiFont;font.pixelSize:14;font.weight:Font.DemiBold;color:root.cardPalette.ink}
    Text {x:460;y:20;width:52;horizontalAlignment:Text.AlignRight;text:(root.page+1)+" / "+root.pages;font.family:bridge.uiFont;font.pixelSize:11;color:root.cardPalette.muted}
    Row {x:516;y:5;spacing:0
        IconButton {width:36;icon:"previous";label:"이전 페이지";ink:root.cardPalette.muted;onClicked:root.page=(root.page-1+root.pages)%root.pages}
        IconButton {width:36;icon:"next";label:"다음 페이지";ink:root.cardPalette.muted;onClicked:root.page=(root.page+1)%root.pages}
        IconButton {objectName:"addShortcutButton";icon:"plus";label:"버튼 추가 · 설치된 앱 선택";ink:root.cardPalette.ink;onClicked:bridge.manageButtons()}
    }
    Grid {x:16;y:52;columns:4;spacing:6
        Repeater {model:bridge.state.links.slice(root.page*8,root.page*8+8)
            Item {required property var modelData;required property int index;width:150;height:46;scale:area.pressed?.96:1
                Behavior on scale {NumberAnimation {duration:120;easing.type:Easing.OutCubic}}
                Rectangle {anchors.fill:parent;radius:13;color:area.containsMouse?(root.cardPalette.dark?"#22ffffff":"#100d3857"):root.cardPalette.dark?"#09ffffff":"#50ffffff";Behavior on color {ColorAnimation {duration:140}}}
                Icon {x:13;y:12;width:22;height:22;name:modelData.glyph;ink:root.cardPalette.ink;visible:!modelData.icon}
                Image {x:11;y:10;width:26;height:26;source:modelData.icon||"";visible:!!modelData.icon;fillMode:Image.PreserveAspectFit;mipmap:true;asynchronous:true}
                Text {x:46;y:15;width:93;text:modelData.title;elide:Text.ElideRight;font.family:bridge.uiFont;font.pixelSize:12;color:root.cardPalette.ink}
                MouseArea {id:area;anchors.fill:parent;hoverEnabled:true;cursorShape:Qt.PointingHandCursor;acceptedButtons:Qt.LeftButton|Qt.RightButton;onClicked:function(mouse){if(mouse.button===Qt.RightButton)bridge.manageButtons();else bridge.launch(root.page*8+index)}}
            }
        }
    }
    DropArea {anchors.fill:parent;onDropped:function(drop){if(drop.hasUrls){bridge.addDroppedFiles(drop.urls.map(function(u){return u.toString()}));drop.acceptProposedAction()}}}
}
