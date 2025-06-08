from flask import Flask, render_template, request, flash, send_file, redirect, url_for
import swisseph as swe
import datetime
import requests
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo
import io
import base64
import mpld3
import math
import matplotlib.pyplot as plt
import os
import json
import re
import time
from pathlib import Path

ZODIAC_SIGNS = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
]

# Signs grouped by modality for pattern classification
MODALITY_SIGNS = {
    'Cardinal': ['Aries', 'Cancer', 'Libra', 'Capricorn'],
    'Fixed': ['Taurus', 'Leo', 'Scorpio', 'Aquarius'],
    'Mutable': ['Gemini', 'Virgo', 'Sagittarius', 'Pisces'],
}

# Glyphs for zodiac signs and planets to draw nicer chart wheels
ZODIAC_GLYPHS = [
    '♈', '♉', '♊', '♋', '♌', '♍',
    '♎', '♏', '♐', '♑', '♒', '♓'
]

PLANET_GLYPHS = {
    'Sun': '☉',
    'Moon': '☽',
    'Mercury': '☿',
    'Venus': '♀',
    'Mars': '♂',
    'Jupiter': '♃',
    'Saturn': '♄',
    'Uranus': '♅',
    'Neptune': '♆',
    'Pluto': '♇',
    'Chiron': '⚷',
    'Mean Node': '☊',
    'Black Moon Lilith': '⚸',
}

# Mapping of zodiac signs to their ruling planets for chart ruler detection
SIGN_RULERS = {
    'Aries': 'Mars',
    'Taurus': 'Venus',
    'Gemini': 'Mercury',
    'Cancer': 'Moon',
    'Leo': 'Sun',
    'Virgo': 'Mercury',
    'Libra': 'Venus',
    'Scorpio': 'Pluto',
    'Sagittarius': 'Jupiter',
    'Capricorn': 'Saturn',
    'Aquarius': 'Uranus',
    'Pisces': 'Neptune',
}

HOUSE_SYSTEMS = {
    'P': 'Placidus',
    'W': 'Whole Sign',
    'K': 'Koch',
    'E': 'Equal House',
    'C': 'Campanus',
    'R': 'Regiomontanus',
    'O': 'Porphyry',
}

# IDs for JPL Horizons lookup of additional bodies
HORIZONS_IDS = {
    'Ceres': '1',
    'Pallas': '2',
    'Juno': '3',
    'Vesta': '4',
}

# Directory to store saved chart images and metadata
CHARTS_DIR = Path('saved_charts')
CHARTS_DIR.mkdir(exist_ok=True)
CHARTS_INDEX = CHARTS_DIR / 'charts.json'
if not CHARTS_INDEX.exists():
    CHARTS_INDEX.write_text('[]')

# Chart wheel size can be adjusted via the CHART_FIGSIZE environment variable
try:
    CHART_FIGSIZE = tuple(
        float(x) for x in os.environ.get('CHART_FIGSIZE', '6,6').split(',')[:2]
    )
    if len(CHART_FIGSIZE) != 2:
        raise ValueError
except Exception:
    CHART_FIGSIZE = (6.0, 6.0)

# theme customization via CHART_THEME environment variable
CHART_THEME = os.environ.get('CHART_THEME', 'light').lower()
THEMES = {
    'light': {
        'bg': 'white',
        'fg': 'black',
        'aspect_colors': {
            'Conjunction': 'green',
            'Opposition': 'red',
            'Square': 'red',
            'Trine': 'green',
            'Sextile': 'blue',
        },
    },
    'dark': {
        'bg': '#222',
        'fg': 'white',
        'aspect_colors': {
            'Conjunction': '#0f0',
            'Opposition': '#f55',
            'Square': '#f55',
            'Trine': '#0f0',
            'Sextile': '#59f',
        },
    },
}
THEME = THEMES.get(CHART_THEME, THEMES['light'])

# enable interactive chart wheel output
CHART_INTERACTIVE = os.environ.get('CHART_INTERACTIVE', '0') == '1'


def cleanup_saved_charts(max_age_days: int = 30) -> None:
    """Remove PNG files not referenced in the index or older than max_age_days."""
    now = time.time()
    try:
        charts = load_charts()
        valid = {c.get('file') for c in charts}
    except Exception:
        valid = set()
    for path in CHARTS_DIR.glob('*.png'):
        age = now - path.stat().st_mtime
        if path.name not in valid or age > max_age_days * 86400:
            try:
                path.unlink()
            except OSError:
                pass
    # prune entries that point to missing files
    try:
        charts = [c for c in charts if (CHARTS_DIR / c.get('file', '')).exists()]
        save_charts(charts)
    except Exception:
        pass

# Clean up any stale chart images on startup
cleanup_saved_charts()

# Aspect configuration: aspect angle and maximum orb
ASPECTS_INFO = {
    'Conjunction': {
        'angle': 0,
        'orb': 8,
        'type': 'major',
        'keywords': 'blending, emphasis',
    },
    'Opposition': {
        'angle': 180,
        'orb': 8,
        'type': 'major',
        'keywords': 'tension, awareness',
    },
    'Square': {
        'angle': 90,
        'orb': 6,
        'type': 'major',
        'keywords': 'challenge, action',
    },
    'Trine': {
        'angle': 120,
        'orb': 6,
        'type': 'major',
        'keywords': 'harmony, ease',
    },
    'Sextile': {
        'angle': 60,
        'orb': 4,
        'type': 'major',
        'keywords': 'opportunity, cooperation',
    },
    # Extended aspects
    'Quincunx': {
        'angle': 150,
        'orb': 3,
        'type': 'minor',
        'keywords': 'adjustment, discomfort',
    },
    'Semi-sextile': {
        'angle': 30,
        'orb': 2,
        'type': 'minor',
        'keywords': 'mild growth, awareness',
    },
    'Semi-square': {
        'angle': 45,
        'orb': 2,
        'type': 'minor',
        'keywords': 'irritation, friction',
    },
    'Sesquiquadrate': {
        'angle': 135,
        'orb': 2,
        'type': 'minor',
        'keywords': 'pressure, imbalance',
    },
}


def load_charts():
    with open(CHARTS_INDEX) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_charts(charts):
    with open(CHARTS_INDEX, 'w') as f:
        json.dump(charts, f)


def format_longitude(deg):
    """Return a string like "10° Capricorn 30'" for a longitude."""
    sign_index = int(deg // 30) % 12
    sign = ZODIAC_SIGNS[sign_index]
    degree_in_sign = deg % 30
    whole_deg = int(degree_in_sign)
    minutes = int(round((degree_in_sign - whole_deg) * 60))
    if minutes == 60:
        whole_deg += 1
        minutes = 0
        if whole_deg == 30:
            whole_deg = 0
            sign_index = (sign_index + 1) % 12
            sign = ZODIAC_SIGNS[sign_index]
    return f"{whole_deg}° {sign} {minutes:02d}'"


def house_for(longitude, cusps):
    """Return house number (1-12) for a longitude given cusp list."""
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if end < start:
            end += 360
        lon = longitude
        if lon < start:
            lon += 360
        if start <= lon < end:
            return i + 1
    return 12


def compute_house_positions(positions, cusps):
    """Return mapping of body name to house number."""
    return {name: house_for(pos, cusps) for name, pos in positions.items()}


def compute_chart_points(jd, lat, lon, hsys=b'P'):
    """Return Ascendant, Midheaven and various Arabic parts."""
    cusps, ascmc = swe.houses(jd, lat, lon, hsys)
    asc = ascmc[0]
    mc = ascmc[1]
    vertex = ascmc[3]

    sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
    moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
    venus_lon = swe.calc_ut(jd, swe.VENUS)[0][0]
    saturn_lon = swe.calc_ut(jd, swe.SATURN)[0][0]
    desc = cusps[6]

    sun_house = house_for(sun_lon, list(cusps))
    if sun_house >= 7:
        pof = (asc + moon_lon - sun_lon) % 360
        pos = (asc + sun_lon - moon_lon) % 360
    else:
        pof = (asc + sun_lon - moon_lon) % 360
        pos = (asc + moon_lon - sun_lon) % 360

    pol = (asc + venus_lon - sun_lon) % 360
    pom = (asc + desc - venus_lon) % 360
    pod = (asc + saturn_lon - moon_lon) % 360

    return {
        'asc': asc,
        'mc': mc,
        'vertex': vertex,
        'part_of_fortune': pof,
        'part_of_spirit': pos,
        'part_of_love': pol,
        'part_of_marriage': pom,
        'part_of_death': pod,
        'cusps': list(cusps),
    }


def fetch_horizons_info(jd, command):
    """Return (lon, speed) for a body using JPL Horizons."""
    url = "https://ssd.jpl.nasa.gov/api/horizons.api"
    params = {
        "format": "text",
        "COMMAND": command,
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "V",
        "CENTER": "500@399",
        "START_TIME": f"JD{jd}",
        "STOP_TIME": f"JD{jd + 1e-4}",
        "STEP_SIZE": "1d",
        "OUT_UNITS": "AU-D",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "$$SOE" and i + 3 < len(lines):
            coords_line = lines[i + 2]
            vel_line = lines[i + 3]
            import re, math
            c_match = re.search(
                r"X\s*=\s*([+-]?\d+\.\d+E[+-]\d+)\s*Y\s*=\s*([+-]?\d+\.\d+E[+-]\d+)\s*Z\s*=\s*([+-]?\d+\.\d+E[+-]\d+)",
                coords_line,
            )
            v_match = re.search(
                r"VX=\s*([+-]?\d+\.\d+E[+-]\d+)\s*VY=\s*([+-]?\d+\.\d+E[+-]\d+)\s*VZ=\s*([+-]?\d+\.\d+E[+-]\d+)",
                vel_line,
            )
            if c_match and v_match:
                x, y, _ = [float(v) for v in c_match.groups()]
                vx, vy, _ = [float(v) for v in v_match.groups()]
                lon = math.degrees(math.atan2(y, x)) % 360
                speed = math.degrees((x * vy - y * vx) / (x * x + y * y))
                return (lon, 0.0, 0.0, speed, 0.0, 0.0)
    raise RuntimeError("Could not parse Horizons response")


def fetch_chiron_info(jd):
    return fetch_horizons_info(jd, "2060")

def compute_body_info(jd, node_type: str = 'mean'):
    """Return longitude and speed for each major body."""

    node_name = 'True Node' if node_type == 'true' else 'Mean Node'
    node_const = swe.TRUE_NODE if node_type == 'true' else swe.MEAN_NODE
    planets = {
        'Sun': swe.SUN,
        'Moon': swe.MOON,
        'Mercury': swe.MERCURY,
        'Venus': swe.VENUS,
        'Mars': swe.MARS,
        'Jupiter': swe.JUPITER,
        'Saturn': swe.SATURN,
        'Uranus': swe.URANUS,
        'Neptune': swe.NEPTUNE,
        'Pluto': swe.PLUTO,
        node_name: node_const,
        'Ceres': swe.CERES,
        'Pallas': swe.PALLAS,
        'Juno': swe.JUNO,
        'Vesta': swe.VESTA,
        'Chiron': swe.CHIRON,
        'Black Moon Lilith': swe.MEAN_APOG,
    }
    info = {}
    for name, body in planets.items():
        try:
            if name == 'Black Moon Lilith':
                vals = swe.calc_ut(jd, body, swe.FLG_MOSEPH | swe.FLG_SPEED)[0]
            else:
                vals = swe.calc_ut(jd, body)[0]
        except swe.Error:
            if name == 'Chiron':
                vals = fetch_chiron_info(jd)
            elif name in HORIZONS_IDS:
                vals = fetch_horizons_info(jd, HORIZONS_IDS[name])
            else:
                raise
        info[name] = (vals[0], vals[3])
    return info

def compute_positions(jd, node_type: str = 'mean'):
    """Return ecliptic longitudes of major bodies for given Julian day."""
    info = compute_body_info(jd, node_type)
    return {name: vals[0] for name, vals in info.items()}

def compute_retrogrades(jd, node_type: str = 'mean'):
    """Return True for bodies that are retrograde on the given day."""
    info = compute_body_info(jd, node_type)
    return {name: vals[1] < 0 for name, vals in info.items()}


def opposite_sign(sign: str) -> str:
    """Return the sign opposite the given one."""
    idx = ZODIAC_SIGNS.index(sign)
    return ZODIAC_SIGNS[(idx + 6) % 12]


DOMICILE_SIGNS = {
    'Sun': ['Leo'],
    'Moon': ['Cancer'],
    'Mercury': ['Gemini', 'Virgo'],
    'Venus': ['Taurus', 'Libra'],
    'Mars': ['Aries', 'Scorpio'],
    'Jupiter': ['Sagittarius', 'Pisces'],
    'Saturn': ['Capricorn', 'Aquarius'],
    'Uranus': ['Aquarius'],
    'Neptune': ['Pisces'],
    'Pluto': ['Scorpio'],
}


EXALTATION_SIGNS = {
    'Sun': 'Aries',
    'Moon': 'Taurus',
    'Mercury': 'Virgo',
    'Venus': 'Pisces',
    'Mars': 'Capricorn',
    'Jupiter': 'Cancer',
    'Saturn': 'Libra',
    'Uranus': 'Scorpio',
    'Neptune': 'Leo',
    'Pluto': 'Aries',
}


def compute_dignities(positions):
    """Return essential dignity for each body if applicable."""
    dignities = {}
    for name, lon in positions.items():
        sign_idx = int(lon // 30) % 12
        sign = ZODIAC_SIGNS[sign_idx]
        dom = DOMICILE_SIGNS.get(name, [])
        if sign in dom:
            dignities[name] = 'Domicile'
            continue
        if any(opposite_sign(s) == sign for s in dom):
            dignities[name] = 'Detriment'
            continue
        ex_sign = EXALTATION_SIGNS.get(name)
        if ex_sign and sign == ex_sign:
            dignities[name] = 'Exaltation'
            continue
        if ex_sign and opposite_sign(ex_sign) == sign:
            dignities[name] = 'Fall'
            continue
        dignities[name] = ''
    return dignities


def angular_distance(lon1, lon2):
    """Return smallest angular distance between two longitudes."""
    diff = abs(lon1 - lon2) % 360
    if diff > 180:
        diff = 360 - diff
    return diff


def compute_aspects(positions):
    """Return list of aspects between bodies with orb and strength."""
    aspects = []
    names = list(positions.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p1 = names[i]
            p2 = names[j]
            diff = angular_distance(positions[p1], positions[p2])
            for aspect, info in ASPECTS_INFO.items():
                orb = abs(diff - info['angle'])
                if orb <= info['orb']:
                    strength = max(0.0, 1 - orb / info['orb'])
                    importance = ''
                    if orb <= 0.5:
                        importance = 'exact'
                    elif orb <= 1.0:
                        importance = 'close'
                    aspects.append({
                        'planet1': p1,
                        'planet2': p2,
                        'aspect': aspect,
                        'orb': orb,
                        'strength': strength,
                        'type': info.get('type', 'minor'),
                        'keywords': info.get('keywords', ''),
                        'importance': importance,
                    })
    aspects.sort(key=lambda a: a['strength'], reverse=True)
    return aspects


def compute_aspects_to_angles(positions, asc, mc):
    """Return aspects between planets and chart angles."""
    data = positions.copy()
    data['Ascendant'] = asc
    data['Midheaven'] = mc
    all_aspects = compute_aspects(data)
    return [
        a
        for a in all_aspects
        if 'Ascendant' in (a['planet1'], a['planet2'])
        or 'Midheaven' in (a['planet1'], a['planet2'])
    ]


def compute_synastry_aspects(chart1_positions, chart2_positions):
    """Return cross-aspects and midpoint charts for two sets of positions."""

    def midpoint_angle(lon1, lon2):
        diff = abs(lon1 - lon2)
        if diff <= 180:
            return ((lon1 + lon2) / 2) % 360
        return ((lon1 + lon2 + 360) / 2) % 360

    pref1 = {f"1_{k}": v for k, v in chart1_positions.items()}
    pref2 = {f"2_{k}": v for k, v in chart2_positions.items()}
    combined = pref1 | pref2

    aspects = compute_aspects(combined)
    cross = [
        {
            **a,
            'planet1': a['planet1'][2:],
            'planet2': a['planet2'][2:],
        }
        for a in aspects
        if (a['planet1'].startswith('1_') and a['planet2'].startswith('2_'))
        or (a['planet1'].startswith('2_') and a['planet2'].startswith('1_'))
    ]

    bodies = chart1_positions.keys() & chart2_positions.keys()
    composite = {
        b: midpoint_angle(chart1_positions[b], chart2_positions[b]) for b in bodies
    }
    davison = composite.copy()

    return {
        'cross_aspects': cross,
        'composite_positions': composite,
        'composite_aspects': compute_aspects(composite) if len(composite) > 1 else [],
        'davison_positions': davison,
        'davison_aspects': compute_aspects(davison) if len(davison) > 1 else [],
    }


def detect_chart_patterns(aspects, positions=None):
    """Identify common aspect patterns including stelliums and kites."""
    trines = {}
    oppositions = []
    squares = []
    sextiles = set()
    quincunx = {}
    bodies = set()
    for asp in aspects:
        p1 = asp['planet1']
        p2 = asp['planet2']
        bodies.update([p1, p2])
        if asp['aspect'] == 'Trine':
            trines.setdefault(p1, set()).add(p2)
            trines.setdefault(p2, set()).add(p1)
        elif asp['aspect'] == 'Opposition':
            oppositions.append((p1, p2))
        elif asp['aspect'] == 'Square':
            squares.append((p1, p2))
        elif asp['aspect'] == 'Sextile':
            sextiles.add(frozenset([p1, p2]))
        elif asp['aspect'] == 'Quincunx':
            quincunx.setdefault(p1, set()).add(p2)
            quincunx.setdefault(p2, set()).add(p1)

    from itertools import combinations

    grand_trines = set()
    triad_bodies = set(trines.keys())
    for a, b, c in combinations(sorted(triad_bodies), 3):
        if (
            b in trines.get(a, set())
            and c in trines.get(a, set())
            and c in trines.get(b, set())
        ):
            grand_trines.add(tuple(sorted([a, b, c])))

    square_map = {}
    for x, y in squares:
        square_map.setdefault(x, set()).add(y)
        square_map.setdefault(y, set()).add(x)

    t_squares = set()
    for x, y in oppositions:
        for z in square_map.get(x, set()) & square_map.get(y, set()):
            t_squares.add(tuple(sorted([x, y, z])))

    # classify t-squares by modality if positions supplied
    t_square_info = {}
    if positions:
        for ts in t_squares:
            modes = []
            for body in ts:
                sign = ZODIAC_SIGNS[int(positions[body] // 30) % 12]
                mode = next(
                    (m for m, signs in MODALITY_SIGNS.items() if sign in signs),
                    None,
                )
                modes.append(mode)
            emphasis = modes[0] if modes.count(modes[0]) == 3 else None
            t_square_info[ts] = emphasis

    # detect kites based on grand trines
    opposition_set = {frozenset(o) for o in oppositions}
    kites = set()
    for tri in grand_trines:
        others = bodies - set(tri)
        for d in others:
            for opp_point in tri:
                if frozenset([d, opp_point]) not in opposition_set:
                    continue
                rem = [p for p in tri if p != opp_point]
                if (
                    frozenset([d, rem[0]]) in sextiles
                    and frozenset([d, rem[1]]) in sextiles
                ):
                    kite = tuple(sorted([d] + list(tri)))
                    kites.add(kite)
                    break

    # detect yods
    yods = set()
    for pair in sextiles:
        a, b = list(pair)
        for c in quincunx.get(a, set()) & quincunx.get(b, set()):
            yods.add(tuple(sorted([a, b, c])))

    # detect stelliums within signs (3+ planets in 8 degrees)
    stelliums = []
    if positions:
        sign_groups = {i: [] for i in range(12)}
        for body, lon in positions.items():
            sign_idx = int(lon // 30) % 12
            deg_in_sign = lon % 30
            sign_groups[sign_idx].append((body, deg_in_sign))
        for idx, items in sign_groups.items():
            if len(items) < 3:
                continue
            items.sort(key=lambda t: t[1])
            for i in range(len(items)):
                j = i
                while j < len(items) and items[j][1] - items[i][1] <= 8:
                    j += 1
                if j - i >= 3:
                    planets = tuple(sorted(p for p, _ in items[i:j]))
                    record = {'sign': ZODIAC_SIGNS[idx], 'planets': planets}
                    if record not in stelliums:
                        stelliums.append(record)

    return {
        'grand_trines': sorted(grand_trines),
        't_squares': [
            {'planets': ts, 'type': t_square_info.get(ts)} for ts in sorted(t_squares)
        ],
        'kites': sorted(kites),
        'yods': sorted(yods),
        'stelliums': stelliums,
    }


def filter_aspects_for_wheel(aspects, max_minor=2):
    """Return aspects to draw on the chart wheel.

    All major aspects are included. Minor aspects are sorted by strength and the
    strongest few are kept to reduce clutter on the wheel."""

    major = [a for a in aspects if a.get('type') == 'major']
    minor = [a for a in aspects if a.get('type') != 'major']
    minor.sort(key=lambda a: a['strength'], reverse=True)
    return major + minor[:max_minor]


def secondary_progressions(natal_jd, target_jd, node_type: str = 'mean'):
    """Return progressed positions using the day-for-a-year method."""
    progressed_jd = natal_jd + (target_jd - natal_jd) / 365.25
    return compute_positions(progressed_jd, node_type)


def solar_arc_progressions(natal_jd, target_jd, node_type: str = 'mean'):
    """Return solar arc progressed positions."""
    natal = compute_positions(natal_jd, node_type)
    target = compute_positions(target_jd, node_type)
    arc = (target['Sun'] - natal['Sun']) % 360
    return {name: (lon + arc) % 360 for name, lon in natal.items()}


def solar_return_jd(natal_jd, year, tol=1e-5, node_type: str = 'mean'):
    """Return Julian day of the solar return for the given year."""
    natal_sun = compute_positions(natal_jd, node_type)['Sun']
    approx = natal_jd + 365.25 * year
    low = approx - 5
    high = approx + 5

    def diff(jd):
        sun = compute_positions(jd, node_type)['Sun']
        return ((sun - natal_sun + 180) % 360) - 180

    for _ in range(20):
        mid = (low + high) / 2
        d = diff(mid)
        if abs(d) < tol:
            return mid
        if d > 0:
            high = mid
        else:
            low = mid
    return mid


def lunar_return_jd(natal_jd, month, tol=1e-5, node_type: str = 'mean'):
    """Return Julian day of the lunar return for the given month."""
    natal_moon = compute_positions(natal_jd, node_type)['Moon']
    approx = natal_jd + 27.321582 * month
    low = approx - 2
    high = approx + 2

    def diff(jd):
        moon = compute_positions(jd, node_type)['Moon']
        return ((moon - natal_moon + 180) % 360) - 180

    for _ in range(20):
        mid = (low + high) / 2
        d = diff(mid)
        if abs(d) < tol:
            return mid
        if d > 0:
            high = mid
        else:
            low = mid
    return mid


def transits(natal_positions, target_jd, node_type: str = 'mean'):
    """Return current positions and aspects to natal chart."""
    current = compute_positions(target_jd, node_type)
    pref_n = {f"n_{k}": v for k, v in natal_positions.items()}
    pref_c = {f"t_{k}": v for k, v in current.items()}
    combined = pref_n | pref_c
    asps = compute_aspects(combined)
    cross = [
        {**a, 'planet1': a['planet1'][2:], 'planet2': a['planet2'][2:]}
        for a in asps
        if (a['planet1'].startswith('n_') and a['planet2'].startswith('t_'))
        or (a['planet1'].startswith('t_') and a['planet2'].startswith('n_'))
    ]
    return {'positions': current, 'aspects': cross}


def electional_days(natal_positions, start_jd, end_jd, step=0.25, orb=1.0):
    """Return days when the transiting Moon trines the natal Sun."""
    sun = natal_positions['Sun']
    days = []
    jd = start_jd
    while jd <= end_jd:
        moon = compute_positions(jd)['Moon']
        diff = abs(((moon - sun + 180) % 360) - 180)
        if abs(diff - 120) <= orb:
            days.append(jd)
        jd += step
    return days


def draw_chart_wheel(positions, cusps, aspects=None, retrogrades=None, asc=None,
                     mc=None, interactive=False):
    """Return a chart wheel as base64 PNG or interactive HTML.

    The ascendant and midheaven can be highlighted if provided."""
    if aspects is None:
        aspects = []
    if retrogrades is None:
        retrogrades = {}

    fig = None
    try:
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE, facecolor=THEME['bg'])
        ax.set_aspect('equal')
        ax.axis('off')

        # outer circle for zodiac
        outer = plt.Circle((0, 0), 1, fill=False, lw=1, color=THEME['fg'])
        ax.add_artist(outer)

        # zodiac glyphs
        for i, glyph in enumerate(ZODIAC_GLYPHS):
            deg = i * 30 + 15
            theta = math.radians(90 - deg)
            x = 1.08 * math.cos(theta)
            y = 1.08 * math.sin(theta)
            ax.text(x, y, glyph, ha='center', va='center', fontsize=12,
                    color=THEME['fg'])

        # draw house cusps and numbers
        for i, cusp in enumerate(cusps):
            theta = math.radians(90 - cusp)
            x = math.cos(theta)
            y = math.sin(theta)
            width = 1.0 if i in (0, 3, 6, 9) else 0.5
            ax.plot([0, x], [0, y], color=THEME['fg'], linewidth=width)

            next_cusp = cusps[(i + 1) % 12]
            diff = (next_cusp - cusp) % 360
            mid_deg = (cusp + diff / 2) % 360
            mtheta = math.radians(90 - mid_deg)
            mx = 0.5 * math.cos(mtheta)
            my = 0.5 * math.sin(mtheta)
            ax.text(mx, my, str(i + 1), ha='center', va='center', fontsize=8,
                    color=THEME['fg'])

        # highlight ascendant and midheaven if supplied
        if asc is not None:
            theta = math.radians(90 - asc)
            x = math.cos(theta)
            y = math.sin(theta)
            ax.plot([0, x], [0, y], color='red', linewidth=1.5)
            ax.text(1.15 * math.cos(theta), 1.15 * math.sin(theta), 'ASC',
                    ha='center', va='center', fontsize=8, color='red')
        if mc is not None:
            theta = math.radians(90 - mc)
            x = math.cos(theta)
            y = math.sin(theta)
            ax.plot([0, x], [0, y], color='blue', linewidth=1.5)
            ax.text(1.15 * math.cos(theta), 1.15 * math.sin(theta), 'MC',
                    ha='center', va='center', fontsize=8, color='blue')

        # track overlapping planets for spacing. group planets by degree and
        # distribute them along a small arc so glyphs do not overlap.
        # cluster planets that are very close in longitude
        items = sorted(positions.items(), key=lambda t: t[1])
        groups = []
        group = [items[0]] if items else []
        for name, lon in items[1:]:
            if lon - group[-1][1] <= 1.0:
                group.append((name, lon))
            else:
                groups.append(group)
                group = [(name, lon)]
        if group:
            groups.append(group)
        if len(groups) > 1 and (groups[0][0][1] + 360 - groups[-1][-1][1]) <= 1.0:
            groups[0] = groups[-1] + groups[0]
            groups.pop()

        planet_points = {}
        scatter_x = []
        scatter_y = []
        labels = []
        for g in groups:
            count = len(g)
            g.sort(key=lambda t: t[1])
            for i, (name, lon) in enumerate(g):
                angle_offset = (i - (count - 1) / 2) * 0.5
                theta = math.radians(90 - (lon + angle_offset))
                r = 0.8 - 0.05 * i
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                ax.plot(x, y, 'o', color=THEME['fg'], markersize=5)
                glyph = PLANET_GLYPHS.get(name, name[0])
                ax.text(x, y + 0.05, glyph, ha='center', va='center',
                        fontsize=10, color=THEME['fg'])
                if retrogrades.get(name):
                    ax.text(x, y - 0.05, '℞', ha='center', va='center',
                            fontsize=6, color=THEME['fg'])
                planet_points[name] = (x, y)
                scatter_x.append(x)
                scatter_y.append(y)
                labels.append(f"{name} {format_longitude(positions[name])}")

        # draw aspect lines
        aspect_colors = THEME['aspect_colors']
        for asp in aspects:
            p1 = asp['planet1']
            p2 = asp['planet2']
            if p1 not in planet_points or p2 not in planet_points:
                continue
            x1, y1 = planet_points[p1]
            x2, y2 = planet_points[p2]
            color = aspect_colors.get(asp['aspect'], 'gray')
            max_orb = ASPECTS_INFO.get(asp['aspect'], {}).get('orb', 5)
            width = 0.5 + max(0, (max_orb - asp['orb']) / max_orb) * 1.5
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=width)

        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)

        if interactive:
            scatter = ax.scatter(scatter_x, scatter_y, s=20, alpha=0)
            tooltip = mpld3.plugins.PointLabelTooltip(scatter, labels)
            mpld3.plugins.connect(fig, tooltip, mpld3.plugins.Zoom())
            return mpld3.fig_to_html(fig)

        buf = io.BytesIO()
        fig.tight_layout()
        plt.savefig(buf, format='png')
        encoded = base64.b64encode(buf.getvalue()).decode()
        return encoded
    except Exception as exc:
        raise RuntimeError('Error generating chart wheel') from exc
    finally:
        if fig:
            plt.close(fig)


def chart_ruler(asc_longitude):
    """Return the planetary ruler of the ascendant sign."""
    sign = ZODIAC_SIGNS[int(asc_longitude // 30) % 12]
    return SIGN_RULERS.get(sign)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "development-secret-key")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            date_str = request.form['date']
            time_str = request.form['time']
            tz_offset_str = request.form.get('tz_offset', '').strip()
            city = request.form.get('city', '').strip()
            lat_str = request.form.get('latitude', '').strip()
            lon_str = request.form.get('longitude', '').strip()
            hsys = request.form.get('house_system', 'P').encode()
            node_type = request.form.get('node_type', 'mean')

            dt_local = datetime.datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
            )
            if dt_local.year < 1800 or dt_local.year > 2100:
                raise ValueError('Date must be between 1800 and 2100')

            # Resolve coordinates from city name if provided
            if city and (not lat_str or not lon_str):
                try:
                    resp = requests.get(
                        'https://nominatim.openstreetmap.org/search',
                        params={'q': city, 'format': 'json', 'limit': 1},
                        headers={'User-Agent': 'moonandsun'},
                        timeout=20
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if not data:
                        raise ValueError('City not found')
                    lat_str = data[0]['lat']
                    lon_str = data[0]['lon']
                except requests.RequestException:
                    raise ValueError('City lookup failed')

            lat = float(lat_str)
            lon = float(lon_str)
            if not (-90 <= lat <= 90):
                raise ValueError('Latitude must be between -90 and 90')
            if not (-180 <= lon <= 180):
                raise ValueError('Longitude must be between -180 and 180')

            if tz_offset_str:
                tz_offset = float(tz_offset_str)
                dt = dt_local
                dt_utc = dt - datetime.timedelta(hours=tz_offset)
            else:
                tf = TimezoneFinder()
                tzname = tf.timezone_at(lat=lat, lng=lon)
                if not tzname:
                    raise ValueError('Could not determine timezone')
                tzinfo = ZoneInfo(tzname)
                dt = dt_local.replace(tzinfo=tzinfo)
                dt_utc = dt.astimezone(datetime.timezone.utc)

            jd = swe.julday(
                dt_utc.year,
                dt_utc.month,
                dt_utc.day,
                dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
            )

            positions = compute_positions(jd, node_type)
            retrogrades = compute_retrogrades(jd, node_type)
            chart_points = compute_chart_points(jd, lat, lon, hsys)
            houses = compute_house_positions(positions, chart_points['cusps'])
            aspects = compute_aspects(positions)
            angle_aspects = compute_aspects_to_angles(
                positions,
                chart_points['asc'],
                chart_points['mc'],
            )
            major_aspects = [a for a in aspects if a['type'] == 'major']
            minor_aspects = [a for a in aspects if a['type'] == 'minor']
            ruler = chart_ruler(chart_points['asc'])
            dignities = compute_dignities(positions)
            patterns = detect_chart_patterns(aspects, positions)
            wheel_aspects = filter_aspects_for_wheel(aspects)
            chart_img = draw_chart_wheel(
                positions,
                chart_points['cusps'],
                wheel_aspects,
                retrogrades,
                asc=chart_points['asc'],
                mc=chart_points['mc'],
            )
            chart_html = None
            if CHART_INTERACTIVE:
                chart_html = draw_chart_wheel(
                    positions,
                    chart_points['cusps'],
                    wheel_aspects,
                    retrogrades,
                    asc=chart_points['asc'],
                    mc=chart_points['mc'],
                    interactive=True,
                )
            formatted_positions = {n: format_longitude(p) for n, p in positions.items()}
            formatted_asc = format_longitude(chart_points['asc'])
            formatted_mc = format_longitude(chart_points['mc'])
            formatted_vertex = format_longitude(chart_points['vertex'])
            formatted_pof = format_longitude(chart_points['part_of_fortune'])
            formatted_cusps = [format_longitude(c) for c in chart_points['cusps']]
            return render_template(
                'chart.html',
                positions=formatted_positions,
                retrogrades=retrogrades,
                houses=houses,
                dignities=dignities,
                major_aspects=major_aspects,
                minor_aspects=minor_aspects,
                angle_aspects=angle_aspects,
                aspects=aspects,
                chart_ruler=ruler,
                patterns=patterns,
                chart_img=chart_img,
                chart_html=chart_html,
                interactive=CHART_INTERACTIVE,
                lat=lat,
                lon=lon,
                dt=dt,
                dt_utc=dt_utc,
                asc=formatted_asc,
                mc=formatted_mc,
                vertex=formatted_vertex,
                part_of_fortune=formatted_pof,
                cusps=formatted_cusps,
                house_system=hsys.decode(),
                node_type=node_type,
                house_systems=HOUSE_SYSTEMS,
            )
        except Exception as exc:
            flash(str(exc))
            return render_template(
                'index.html',
                date_value=request.form.get('date', ''),
                time_value=request.form.get('time', ''),
                tz_offset_value=request.form.get('tz_offset', ''),
                city_value=request.form.get('city', ''),
                lat_value=request.form.get('latitude', ''),
                lon_value=request.form.get('longitude', ''),
                house_system_value=request.form.get('house_system', 'P'),
                node_type=request.form.get('node_type', 'mean'),
                house_systems=HOUSE_SYSTEMS,
            )
    return render_template(
        'index.html',
        date_value='',
        time_value='',
        tz_offset_value='',
        city_value='',
        lat_value='',
        lon_value='',
        house_system_value='P',
        node_type='mean',
        house_systems=HOUSE_SYSTEMS,
    )


@app.route('/save_chart', methods=['POST'])
def save_chart():
    name = request.form.get('chart_name', '').strip()
    img_data = request.form.get('chart_img', '')
    if not name or not img_data:
        flash('Chart name and image required')
        return redirect(url_for('index'))

    birth_dt = request.form.get('birth_dt')
    house_system = request.form.get('house_system')
    node_type = request.form.get('node_type', 'mean')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')

    data = img_data.split(',', 1)[-1]
    img_bytes = base64.b64decode(data)

    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    dt_str = None
    if birth_dt:
        try:
            dt_obj = datetime.datetime.fromisoformat(birth_dt)
            dt_str = dt_obj.strftime('%Y%m%d_%H%M')
        except ValueError:
            dt_str = None
    if not dt_str:
        dt_str = str(int(time.time()))
    fname = f"{slug}_{dt_str}.png"
    (CHARTS_DIR / fname).write_bytes(img_bytes)

    metadata = {
        'birth_dt': birth_dt,
        'house_system': house_system,
        'node_type': node_type,
        'latitude': lat,
        'longitude': lon,
    }

    charts = load_charts()
    charts.append({'name': name, 'file': fname, 'metadata': metadata})
    save_charts(charts)
    flash('Chart saved')
    return redirect(url_for('list_charts'))


@app.route('/charts')
def list_charts():
    charts = load_charts()
    return render_template('charts.html', charts=charts)


@app.route('/download/<path:filename>')
def download_chart(filename):
    path = CHARTS_DIR / filename
    if not path.exists():
        flash('File not found')
        return redirect(url_for('index'))
    return send_file(path, as_attachment=True, download_name=filename)


@app.route('/delete/<path:filename>', methods=['POST'])
def delete_chart(filename):
    charts = load_charts()
    chart = next((c for c in charts if c.get('file') == filename), None)
    if not chart:
        flash('Chart not found')
        return redirect(url_for('list_charts'))
    path = CHARTS_DIR / filename
    if path.exists():
        path.unlink()
    charts = [c for c in charts if c.get('file') != filename]
    save_charts(charts)
    flash('Chart deleted')
    return redirect(url_for('list_charts'))


@app.route('/edit/<path:filename>')
def edit_chart(filename):
    charts = load_charts()
    chart = next((c for c in charts if c.get('file') == filename), None)
    if not chart:
        flash('Chart not found')
        return redirect(url_for('list_charts'))
    md = chart.get('metadata', {})
    date_val = ''
    time_val = ''
    dt_iso = md.get('birth_dt')
    if dt_iso:
        try:
            dt_obj = datetime.datetime.fromisoformat(dt_iso)
            date_val = dt_obj.strftime('%Y-%m-%d')
            time_val = dt_obj.strftime('%H:%M')
        except ValueError:
            pass
    return render_template(
        'index.html',
        date_value=date_val,
        time_value=time_val,
        tz_offset_value='',
        city_value='',
        lat_value=md.get('latitude', ''),
        lon_value=md.get('longitude', ''),
        house_system_value=md.get('house_system', 'P'),
        node_type=md.get('node_type', 'mean'),
        house_systems=HOUSE_SYSTEMS,
    )

if __name__ == '__main__':
    app.run(debug=True)
