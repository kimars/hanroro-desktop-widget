import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtMultimedia
Item {
    id:scene
    property string layerRole:"preview"
    property real roomScale:Math.min(width/1600,height/900)
    readonly property var s:bridge.state
    readonly property bool bg:layerRole!=="overlay"
    readonly property bool fg:layerRole!=="background"
    readonly property bool dark:s.theme==="night" || s.dim>.4
    readonly property color ink:dark?"#f5f5f3":"#202626"
    readonly property color secondary:dark?"#b7bdb9":"#676e6b"
    readonly property color surface:dark?"#e523272a":"#d9fafbf9"
    readonly property color edge:dark?"#45ffffff":"#aaffffff"
    readonly property bool surfaceActive:Window.window!==null && Window.window.visible
    readonly property bool moving:s.motion&&!bridge.backgroundPaused&&!bridge.editMode&&surfaceActive
    property date now:new Date()
    property bool videoFailed:false
    property string selectedDecoration:""
    function pad(n){return (n<10?'0':'')+n}
    function updateRegions(){
        if(layerRole!=="overlay")return
        let regions=[]
        for(let it of [clock,player,memo,calendar,dock,systemMonitor,focusTimer,tools]){
            if(!it.visible)continue
            let top=it.mapToItem(scene,-10,-42),bottom=it.mapToItem(scene,it.width+16,it.height+14)
            regions.push({x:Math.floor(top.x),y:Math.floor(top.y),w:Math.ceil(bottom.x-top.x),h:Math.ceil(bottom.y-top.y)})
        }
        for(let i=0;i<furniture.count;i++){
            let obj=furniture.itemAt(i)
            if(!obj||!obj.visible)continue
            let active=bridge.editMode&&!obj.item.locked
            let bounds=obj.mapToItem(scene,active?Qt.rect(-8,-44,Math.max(obj.width,272)+16,obj.height+54):Qt.rect(-5,-5,obj.width+10,obj.height+10))
            regions.push({x:Math.floor(bounds.x),y:Math.floor(bounds.y),w:Math.ceil(bounds.width),h:Math.ceil(bounds.height),paintOnly:!active})
        }
        if(bridge.editMode)regions.push({x:width/2-210,y:14,w:420,h:34})
        if(toastBox.visible)regions.push({x:width/2-toastBox.width/2,y:height-80,w:toastBox.width,h:48})
        bridge.hitRegions(regions)
    }
    Timer {interval:1000;running:scene.fg&&scene.surfaceActive;repeat:true;onTriggered:scene.now=new Date()}
    Timer {id:regionThrottle;interval:64;onTriggered:scene.updateRegions()}
    function scheduleRegions(){if(scene.layerRole==="overlay"&&!regionThrottle.running)regionThrottle.start()}
    Timer {id:regionsSettled;interval:260;onTriggered:scene.updateRegions()}
    Connections {target:bridge;function onStateChanged(){if(scene.layerRole==="overlay")regionsSettled.restart()} function onEditChanged(){if(scene.layerRole==="overlay")scene.updateRegions()} function onDecorationsChanged(){scene.scheduleRegions()} function onLayoutChanged(){scene.scheduleRegions()} function onDragActivity(){scene.scheduleRegions()}}
    Image {anchors.fill:parent;visible:scene.bg;source:s.wallpaperUrl;fillMode:Image.PreserveAspectCrop;mipmap:true;asynchronous:true}
    MediaPlayer {
        id:wallVideo;objectName:"wallpaperVideo";source:scene.bg&&s.backgroundMode==="video"?s.backgroundUrl:"";loops:MediaPlayer.Infinite
        videoOutput:videoOutput;audioOutput:AudioOutput {muted:true}
        onSourceChanged:{scene.videoFailed=false;if(source.toString()!==''&&scene.surfaceActive&&!bridge.backgroundPaused)play()}
        onErrorOccurred:function(error,message){scene.videoFailed=true;bridge.videoError(error,message)}
    }
    Rectangle {anchors.fill:parent;visible:scene.bg&&s.backgroundMode==="video"&&!scene.videoFailed;color:"#101418"}
    VideoOutput {id:videoOutput;objectName:"backgroundVideoOutput";anchors.fill:parent;visible:scene.bg&&s.backgroundMode==="video"&&!scene.videoFailed;fillMode:s.wallpaperFit==="fit"?VideoOutput.PreserveAspectFit:VideoOutput.PreserveAspectCrop}
    Rectangle {anchors.fill:parent;visible:videoOutput.visible;color:"black";opacity:s.dim}
    onSurfaceActiveChanged:{if(surfaceActive&&!bridge.backgroundPaused&&wallVideo.source.toString()!=='')wallVideo.play();else wallVideo.pause()}
    Connections {target:bridge;function onPausedChanged(){if(!bridge.backgroundPaused&&scene.surfaceActive&&wallVideo.source.toString()!=='')wallVideo.play();else wallVideo.pause()}}
    Item {
        id:world;width:1600;height:900;scale:scene.roomScale;anchors.centerIn:parent
        Repeater {id:furniture;model:scene.fg?bridge.decorationModel:null
            Decoration {required property var entry;item:entry;moving:scene.moving&&!bridge.editMode;selected:scene.selectedDecoration===entry.id;onSelectRequested:function(identity){scene.selectedDecoration=identity};onRegionChanged:scene.scheduleRegions()}
        }
        WidgetFrame {
            id:clock;widgetKey:"clock";title:"시계";width:600;height:220;visible:cfg.visible&&scene.fg
            // Keep the clock face clean: no duplicate wordmark above the time.
            Text {x:-5;y:7;objectName:"clockTime";text:(now.getHours()%12===11&&now.getMinutes()===11)?"로로시":scene.pad(now.getHours())+":"+scene.pad(now.getMinutes());font.family:bridge.clockFont;font.pixelSize:112;font.weight:Font.Light;font.letterSpacing:-3;color:clock.cfg.color||scene.ink}
            Text {y:151;text:now.getFullYear()+". "+scene.pad(now.getMonth()+1)+". "+scene.pad(now.getDate())+"   "+["일요일","월요일","화요일","수요일","목요일","금요일","토요일"][now.getDay()];font.family:bridge.uiFont;font.weight:Font.Normal;font.pixelSize:17;font.letterSpacing:.6;color:clock.cfg.color||scene.secondary}
        }
        MusicCard {id:player;objectName:"musicCard";visible:cfg.visible&&scene.fg;moving:scene.moving}
        MemoCard {id:memo;objectName:"memoCard";visible:cfg.visible&&scene.fg;available:scene.fg&&scene.surfaceActive}
        CalendarCard {id:calendar;visible:cfg.visible&&scene.fg;now:scene.now}
        LauncherCard {id:dock;objectName:"launcherCard";visible:cfg.visible&&scene.fg}
        SystemCard {id:systemMonitor;objectName:"systemCard";visible:cfg.visible&&scene.fg}
        FocusCard {id:focusTimer;objectName:"focusCard";visible:cfg.visible&&scene.fg}
        Item {id:tools;x:1348;y:804;width:198;height:48;visible:scene.fg
            Rectangle {antialiasing:true;anchors.fill:parent;radius:24;color:scene.surface;border.color:scene.edge}
            Row {anchors.centerIn:parent;spacing:4
                IconButton {width:42;height:40;icon:"room";label:"가구 · 사진";ink:scene.ink;onClicked:bridge.manageRoom()}
                IconButton {width:42;height:40;icon:"plus";label:"버튼 추가";ink:scene.ink;onClicked:bridge.manageButtons()}
                IconButton {width:42;height:40;objectName:"layoutEditButton";icon:bridge.editMode?"check":"edit";label:bridge.editMode?"편집 완료":"위젯 편집";ink:scene.ink;onClicked:bridge.toggleEdit()}
                IconButton {width:42;height:40;icon:"settings";label:"설정";ink:scene.ink;onClicked:bridge.settings()}
            }
        }
    }
    Rectangle {antialiasing:true;id:toastBox;visible:false;onVisibleChanged:if(scene.layerRole==="overlay")Qt.callLater(scene.updateRegions);z:10000;anchors.horizontalCenter:parent.horizontalCenter;anchors.bottom:parent.bottom;anchors.bottomMargin:32;width:Math.min(680,toastText.implicitWidth+40);height:48;radius:16;color:"#ed232b2e"
        Text {id:toastText;anchors.centerIn:parent;width:Math.min(640,implicitWidth);elide:Text.ElideRight;color:"#f4f5f2";font.family:bridge.uiFont;font.weight:Font.Normal;font.pixelSize:13}
        Timer {id:toastTimer;interval:4000;onTriggered:toastBox.visible=false}
        Connections {target:bridge;function onToast(message){if(!scene.fg)return;toastText.text=message;toastBox.visible=true;toastTimer.restart()}}
    }
    Rectangle {antialiasing:true;visible:bridge.editMode&&scene.fg;anchors.top:parent.top;anchors.topMargin:14;anchors.horizontalCenter:parent.horizontalCenter;width:420;height:34;radius:17;color:"#ed232b2e";enabled:false
        Text {anchors.centerIn:parent;text:"상단 손잡이로 이동  ·  + / − 크기 조절  ·  체크로 완료";font.family:bridge.uiFont;font.weight:Font.Normal;font.pixelSize:12;color:"#f5f5f2"}
    }
}
