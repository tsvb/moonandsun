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
    return {
        'asc': ascmc[0],
        'mc': ascmc[1],
        'cusps': list(cusps),
    }

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
    }
    info = {}
    for name, body in planets.items():
        vals = swe.calc_ut(jd, body)[0]
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


def draw_chart_wheel(positions, cusps):
    """Return base64-encoded PNG of a simple chart wheel."""
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={'projection': 'polar'})
    ax.set_theta_direction(-1)
    ax.set_theta_offset(math.radians(90))
    ax.set_yticklabels([])
    ax.set_xticklabels([])

    # draw house cusps
    for cusp in cusps:
        theta = math.radians(90 - cusp)
        ax.plot([theta, theta], [0, 1], color='black', linewidth=0.5)

    # plot planet positions
    for name, lon in positions.items():
        theta = math.radians(90 - lon)
        ax.plot(theta, 0.8, 'o')
        ax.text(theta, 0.85, name[0], ha='center', va='center', fontsize=8)

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
                        headers={'User-Agent': 'moonandsun'}
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
            chart_img = draw_chart_wheel(positions, chart_points['cusps'])
            formatted_positions = {n: format_longitude(p) for n, p in positions.items()}
            formatted_asc = format_longitude(chart_points['asc'])
            formatted_mc = format_longitude(chart_points['mc'])
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
                cusps=formatted_cusps,
                house_system=hsys.decode(),
            )
        except Exception as exc:
            flash(str(exc))
            return render_template('index.html')
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
