"""Small, validated 2D scene objects. Coordinates use the 1600 × 900 desktop."""
import math,uuid
from pathlib import Path
import json
CATALOG=json.loads((Path(__file__).resolve().parent/'assets/furniture/catalog.json').read_text(encoding='utf-8'))

def normalize_item(value):
    if not isinstance(value,dict) or value.get('kind') not in CATALOG:return None
    kind=value['kind'];spec=CATALOG[kind];out={'id':str(value.get('id') or uuid.uuid4().hex)[:64],'kind':kind,'image':str(value.get('image',''))[:4096],'flipped':bool(value.get('flipped',False)),'locked':bool(value.get('locked',False)),'animate':bool(value.get('animate',True))}
    def number(key,default,lo,hi):
        try:v=float(value.get(key,default));return max(lo,min(hi,v)) if math.isfinite(v) else default
        except (ValueError,TypeError,OverflowError):return default
    out.update(width=number('width',spec['width'],70,760),height=number('height',spec['height'],70,760),scale=number('scale',1,.25,2),rotation=number('rotation',0,-180,180),z=int(number('z',-20,-100,80)))
    angle=math.radians(out['rotation']);c=math.cos(angle);s=math.sin(angle);w=out['width'];h=out['height']
    span_x=abs(w*c)+abs(h*s);span_y=abs(w*s)+abs(h*c)
    out['scale']=min(out['scale'],1600/max(1,span_x),860/max(1,span_y))
    points=[(x*out['scale']*c-y*out['scale']*s,x*out['scale']*s+y*out['scale']*c) for x,y in [(0,0),(w,0),(0,h),(w,h)]]
    out['x']=number('x',500,-min(v[0] for v in points),1600-max(v[0] for v in points));out['y']=number('y',500,40-min(v[1] for v in points),900-max(v[1] for v in points))
    return out
