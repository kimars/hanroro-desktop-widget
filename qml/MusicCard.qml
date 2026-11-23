import QtQuick
WidgetFrame {
    id:root;widgetKey:"player";title:"음악";width:348;height:432
    property bool moving:true
    readonly property color ink:cardPalette.ink
    readonly property color muted:cardPalette.muted
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;stroke:root.cardPalette.dark?"#304d5250":"#80ffffff";rounding:24}
    Item {width:348;height:274;clip:true
        Image {anchors.fill:parent;source:bridge.state.assetUrl+"ui/paper-grain.svg";fillMode:Image.Tile;sourceSize.width:128;sourceSize.height:128}
        Rectangle {x:-55;y:-39;width:332;height:332;radius:166;color:"#16000000";antialiasing:true}
        Item {id:record;objectName:"paperRecord";x:-55;y:-46;width:332;height:332
            Image {anchors.fill:parent;source:bridge.state.assetUrl+"ui/paper-vinyl.svg";sourceSize.width:664;sourceSize.height:664;mipmap:true}
            RoundImage {anchors.centerIn:parent;width:153;height:153;source:bridge.albumCover || bridge.photo}
            Rectangle {anchors.centerIn:parent;width:7;height:7;radius:4;color:"#f4f3ec";border.color:"#b8b9af";antialiasing:true}
            RotationAnimator on rotation {from:0;to:360;duration:14000;running:bridge.playing&&root.moving;loops:Animation.Infinite}
        }
        Image {x:188;y:-2;width:155;height:274;source:bridge.state.assetUrl+"ui/paper-tonearm.svg";sourceSize.width:310;sourceSize.height:548;mipmap:true
            transform:Rotation {origin.x:118;origin.y:35;angle:bridge.playing?4:0;Behavior on angle {NumberAnimation {duration:bridge.state.motion?600:0;easing.type:Easing.InOutCubic}}}
        }
    }
    Text {objectName:"musicTrackTitle";x:22;y:278;width:260;elide:Text.ElideRight;text:bridge.trackTitle;font.family:bridge.uiFont;font.pixelSize:23;font.weight:Font.Bold;font.letterSpacing:-.6;color:root.ink}
    Text {x:22;y:309;width:280;elide:Text.ElideRight;text:bridge.trackArtist || bridge.trackHint;font.family:bridge.uiFont;font.pixelSize:13;color:root.muted}
    IconButton {x:294;y:275;icon:"settings";label:"재생 앱 연결";ink:root.ink;onClicked:bridge.chooseMusic()}
    Item {id:audioSpectrum;objectName:"playerSpectrum";x:22;y:334;width:304;height:23
        readonly property var bins:root.visible&&root.moving&&bridge.state.audioReactive?bridge.audioLevels:[]
        Row {anchors.fill:parent;spacing:3
            Repeater {model:32
                Rectangle {required property int index;width:6.59;height:2+(audioSpectrum.bins[index]||0)*21;anchors.bottom:parent.bottom;radius:2;color:root.ink;opacity:.2+(audioSpectrum.bins[index]||0)*.65
                    Behavior on height {enabled:root.moving;NumberAnimation {duration:65}}
                }
            }
        }
    }
    Rectangle {objectName:"musicSeekBar";x:22;y:362;width:304;height:2;radius:1;color:root.cardPalette.dark?"#56615f":"#d5d0c7"
        Rectangle {width:parent.width*bridge.progress;height:2;radius:1;color:root.ink}
        MouseArea {anchors.fill:parent;anchors.topMargin:-7;anchors.bottomMargin:-7;enabled:bridge.canSeek;cursorShape:enabled?Qt.PointingHandCursor:Qt.ArrowCursor;onClicked:function(mouse){bridge.seek(mouse.x/width)}}
    }
    Text {x:22;y:370;text:bridge.elapsed;font.family:bridge.uiFont;font.pixelSize:9;color:root.muted}
    Text {x:276;y:370;width:50;horizontalAlignment:Text.AlignRight;text:bridge.duration;font.family:bridge.uiFont;font.pixelSize:9;color:root.muted}
    Row {x:76;y:389;spacing:12
        IconButton {width:52;height:34;enabled:bridge.canPrevious;opacity:enabled?1:.35;icon:"previous";label:"이전 곡";ink:root.ink;fill:root.cardPalette.dark?"#17ffffff":"#60ffffff";circle:false;onClicked:bridge.previousTrack()}
        IconButton {objectName:"musicPlayButton";enabled:bridge.canPlayPause;opacity:enabled?1:.35;width:68;height:34;icon:bridge.playing?"pause":"play";label:"재생 / 일시 정지";ink:root.ink;fill:root.cardPalette.dark?"#26ffffff":"#b3ffffff";circle:false;onClicked:bridge.playPause()}
        IconButton {width:52;height:34;enabled:bridge.canNext;opacity:enabled?1:.35;icon:"next";label:"다음 곡";ink:root.ink;fill:root.cardPalette.dark?"#17ffffff":"#60ffffff";circle:false;onClicked:bridge.nextTrack()}
    }
}
