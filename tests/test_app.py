import sys
from pathlib import Path
import swisseph as swe

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app import app, compute_positions, compute_chart_points


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
    # Check a couple of bodies rounded to two decimals
    sun_lon = f"{expected['Sun']:.2f}".encode()
    moon_lon = f"{expected['Moon']:.2f}".encode()
    assert sun_lon in resp.data
    assert moon_lon in resp.data
    chart_points = compute_chart_points(jd, 0, 0, b'P')
    asc_lon = f"{chart_points['asc']:.2f}".encode()
    cusp1 = f"{chart_points['cusps'][0]:.2f}".encode()
    assert asc_lon in resp.data
    assert cusp1 in resp.data

    # Check whole sign houses differ
    data['house_system'] = 'W'
    resp2 = client.post('/', data=data)
    assert resp2.status_code == 200
    chart_points_w = compute_chart_points(jd, 0, 0, b'W')
    cusp1_w = f"{chart_points_w['cusps'][0]:.2f}".encode()
    assert cusp1_w in resp2.data
