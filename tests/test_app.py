import sys
from pathlib import Path
import swisseph as swe
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app import (
    app,
    compute_positions,
    compute_chart_points,
    format_longitude,
    compute_house_positions,
    compute_aspects,
    chart_ruler,
    compute_retrogrades,
)


def test_index_get():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Generate your natal chart' in resp.data
    assert b'House system' in resp.data


def test_index_post_positions():
    client = app.test_client()
    data = {
        'date': '2000-01-01',
        'time': '12:00',
        'tz_offset': '0',
        'latitude': '0',
        'longitude': '0',
        'house_system': 'P'
    }
    resp = client.post('/', data=data)
    assert resp.status_code == 200
    jd = swe.julday(2000, 1, 1, 12.0)
    expected = compute_positions(jd)
    chart_points = compute_chart_points(jd, 0, 0, b'P')
    houses = compute_house_positions(expected, chart_points['cusps'])
    # check formatted body positions and house numbers appear
    sun_pos = format_longitude(expected['Sun']).replace("'", "&#39;").encode()
    moon_pos = format_longitude(expected['Moon']).replace("'", "&#39;").encode()
    assert sun_pos in resp.data
    assert moon_pos in resp.data
    sun_house_fragment = f">{houses['Sun']}<".encode()
    assert sun_house_fragment in resp.data
    # also check ascendant and first cusp formatting
    asc_str = format_longitude(chart_points['asc']).replace("'", "&#39;").encode()
    cusp1 = format_longitude(chart_points['cusps'][0]).replace("'", "&#39;").encode()
    assert asc_str in resp.data
    assert cusp1 in resp.data

    # Check whole sign houses differ
    data['house_system'] = 'W'
    resp2 = client.post('/', data=data)
    assert resp2.status_code == 200
    chart_points_w = compute_chart_points(jd, 0, 0, b'W')
    cusp1_w = format_longitude(chart_points_w['cusps'][0]).replace("'", "&#39;").encode()
    assert cusp1_w in resp2.data
    assert b'data:image/png;base64' in resp.data


def test_aspects_and_chart_ruler():
    jd = swe.julday(2000, 1, 1, 12.0)
    positions = compute_positions(jd)
    aspects = compute_aspects(positions)
    assert any(
        a['planet1'] == 'Sun' and a['planet2'] == 'Saturn' and a['aspect'] == 'Trine'
        for a in aspects
    )
    chart_points = compute_chart_points(jd, 0, 0, b'P')
    assert chart_ruler(chart_points['asc']) == 'Mars'


def test_compute_retrogrades():
    jd_direct = swe.julday(2000, 1, 1, 12.0)
    jd_retro = swe.julday(2020, 6, 20, 0.0)
    retro_direct = compute_retrogrades(jd_direct)
    retro_retro = compute_retrogrades(jd_retro)
    assert not retro_direct['Mercury']
    assert retro_retro['Mercury']


def test_city_lookup_failure(monkeypatch):
    client = app.test_client()
    data = {
        'date': '2000-01-01',
        'time': '12:00',
        'tz_offset': '0',
        'city': 'Nowhere',
        'latitude': '',
        'longitude': '',
        'house_system': 'P'
    }

    def mock_get(*args, **kwargs):
        raise requests.RequestException()

    monkeypatch.setattr('app.requests.get', mock_get)
    resp = client.post('/', data=data)
    assert resp.status_code == 200
    assert b'City lookup failed' in resp.data

