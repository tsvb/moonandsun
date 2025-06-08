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
    filter_aspects_for_wheel,
    compute_dignities,
    compute_aspects_to_angles,
    detect_chart_patterns,
    compute_synastry_aspects,
    secondary_progressions,
    solar_arc_progressions,
    solar_return_jd,
    lunar_return_jd,
    transits,
    electional_days,
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

    assert 'Chiron' in expected
    assert 'Black Moon Lilith' in expected
    vertex_str = format_longitude(chart_points['vertex']).replace("'", "&#39;").encode()
    pof_str = format_longitude(chart_points['part_of_fortune']).replace("'", "&#39;").encode()
    assert vertex_str in resp.data
    assert pof_str in resp.data

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


def test_extended_aspects():
    jd = swe.julday(2000, 1, 1, 12.0)
    positions = compute_positions(jd)
    aspects = compute_aspects(positions)

    assert any(
        a['planet1'] == 'Mercury' and a['planet2'] == 'Venus' and a['aspect'] == 'Semi-sextile'
        for a in aspects
    )
    assert any(
        a['planet1'] == 'Saturn' and a['planet2'] == 'Pluto' and a['aspect'] == 'Quincunx'
        for a in aspects
    )
    assert any(
        a['planet1'] == 'Jupiter' and a['planet2'] == 'Pluto' and a['aspect'] == 'Sesquiquadrate'
        for a in aspects
    )

    jd2 = swe.julday(2020, 1, 1, 12.0)
    pos2 = compute_positions(jd2)
    aspects2 = compute_aspects(pos2)
    assert any(
        a['planet1'] == 'Uranus' and a['planet2'] == 'Neptune' and a['aspect'] == 'Semi-square'
        for a in aspects2
    )


def test_aspect_sorting_and_keywords():
    jd = swe.julday(2000, 1, 1, 12.0)
    positions = compute_positions(jd)
    aspects = compute_aspects(positions)
    assert len(aspects) >= 2
    assert aspects[0]['strength'] >= aspects[1]['strength']
    assert 'type' in aspects[0]
    assert 'keywords' in aspects[0]


def test_compute_retrogrades():
    jd_direct = swe.julday(2000, 1, 1, 12.0)
    jd_retro = swe.julday(2020, 6, 20, 0.0)
    retro_direct = compute_retrogrades(jd_direct)
    retro_retro = compute_retrogrades(jd_retro)
    assert not retro_direct['Mercury']
    assert retro_retro['Mercury']


def test_retrograde_indicator_display():
    client = app.test_client()
    data = {
        'date': '2020-06-20',
        'time': '00:00',
        'tz_offset': '0',
        'latitude': '0',
        'longitude': '0',
        'house_system': 'P'
    }
    resp = client.post('/', data=data)
    assert resp.status_code == 200
    assert '℞'.encode('utf-8') in resp.data


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


def test_filter_aspects_for_wheel():
    jd = swe.julday(2000, 1, 1, 12.0)
    positions = compute_positions(jd)
    aspects = compute_aspects(positions)
    filtered = filter_aspects_for_wheel(aspects, max_minor=2)
    # Ensure only a small number of minor aspects remain
    minor_count = sum(1 for a in filtered if a['type'] == 'minor')
    assert minor_count <= 2
    # All major aspects should still be present
    major = [a for a in aspects if a['type'] == 'major']
    for ma in major:
        assert any(
            ma['planet1'] == f['planet1'] and ma['planet2'] == f['planet2'] and ma['aspect'] == f['aspect']
            for f in filtered
        )


def test_birth_date_validation():
    client = app.test_client()
    data = {
        'date': '1700-01-01',
        'time': '12:00',
        'tz_offset': '0',
        'latitude': '0',
        'longitude': '0',
        'house_system': 'P'
    }
    resp = client.post('/', data=data)
    assert resp.status_code == 200
    assert b'Date must be between' in resp.data


def test_compute_dignities():
    positions = {'Sun': 130.0, 'Moon': 95.0}
    dignities = compute_dignities(positions)
    assert dignities['Sun'] == 'Domicile'
    assert dignities['Moon'] == 'Domicile'


def test_aspects_to_angles():
    positions = {'Sun': 0.0}
    aspects = compute_aspects_to_angles(positions, 0.0, 90.0)
    assert any(
        a['aspect'] == 'Conjunction' and 'Ascendant' in (a['planet1'], a['planet2'])
        for a in aspects
    )


def test_detect_chart_patterns():
    positions = {
        'Sun': 0.0,
        'Jupiter': 120.0,
        'Mars': 240.0,
        'Saturn': 180.0,
        'Mercury': 90.0,
    }
    aspects = compute_aspects(positions)
    patterns = detect_chart_patterns(aspects, positions)
    assert ('Jupiter', 'Mars', 'Sun') in patterns['grand_trines']
    ts_match = [ts for ts in patterns['t_squares'] if set(ts['planets']) == {'Mercury', 'Saturn', 'Sun'}]
    assert ts_match and ts_match[0]['type'] == 'Cardinal'
    assert ('Jupiter', 'Mars', 'Saturn', 'Sun') in patterns['kites']


def test_yod_and_stellium_detection():
    positions = {
        'Mercury': 0.0,
        'Venus': 5.0,
        'Sun': 7.0,
        'Jupiter': 60.0,
        'Mars': 210.0,
    }
    aspects = compute_aspects(positions)
    patterns = detect_chart_patterns(aspects, positions)
    assert any(s['sign'] == 'Aries' for s in patterns['stelliums'])
    assert ('Jupiter', 'Mars', 'Mercury') in patterns['yods']


def test_big_four_asteroids_and_parts():
    jd = swe.julday(2000, 1, 1, 12.0)
    positions = compute_positions(jd)
    for name in ['Ceres', 'Pallas', 'Juno', 'Vesta']:
        assert name in positions
    points = compute_chart_points(jd, 0, 0, b'P')
    for key in ['part_of_spirit', 'part_of_love', 'part_of_marriage', 'part_of_death']:
        assert key in points


def test_true_node_option():
    jd = swe.julday(2000, 1, 1, 12.0)
    mean_pos = compute_positions(jd, 'mean')
    true_pos = compute_positions(jd, 'true')
    assert 'Mean Node' in mean_pos
    assert 'True Node' in true_pos
    assert mean_pos['Mean Node'] != true_pos['True Node']


def test_compute_synastry_aspects():
    chart1 = {'Sun': 0.0, 'Moon': 90.0}
    chart2 = {'Sun': 180.0, 'Moon': 0.0}
    syn = compute_synastry_aspects(chart1, chart2)
    cross = syn['cross_aspects']
    assert any(
        a['planet1'] == 'Sun' and a['planet2'] == 'Sun' and a['aspect'] == 'Opposition'
        for a in cross
    )
    assert syn['composite_positions']['Sun'] == 90.0


def test_secondary_progressions():
    natal_jd = swe.julday(2000, 1, 1, 12.0)
    target_jd = swe.julday(2030, 1, 1, 12.0)
    prog = secondary_progressions(natal_jd, target_jd)
    expect = compute_positions(natal_jd + (target_jd - natal_jd) / 365.25)
    assert abs(prog['Sun'] - expect['Sun']) < 1e-6


def test_solar_arc_progressions():
    natal_jd = swe.julday(2000, 1, 1, 12.0)
    target_jd = swe.julday(2030, 1, 1, 12.0)
    prog = solar_arc_progressions(natal_jd, target_jd)
    natal = compute_positions(natal_jd)
    target = compute_positions(target_jd)
    arc = (target['Sun'] - natal['Sun']) % 360
    expected = (natal['Moon'] + arc) % 360
    assert abs(prog['Moon'] - expected) < 1e-6


def test_returns_and_transits():
    natal_jd = swe.julday(2000, 1, 1, 12.0)
    natal = compute_positions(natal_jd)
    sr_jd = solar_return_jd(natal_jd, 1)
    diff_sun = ((compute_positions(sr_jd)['Sun'] - natal['Sun'] + 180) % 360) - 180
    assert abs(diff_sun) < 1e-4
    lr_jd = lunar_return_jd(natal_jd, 1)
    diff_moon = ((compute_positions(lr_jd)['Moon'] - natal['Moon'] + 180) % 360) - 180
    assert abs(diff_moon) < 1e-4
    t = transits(natal, sr_jd)
    assert 'positions' in t and 'aspects' in t
    assert t['aspects']


def test_electional_days():
    natal_jd = swe.julday(2000, 1, 1, 12.0)
    natal = compute_positions(natal_jd)
    start = swe.julday(2000, 1, 15, 0.0)
    end = swe.julday(2000, 1, 25, 0.0)
    days = electional_days(natal, start, end)
    assert days and all(start <= d <= end for d in days)


