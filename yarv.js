//
//
//

var yarv_debugging = 1; // set to spew debugging to js console
var yarv_tracking = null; // which <img> are we tracking?


// make sure a number has 2 digits
function yarv_d2(x) {
    if (x<10) x = "0" + x;
    return x;
}

// Convert a unix timestamp to a readable datetime
function yarv_toStrDateTime(x, show_seconds) {
    var d = new Date(x*1000);
    var t = yarv_d2(d.getHours()) + ':' + yarv_d2(d.getMinutes());
    if (show_seconds) {
        t += ':' + yarv_d2(d.getSeconds());
    }
    d = d.getFullYear() + '-' + yarv_d2(d.getMonth()+1) + '-' + yarv_d2(d.getDate()) + ' ' + t;
    return d;
}

// (Re)load an image
function yarv_loadImage(imgid, start, end) {
    //alert(imgid);
    var show_seconds = (end-start) <= 3600;
    document.form1.start.value = yarv_toStrDateTime(start, show_seconds);
    document.form1.end.value = yarv_toStrDateTime(end, show_seconds);
    var img = document.getElementById(imgid);
    img.setAttribute('start', start);
    img.setAttribute('end', end);
    img.src = img.getAttribute('url')
        + '?' + 'w=' + img.getAttribute('graph_width') + '&amp;h=' + img.getAttribute('graph_height') + '&amp;r=' + img.getAttribute('rrd')
        + '&amp;s=' + start + '&amp;e=' + end;
}

// Stupid browser wars
function yarv_xlat_button(event) {
    if (event.which == null)
	    /* IE case */
	    return (event.button < 2) ? "LEFT" :
	    ((event.button == 4) ? "MIDDLE" : "RIGHT");

    /* All others */
    return (event.which < 2) ? "LEFT" :
	    ((event.which == 2) ? "MIDDLE" : "RIGHT");
}

// If left button pressed, start tracking
function yarv_mousedown(event, imgid) {
    event = event || window.event; // IE-ism
    if (yarv_xlat_button(event) != 'LEFT')
	    return;
    event.preventDefault();
    if (yarv_debugging) console.log('mousedown');
    yarv_tracking = imgid;
    var ss = document.getElementById('yarv_selrect').style;
    // FIXME: top and height should match graph and not track the mouse
    var img = document.getElementById(imgid);
    var top = img.getBoundingClientRect().top + parseInt(img.getAttribute('graph_top'));
    console.log('top='+top);
    ss.top = top+'px';
    ss.left = event.clientX+'px';
    ss.height = img.getAttribute('graph_height')+'px';
    ss.width = 1+'px';
    ss.display = 'block';
}

// Compute what timespan the selection rectangle spans
function yarv_selrect2time(ss) {
    var img = document.getElementById(yarv_tracking);
    var selwidth = parseInt(ss.width);
    var x1 = parseInt(ss.left);
    var x2 = x1+selwidth;
    var graph_left = parseInt(img.getAttribute('graph_left'));
    var img_left = parseInt(img.x);
    var xstart = img_left + graph_left;
    var start = parseInt(img.getAttribute('start'));
    var end = parseInt(img.getAttribute('end'));
    var diffsec = end - start;
    var dx1px = x1-xstart;
    var dx1sec = Math.floor(dx1px/img.getAttribute('graph_width')*diffsec);
    var dx2px = x2-xstart;
    var dx2sec = Math.floor(dx2px/img.getAttribute('graph_width')*diffsec);

    if (yarv_debugging) {
        console.log('start='+start+'('+yarv_toStrDateTime(start, 1)+'), end='+end+'('+yarv_toStrDateTime(end, 1)+')');
        console.log('diffsec='+diffsec);
        console.log('graph_left='+graph_left+', img_left='+img_left);
        console.log('xstart='+xstart+', x1='+x1+', dx1px='+dx1px+', dx1sec='+dx1sec);
    }
    var s = start+dx1sec;
    var e = start+dx2sec;

    if (yarv_debugging) console.log( s+'('+yarv_toStrDateTime(s, 1) + ') - ' + e + '(' + yarv_toStrDateTime(e, 1) + ')' );
    return { s:s, e:e };
}

// Is this an end-of-tracking mouseup? If so, zoom in or out
function yarv_mouseup(event) {
    if (!yarv_tracking)
	    return;

    if (yarv_xlat_button(event) != 'LEFT')
	    return;

    if (yarv_debugging) console.log('mouseup');
    var ss = document.getElementById('yarv_selrect').style;
    ss.display='none';

    var img = document.getElementById(yarv_tracking);

    ///alert(yarv_selrect.style.left+'-'+ss.width);
    var selwidth = parseInt(ss.width);
    if (selwidth <= 1) {
	    zoomOut(yarv_tracking, img);
        yarv_tracking = null;
	    return;
    }

    var x = yarv_selrect2time(ss);
    var h = img.getAttribute('history');
    if (!h)
        h = new Array();
    else
        h = JSON.parse(h);
    h.push(x);
    img.setAttribute('history', JSON.stringify(h));

    var imgid = yarv_tracking;
    yarv_tracking = null;
    yarv_loadImage(imgid, x.s, x.e);
}

// FIXME: Don't let selrect out of real graph area

// If tracking, update selrect
function yarv_mousemove(event) {
    if (yarv_xlat_button(event) != 'LEFT')
	    return;

    if (!yarv_tracking)
	    return;

    if (yarv_debugging) console.log('mousemove');
    event = event || window.event; // IE-ism

    if(event.offsetX || event.offsetY) { //For Internet Explorer
	    x=event.offsetX;
	    y=event.offsetY;
    } else { //For FireFox
	    x=event.pageX;
	    y=event.pageY;
    } 
    var ss = document.getElementById('yarv_selrect').style;
//    ss.height=(y-parseInt(ss.top)) + 'px';
    ss.width=(x-parseInt(ss.left)) + 'px';
    if (yarv_debugging) yarv_selrect2time(ss);
}

/* Never called? Just leave the alert in to see if it is ever called */
function yarv_losecapture() {
    yarv_tracking = null;
    document.getElementById('yarv_selrect').style.display = 'none';
    alert('capture lost');
}

// Zoom out, called on single click
function zoomOut(imgid, img) {
    var start = parseInt(img.getAttribute('start'));
    var end = parseInt(img.getAttribute('end'));
    var sh = img.getAttribute('history');
    var history;
    if (sh) {
        var history = JSON.parse(sh);
	    var x=history.pop();
    }

    if (!sh || !x) {
	    var diffsec = end - start;
	    start -= diffsec;
	    end += diffsec;
	    var now = Math.floor((new Date()).valueOf()/1000);
	    if (now < end) {
	        diffsec = end - now;
	        start -= diffsec;
	        end -= diffsec;
	    }
    } else {
	    start=x.s;
	    end=x.e;
        img.setAttribute('history', JSON.stringify(history));
    }
    yarv_loadImage(imgid, start, end);
}

// Set eventlisteners
if (document.addEventListener) {
    document.addEventListener('mouseup', function (event) {yarv_mouseup(event)});
} else if (document.attachEvent) {
    document.attachEvent('mouseup', function (event) {yarv_mouseup(event)});
} else
    alert('Cannot register mouseup event listener');



