"""Bounded spatial queries for anonymised Police.uk points."""
import math
from .core import haversine

def bounds(raw,p):
    try:
        west,south,east,north=map(float,raw.split(','))
    except (ValueError,TypeError):raise ValueError('框選格式應為 west,south,east,north。')
    if not all(math.isfinite(v) for v in (west,south,east,north)) or not (-9<=west<east<=2 and 49<=south<north<=61):
        raise ValueError('請在英國附近選擇有效矩形。')
    area=haversine(south,west,north,west)*haversine(south,west,south,east)
    if area>400 or area<0.0001:raise ValueError('框選範圍須介乎 0.0001 至 400 km²，請調整地圖。')
    if haversine(p['latitude'],p['longitude'],(south+north)/2,(west+east)/2)>25:
        raise ValueError('請在 postcode 附近 25 km 內框選；其他地區請先更換 postcode。')
    return [west,south,east,north]

def query_shape(p):
    box=p.get('_crime_bbox');radius=p.get('_radius_km',1.609344)
    if box:
        w,s,e,n=box
        return {'mode':'rectangle','bbox':box},f'{s},{w}:{n},{w}:{n},{e}:{s},{e}'
    if not math.isfinite(radius) or not 0.1<=radius<=16.1:raise ValueError('治安搜尋半徑須介乎 0.1 至 16.1 km（約 10 miles）。')
    # Circumscribe the true circle, then precisely filter returned anonymous points.
    r=(radius+0.001)/math.cos(math.pi/32)/6371.0088
    lat,lon=map(math.radians,[p['latitude'],p['longitude']]);points=[]
    for i in range(32):
        angle=2*math.pi*i/32
        y=math.asin(math.sin(lat)*math.cos(r)+math.cos(lat)*math.sin(r)*math.cos(angle))
        x=lon+math.atan2(math.sin(angle)*math.sin(r)*math.cos(lat),math.cos(r)-math.sin(lat)*math.sin(y))
        points.append(f'{math.degrees(y):.6f},{math.degrees(x):.6f}')
    return {'mode':'circle','radius_km':radius,'radius_miles':radius/1.609344,'center':[p['latitude'],p['longitude']]},':'.join(points)

def contains(shape,lat,lon):
    if shape['mode']=='rectangle':
        w,s,e,n=shape['bbox'];return s<=lat<=n and w<=lon<=e
    return haversine(*shape['center'],lat,lon)<=shape['radius_km']+0.000001
