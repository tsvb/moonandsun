from flask import Flask, render_template, request, flash, send_file, redirect, url_for
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
import json
import re
import time
from pathlib import Path

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


def filter_aspects_for_wheel(aspects, max_minor=2):
    """Return aspects to draw on the chart wheel.

    All major aspects are included. Minor aspects are sorted by strength and the
    strongest few are kept to reduce clutter on the wheel."""

    major = [a for a in aspects if a.get('type') == 'major']
    minor = [a for a in aspects if a.get('type') != 'major']
    minor.sort(key=lambda a: a['strength'], reverse=True)
    return major + minor[:max_minor]


def draw_chart_wheel(positions, cusps, aspects=None, retrogrades=None, asc=None, mc=None):
    """Return base64-encoded PNG of an improved chart wheel.

    The ascendant and midheaven can be highlighted if provided."""
    if aspects is None:
        aspects = []
    if retrogrades is None:
        retrogrades = {}

    fig = None
    try:
        fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
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
        buckets = {}
        for name, lon in positions.items():
            key = round(lon)  # bucket planets within 1 degree
            buckets.setdefault(key, []).append((name, lon))

        planet_points = {}
        for items in buckets.values():
            count = len(items)
            items.sort(key=lambda t: t[1])
            for i, (name, lon) in enumerate(items):
                angle_offset = (i - (count - 1) / 2) * 0.5  # degrees
                theta = math.radians(90 - (lon + angle_offset))
                r = 0.8 - 0.05 * i
                x = r * math.cos(theta)
                y = r * math.sin(theta)
                ax.plot(x, y, 'o', color='black', markersize=5)
                glyph = PLANET_GLYPHS.get(name, name[0])
                ax.text(x, y + 0.05, glyph, ha='center', va='center', fontsize=10)
                if retrogrades.get(name):
                    ax.text(x, y - 0.05, '℞', ha='center', va='center', fontsize=6)
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

            positions = compute_positions(jd)
            retrogrades = compute_retrogrades(jd)
            chart_points = compute_chart_points(jd, lat, lon, hsys)
            houses = compute_house_positions(positions, chart_points['cusps'])
            aspects = compute_aspects(positions)
            major_aspects = [a for a in aspects if a['type'] == 'major']
            minor_aspects = [a for a in aspects if a['type'] == 'minor']
            ruler = chart_ruler(chart_points['asc'])
            wheel_aspects = filter_aspects_for_wheel(aspects)
            chart_img = draw_chart_wheel(
                positions,
                chart_points['cusps'],
                wheel_aspects,
                retrogrades,
                asc=chart_points['asc'],
                mc=chart_points['mc'],
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
                major_aspects=major_aspects,
                minor_aspects=minor_aspects,
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
            return render_template(
                'index.html',
                date_value=request.form.get('date', ''),
                time_value=request.form.get('time', ''),
                tz_offset_value=request.form.get('tz_offset', ''),
                city_value=request.form.get('city', ''),
                lat_value=request.form.get('latitude', ''),
                lon_value=request.form.get('longitude', ''),
                house_system_value=request.form.get('house_system', 'P'),
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
    )

if __name__ == '__main__':
    app.run(debug=True)
