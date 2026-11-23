import QtQuick
Canvas {
    id:root
    property url source
    onSourceChanged:{if(source.toString()!=='')loadImage(source);else requestPaint()}
    onImageLoaded:requestPaint()
    onWidthChanged:requestPaint()
    Image {id:dimensions;source:root.source;visible:false;sourceSize.width:256;onStatusChanged:root.requestPaint()}
    onPaint:{
        let c=getContext('2d');c.reset();c.beginPath();c.arc(width/2,height/2,width/2,0,2*Math.PI);c.clip();
        if(source.toString()!=='' && isImageLoaded(source)){
            let iw=dimensions.implicitWidth||width,ih=dimensions.implicitHeight||height;let factor=Math.max(width/iw,height/ih)
            c.drawImage(source,(width-iw*factor)/2,(height-ih*factor)/2,iw*factor,ih*factor)
        }else{c.fillStyle='#aeb7b2';c.fillRect(0,0,width,height)}
    }
}
