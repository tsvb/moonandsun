from flask import Flask, render_template, request
import swisseph as swe
import datetime

ZODIAC_SIGNS = [
    'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
]


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

def compute_positions(jd):
    """Return ecliptic longitudes of major bodies for given Julian day."""
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
    positions = {}
    for name, body in planets.items():
        lon_lat_dist = swe.calc_ut(jd, body)[0]
        positions[name] = lon_lat_dist[0]
    return positions

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date_str = request.form['date']
        time_str = request.form['time']
        tz_offset = float(request.form['tz_offset'])
        lat = float(request.form['latitude'])
        lon = float(request.form['longitude'])
        hsys = request.form.get('house_system', 'P').encode()

        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        dt_utc = dt - datetime.timedelta(hours=tz_offset)
        jd = swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
        )

        positions = compute_positions(jd)
        chart_points = compute_chart_points(jd, lat, lon, hsys)
        houses = compute_house_positions(positions, chart_points['cusps'])
        formatted_positions = {n: format_longitude(p) for n, p in positions.items()}
        formatted_asc = format_longitude(chart_points['asc'])
        formatted_mc = format_longitude(chart_points['mc'])
        formatted_cusps = [format_longitude(c) for c in chart_points['cusps']]
        return render_template('chart.html', positions=formatted_positions,
                               houses=houses,
                               lat=lat, lon=lon, dt=dt, dt_utc=dt_utc,
                               asc=formatted_asc,
                               mc=formatted_mc,
                               cusps=formatted_cusps,
                               house_system=hsys.decode())
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
