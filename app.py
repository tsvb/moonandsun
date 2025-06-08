from flask import Flask, render_template, request, flash
import swisseph as swe
import datetime
import requests
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo
import io
import base64
import math
import matplotlib.pyplot as plt
import os

ZODIAC_SIGNS = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
]

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

# Aspect configuration: aspect angle and maximum orb
ASPECTS_INFO = {
    'Conjunction': {'angle': 0, 'orb': 8},
    'Opposition': {'angle': 180, 'orb': 8},
    'Square': {'angle': 90, 'orb': 6},
    'Trine': {'angle': 120, 'orb': 6},
    'Sextile': {'angle': 60, 'orb': 4},
    # Extended aspects
    'Quincunx': {'angle': 150, 'orb': 3},
    'Semi-sextile': {'angle': 30, 'orb': 2},
    'Semi-square': {'angle': 45, 'orb': 2},
    'Sesquiquadrate': {'angle': 135, 'orb': 2},
}


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
    """Return Ascendant, Midheaven and house cusps."""
    cusps, ascmc = swe.houses(jd, lat, lon, hsys)
    asc = ascmc[0]
    mc = ascmc[1]
    vertex = ascmc[3]

    sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
    moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
    sun_house = house_for(sun_lon, list(cusps))
    if sun_house >= 7:
        pof = (asc + moon_lon - sun_lon) % 360
    else:
        pof = (asc + sun_lon - moon_lon) % 360

    return {
        'asc': asc,
        'mc': mc,
        'vertex': vertex,
        'part_of_fortune': pof,
        'cusps': list(cusps),
    }


def fetch_chiron_info(jd):
    """Return (lon, speed) for Chiron using JPL Horizons if SwissEph data missing."""
    url = "https://ssd.jpl.nasa.gov/api/horizons.api"
    params = {
        "format": "text",
        "COMMAND": "2060",
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
    raise RuntimeError("Could not parse Horizons response for Chiron")

def compute_body_info(jd):
    """Return longitude and speed for each major body for the given Julian day."""
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
        'Mean Node': swe.MEAN_NODE,
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
            else:
                raise
        info[name] = (vals[0], vals[3])
    return info

def compute_positions(jd):
    """Return ecliptic longitudes of major bodies for given Julian day."""
    info = compute_body_info(jd)
    return {name: vals[0] for name, vals in info.items()}

def compute_retrogrades(jd):
    """Return True for bodies that are retrograde on the given day."""
    info = compute_body_info(jd)
    return {name: vals[1] < 0 for name, vals in info.items()}


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
                    aspects.append({
                        'planet1': p1,
                        'planet2': p2,
                        'aspect': aspect,
                        'orb': orb,
                        'strength': strength,
                    })
    return aspects


def draw_chart_wheel(positions, cusps, aspects=None):
    """Return base64-encoded PNG of an improved chart wheel."""
    if aspects is None:
        aspects = []

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect('equal')
    ax.axis('off')

    # outer circle for zodiac
    outer = plt.Circle((0, 0), 1, fill=False, lw=1, color='black')
    ax.add_artist(outer)

    # zodiac glyphs
    for i, glyph in enumerate(ZODIAC_GLYPHS):
        deg = i * 30 + 15
        theta = math.radians(90 - deg)
        x = 1.08 * math.cos(theta)
        y = 1.08 * math.sin(theta)
        ax.text(x, y, glyph, ha='center', va='center', fontsize=12)

    # draw house cusps and numbers
    for i, cusp in enumerate(cusps):
        theta = math.radians(90 - cusp)
        x = math.cos(theta)
        y = math.sin(theta)
        ax.plot([0, x], [0, y], color='black', linewidth=0.5)

        next_cusp = cusps[(i + 1) % 12]
        diff = (next_cusp - cusp) % 360
        mid_deg = (cusp + diff / 2) % 360
        mtheta = math.radians(90 - mid_deg)
        mx = 0.5 * math.cos(mtheta)
        my = 0.5 * math.sin(mtheta)
        ax.text(mx, my, str(i + 1), ha='center', va='center', fontsize=8)

    # track overlapping planets for spacing
    buckets = {}
    planet_points = {}
    for name, lon in positions.items():
        key = round(lon, 1)
        offset = buckets.get(key, 0)
        buckets[key] = offset + 1
        theta = math.radians(90 - lon)
        r = 0.8 - 0.05 * offset
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        ax.plot(x, y, 'o', color='black', markersize=5)
        glyph = PLANET_GLYPHS.get(name, name[0])
        ax.text(x, y + 0.05, glyph, ha='center', va='center', fontsize=10)
        planet_points[name] = (x, y)

    # draw aspect lines
    aspect_colors = {
        'Conjunction': 'green',
        'Opposition': 'red',
        'Square': 'red',
        'Trine': 'green',
        'Sextile': 'blue',
    }
    for asp in aspects:
        p1 = asp['planet1']
        p2 = asp['planet2']
        if p1 not in planet_points or p2 not in planet_points:
            continue
        x1, y1 = planet_points[p1]
        x2, y2 = planet_points[p2]
        color = aspect_colors.get(asp['aspect'], 'gray')
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=0.7)

    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)

    buf = io.BytesIO()
    fig.tight_layout()
    plt.savefig(buf, format='png')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


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

            # Resolve coordinates from city name if provided
            if city and (not lat_str or not lon_str):
                try:
                    resp = requests.get(
                        'https://nominatim.openstreetmap.org/search',
                        params={'q': city, 'format': 'json', 'limit': 1},
                        headers={'User-Agent': 'moonandsun'},
                        timeout=10
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
                dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                dt_utc = dt - datetime.timedelta(hours=tz_offset)
            else:
                tf = TimezoneFinder()
                tzname = tf.timezone_at(lat=lat, lng=lon)
                if not tzname:
                    raise ValueError('Could not determine timezone')
                tzinfo = ZoneInfo(tzname)
                dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
                dt_utc = dt.astimezone(datetime.timezone.utc)

            jd = swe.julday(
                dt_utc.year,
                dt_utc.month,
                dt_utc.day,
                dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
            )

            positions = compute_positions(jd)
            chart_points = compute_chart_points(jd, lat, lon, hsys)
            houses = compute_house_positions(positions, chart_points['cusps'])
            aspects = compute_aspects(positions)
            ruler = chart_ruler(chart_points['asc'])
            chart_img = draw_chart_wheel(positions, chart_points['cusps'], aspects)
            formatted_positions = {n: format_longitude(p) for n, p in positions.items()}
            formatted_asc = format_longitude(chart_points['asc'])
            formatted_mc = format_longitude(chart_points['mc'])
            formatted_vertex = format_longitude(chart_points['vertex'])
            formatted_pof = format_longitude(chart_points['part_of_fortune'])
            formatted_cusps = [format_longitude(c) for c in chart_points['cusps']]
            return render_template(
                'chart.html',
                positions=formatted_positions,
                houses=houses,
                aspects=aspects,
                chart_ruler=ruler,
                chart_img=chart_img,
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
            )
        except Exception as exc:
            flash(str(exc))
            return render_template('index.html')
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
