"""Export our own simple SVG diagrams to PNG; no generated raster image is edited."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

root=Path(__file__).resolve().parent
scale=2
font_cache={}
def color(value):
    return None if value in (None,'none') else value
def font(size,bold):
    key=(size,bold)
    if key not in font_cache:
        font_cache[key]=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf',size)
    return font_cache[key]
for svg in root.glob('*.svg'):
    doc=ET.parse(svg).getroot()
    w,h=int(doc.attrib['width']),int(doc.attrib['height'])
    im=Image.new('RGB',(w*scale,h*scale),'white')
    draw=ImageDraw.Draw(im)
    for item in doc.iter():
        tag=item.tag.split('}')[-1];a=item.attrib
        fill=color(a.get('fill'));stroke=color(a.get('stroke'))
        width=max(1,round(float(a.get('stroke-width',1))*scale))
        if tag=='rect':
            x,y,ww,hh=[float(a.get(k,0))*scale for k in ('x','y','width','height')]
            draw.rounded_rectangle((x,y,x+ww,y+hh),radius=float(a.get('rx',0))*scale,fill=fill,outline=stroke,width=width)
        elif tag=='circle':
            x,y,r=[float(a[k])*scale for k in ('cx','cy','r')]
            draw.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=stroke,width=width)
        elif tag=='polyline':
            nums=[float(n)*scale for n in re.findall(r'-?\d+(?:\.\d+)?',a['points'])]
            pts=list(zip(nums[::2],nums[1::2]))
            draw.line(pts,fill=stroke,width=width,joint='curve')
        elif tag=='line':
            xy=[float(a[k])*scale for k in ('x1','y1','x2','y2')]
            draw.line(xy,fill=stroke,width=width)
        elif tag=='path':
            nums=[float(n)*scale for n in re.findall(r'-?\d+(?:\.\d+)?',a['d'])]
            pts=list(zip(nums[::2],nums[1::2]))
            if a['d'].strip().endswith('Z'):pts.append(pts[0])
            draw.line(pts,fill=stroke,width=width,joint='curve')
        elif tag=='text':
            xy=(float(a['x'])*scale,float(a['y'])*scale)
            anchor={'start':'ls','middle':'ms','end':'rs'}.get(a.get('text-anchor','start'),'ls')
            draw.text(xy,item.text or '',font=font(round(float(a['font-size'])*scale),a.get('font-weight')=='700'),fill=fill or '#17212b',anchor=anchor)
    im.save(svg.with_suffix('.png'))
    print(svg.with_suffix('.png'))
