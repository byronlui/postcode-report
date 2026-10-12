import asyncio
import pytest
from shapely.geometry import Point
from app import ground
from app.core import UpstreamError


def test_geopackage_header_and_envelope():
    point=Point(1,2)
    for flag,padding in [(1,0),(3,32)]:
        blob=b'GP'+bytes([0,flag])+(27700).to_bytes(4,'little')+b'\0'*padding+point.wkb
        assert ground.gpkg_geometry(blob).equals(point)
    with pytest.raises(ValueError):ground.gpkg_geometry(b'not a geopackage')


def test_radon_is_grid_maximum_and_missing_is_not_low(monkeypatch):
    async def get(*args,**kwargs):return {'features':[{'attributes':{'TILE':'SU7775','CLASS_MAX':3,'VERSION':'v3'}}]},{}
    monkeypatch.setattr(ground.fetch,'get',get)
    p={'country':'England','latitude':51.47,'longitude':-.88}
    r=asyncio.run(ground.radon(p))
    assert r['rows'][0]['value']=='3–<5%'
    assert '最高' in r['rows'][0]['category']
    async def empty(*args,**kwargs):return {'features':[]},{}
    monkeypatch.setattr(ground.fetch,'get',empty)
    assert asyncio.run(ground.radon(p))['status']=='no_data'


def test_radon_service_error_never_becomes_empty_low(monkeypatch):
    async def get(*args,**kwargs):return {'error':{'code':400}},{}
    monkeypatch.setattr(ground.fetch,'get',get)
    with pytest.raises(UpstreamError):asyncio.run(ground.radon({'country':'England','latitude':51,'longitude':0}))


def test_ground_coverage_excludes_northern_ireland():
    p={'country':'Northern Ireland'}
    assert asyncio.run(ground.radon(p))['status']=='coverage_gap'
    assert asyncio.run(ground.geology(p))['status']=='coverage_gap'
