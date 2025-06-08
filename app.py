from flask import Flask, render_template, request
import swisseph as swe
import datetime


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
        return render_template('chart.html', positions=positions,
                               lat=lat, lon=lon, dt=dt, dt_utc=dt_utc,
                               asc=chart_points['asc'],
                               mc=chart_points['mc'],
                               cusps=chart_points['cusps'],
                               house_system=hsys.decode())
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
