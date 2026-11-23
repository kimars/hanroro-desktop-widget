import QtQuick
WidgetFrame {
    id:root
    widgetKey:"calendar"
    title:"달력 · 일정"
    width:280
    height:194
    property date now:new Date()
    property int monthOffset:0
    property string selectedDate:dateKey(now.getFullYear(),now.getMonth()+1,now.getDate())
    readonly property date monthDate:new Date(now.getFullYear(),now.getMonth()+monthOffset,1)
    function pad(n){return n<10?"0"+n:String(n)}
    function dateKey(y,m,d){return y+"-"+pad(m)+"-"+pad(d)}
    function eventFor(key){
        var rows=bridge.state.events||[]
        for(var i=0;i<rows.length;i++)if(rows[i].date===key)return rows[i]
        return null
    }
    StyledCard {anchors.fill:parent;fill:root.cardPalette.surface;rounding:20}
    Text {
        x:18;y:14
        text:root.monthDate.getFullYear()+"년 "+(root.monthDate.getMonth()+1)+"월"
        font.family:bridge.uiFont;font.pixelSize:16;font.weight:Font.DemiBold
        color:root.cardPalette.ink
    }
    Row {
        x:196;y:10;spacing:2
        IconButton {width:24;height:24;iconSize:12;icon:"chevron-left";label:"이전 달";ink:root.cardPalette.muted;onClicked:root.monthOffset--}
        IconButton {width:24;height:24;iconSize:12;icon:"chevron-right";label:"다음 달";ink:root.cardPalette.muted;onClicked:root.monthOffset++}
        IconButton {width:24;height:24;iconSize:14;icon:"plus";label:"일정 추가";ink:root.cardPalette.ink;onClicked:bridge.editEvents()}
    }
    Row {
        x:14;y:44;spacing:0
        Repeater {
            model:["일","월","화","수","목","금","토"]
            Text {required property string modelData;required property int index;width:36;height:16;text:modelData;horizontalAlignment:Text.AlignHCenter
                font.family:bridge.uiFont;font.pixelSize:10;color:index===0?"#c47d83":index===6?"#718eae":root.cardPalette.muted}
        }
    }
    Grid {
        id:days;x:14;y:61;columns:7;spacing:0
        property int first:new Date(root.monthDate.getFullYear(),root.monthDate.getMonth(),1).getDay()
        property int count:new Date(root.monthDate.getFullYear(),root.monthDate.getMonth()+1,0).getDate()
        Repeater {
            model:42
            Item {
                required property int index
                property int day:index-days.first+1
                property string key:day>0&&day<=days.count?root.dateKey(root.monthDate.getFullYear(),root.monthDate.getMonth()+1,day):""
                width:36;height:18
                Rectangle {
                    anchors.centerIn:parent;width:25;height:18;radius:8
                    color:parent.key===root.selectedDate?"#bfe5f2f4":"transparent"
                    border.color:parent.key===root.selectedDate?"#a6ffffff":"transparent"
                    Behavior on color {ColorAnimation{duration:bridge.state.motion?140:0}}
                }
                Text {
                    anchors.centerIn:parent
                    text:parent.day>0&&parent.day<=days.count?parent.day:""
                    font.family:bridge.uiFont;font.pixelSize:10
                    font.weight:parent.key===root.selectedDate?Font.DemiBold:Font.Normal
                    color:parent.key===root.selectedDate?root.cardPalette.ink:parent.index%7===0?"#bd7c83":parent.index%7===6?"#718eae":root.cardPalette.ink
                }
                Rectangle {
                    visible:!!root.eventFor(parent.key)
                    width:3;height:3;radius:2;color:root.cardPalette.accent
                    anchors.horizontalCenter:parent.horizontalCenter;anchors.bottom:parent.bottom;anchors.bottomMargin:0
                }
                MouseArea {
                    anchors.fill:parent;enabled:parent.key!=="";cursorShape:Qt.PointingHandCursor
                    onClicked:root.selectedDate=parent.key
                }
            }
        }
    }
    Rectangle {
        x:14;y:174;width:252;height:1;color:root.cardPalette.muted;opacity:.18
    }
    Item {
        x:18;y:178;width:246;height:14
        Row {
        anchors.fill:parent;spacing:7
        Rectangle {width:5;height:5;radius:3;color:root.cardPalette.accent;y:4}
        Text {
            width:232;elide:Text.ElideRight
            text:{var event=root.eventFor(root.selectedDate);return event?event.title:root.selectedDate.replace(/-/g,".")+"  ·  일정 없음"}
            font.family:bridge.uiFont;font.pixelSize:10;color:root.cardPalette.muted
        }
        }
        MouseArea {anchors.fill:parent;cursorShape:Qt.PointingHandCursor;onClicked:bridge.editEvents()}
    }
}
