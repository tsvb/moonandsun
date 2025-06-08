# Moon and Sun Natal Chart

This project is a simple Flask web application that generates planetary positions for a natal chart using the [Swiss Ephemeris](https://www.astro.com/swisseph/).
The application now also calculates major aspects between planets with their orb strength, identifies the chart ruler based on the ascendant sign and draws a chart wheel illustrating the houses and planetary locations. Retrograde markers are displayed for relevant bodies in both the results table and the chart wheel, and Unicode glyphs are used for planets and zodiac signs, house numbers and aspect lines to produce a clear presentation. Essential dignities are listed for each planet, aspects to the ascendant and midheaven are shown, and the app recognises simple chart patterns like grand trines and t-squares.

## Setup

1. Install Python 3.12 or later.
2. Create a virtual environment (recommended) and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for running tests
```
The `requirements.txt` file now includes `matplotlib` which is used to draw the chart wheel. The Swiss Ephemeris Python bindings (`pyswisseph`) are an absolute requirement for running the application and executing the automated tests.

The application uses Flask sessions and expects a secret key. Set the
`SECRET_KEY` environment variable to override the default development key.
Chart wheel size can be customised by setting `CHART_FIGSIZE` to a comma
separated width and height (e.g. `7,7`).
The `CHART_THEME` variable toggles between light and dark colors. Setting
`CHART_INTERACTIVE=1` enables a D3-powered interactive wheel with tooltips.
Setting `WEBGL_WHEEL=1` uses a WebGL renderer for the wheel. If `REDIS_URL` is
set computed charts are cached in Redis and providing `DATABASE_URL` stores
chart metadata in PostgreSQL.

The web UI supports a dark/light toggle and basic PWA features. A
service worker caches pages for offline use and a `manifest.json`
enables installation on mobile devices.

## Running

Run the Flask app with:

```bash
python app.py
```

Visit `http://localhost:5000` in your browser and enter your birth details to generate the planetary positions. The form accepts either a city name or latitude/longitude coordinates. If you leave the timezone offset blank it will be detected automatically from the coordinates.

## Testing

Run the automated tests with:

```bash
pytest
```

## Chart Management

After generating a chart you can save it from the results page. Saved charts are
listed on a dedicated page where each entry shows the chart name and birth date.
You can download or delete individual charts. The stored metadata includes the
birth details, coordinates and chosen house system so charts remain identifiable.
Saved image filenames incorporate the chart name and birth timestamp instead of
generic numbers.

Old chart images older than 30 days or removed from the index are cleaned up
automatically when the application starts.

## Packaging

You can create standalone executables for Windows, macOS and Linux using [PyInstaller](https://www.pyinstaller.org/). The `natal_chart.spec` file now collects templates, static assets and the Swiss Ephemeris star data when available. It also specifies the matplotlib backend and creates a macOS bundle automatically.
Binary icon assets are not included in the repository (some tools cannot display them in diffs). Provide your own icon files inside the `icons/` directory (e.g. `icon.ico` for Windows and `icon.icns` for macOS) if you want a custom installer graphic.

Install PyInstaller and run it with the spec file:

```bash
pip install pyinstaller
pyinstaller natal_chart.spec
```

The resulting executable will be placed in the `dist/` directory. If you added `icons/icon.ico` before building on Windows (or `icon.icns` on macOS) the installer will include it automatically.

### Windows installer

To build a traditional Windows installer install [NSIS](https://nsis.sourceforge.io/)
and run:

```bash
makensis installer.nsi
```

This produces `moonandsun_setup.exe` that installs the packaged application to
`Program Files/MoonAndSun` with desktop and Start Menu shortcuts.

## Time-Based Features

Additional helpers calculate progressed and return charts:

- **Secondary progressions** using the day-for-a-year method.
- **Solar arc progressions** adding the Sun's arc to all bodies.
- **Transits** comparing current positions to a natal chart.
- **Solar and lunar returns** for annual and monthly cycles.
- **Electional suggestions** when the transiting Moon trines the natal Sun.

## Future Work

Next development steps focus on improving the user interface.
Potential frontend upgrades include:
- **React + FastAPI** for a modern stack.
- **Flask + HTMX** for lighter enhancements.
- **Vue.js + Flask API** as a balanced approach.

-### Phase 4: Technical Excellence (1-2 weeks)

Focus areas for performance optimization:

- **Caching**: refine Redis usage for computed charts.
- **Database**: optimise the PostgreSQL schema for chart metadata.
- **API**: Pagination and filtering for chart lists.
- **Chart generation**: WebGL-driven interactive wheels.
