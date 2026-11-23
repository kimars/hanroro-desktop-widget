import QtQuick
Image {
    property string name:"app"
    property color ink:"#202626"
    property real stroke:1.7
    readonly property bool light:ink.r+ink.g+ink.b>1.6
    source:bridge.state.assetUrl+"icons/"+(light?"light/":"dark/")+name+".svg"
    width:24;height:24;sourceSize.width:width*2;sourceSize.height:height*2
    fillMode:Image.PreserveAspectFit;antialiasing:true;mipmap:true
}
