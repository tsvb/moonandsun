import sys
from pathlib import Path
import swisseph as swe

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app import app, compute_positions


def test_index_get():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Generate your natal chart' in resp.data


def test_index_post_positions():
    client = app.test_client()
    data = {
        'date': '2000-01-01',
        'time': '12:00',
        'tz_offset': '0',
        'latitude': '0',
        'longitude': '0',
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
