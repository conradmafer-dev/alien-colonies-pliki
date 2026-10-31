"""Optical measurements only; no raster pixels are modified here."""
import math
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, label, find_objects


def optical_core(path, name, side=None):
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        rgb=np.asarray(image.convert('RGB')).astype(float)
    h,w=rgb.shape[:2]
    gray=rgb@np.array([.2126,.7152,.0722])
    low,high=(.70,.999) if side=='left' else ((.001,.30) if side=='right' else (.4,.6))
    top,bottom=int(h*.30),int(h*.65)
    left,right=int(w*low),int(w*high)
    if name not in ('void','eclipse'):
        smooth=gaussian_filter(gray,14)
        roi=smooth[top:bottom,left:right]
        y,x=np.unravel_index(np.argmax(roi),roi.shape)
        return {'core_pixels':[float(x+left),float(y+top)],'dimensions':[w,h]}
    roi=np.zeros(gray.shape,dtype=bool);roi[top:bottom,left:right]=True
    components,_=label((gray<26)&roi)
    candidates=[]
    for index,slices in enumerate(find_objects(components),1):
        if slices is None:continue
        y,x=slices
        mask=components[slices]==index
        area=int(np.count_nonzero(mask));bw,bh=x.stop-x.start,y.stop-y.start
        if area<45 or max(bw,bh)>w*.10 or min(bw,bh)<5 or not .65<bw/bh<1.6:continue
        fill=area/(bw*bh)
        if fill<.5:continue
        ys,xs=np.nonzero(mask)
        cx,cy=float(xs.mean()+x.start),float(ys.mean()+y.start)
        border=math.ceil(max(bw,bh)*.35)+3
        ring=gray[max(0,y.start-border):min(h,y.stop+border),max(0,x.start-border):min(w,x.stop+border)]
        inner=gray[slices]
        annulus=(float(ring.sum())-float(inner.sum()))/max(1,ring.size-inner.size)
        contrast=annulus-float(inner[mask].mean())
        candidates.append((contrast+12*fill,cx,cy,int(bw),int(bh),contrast))
    assert candidates, (str(path),name,side)
    _,cx,cy,bw,bh,contrast=max(candidates)
    return {'core_pixels':[cx,cy],'dimensions':[w,h],'dark_horizon_bbox':[bw,bh],
            'dark_horizon_radius_pixels':max(bw,bh)/2,'rim_contrast':contrast}
