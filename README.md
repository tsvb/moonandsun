# Moon and Sun Natal Chart

This project is a simple Flask web application that generates planetary positions for a natal chart using the [Swiss Ephemeris](https://www.astro.com/swisseph/).
The application now also calculates major aspects between planets with their orb strength, identifies the chart ruler based on the ascendant sign and draws a chart wheel illustrating the houses and planetary locations.

## Setup

1. Install Python 3.12 or later.
2. Create a virtual environment (recommended) and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for running tests
```
The `requirements.txt` file now includes `matplotlib` which is used to draw the chart wheel.

The application uses Flask sessions and expects a secret key. Set the
`SECRET_KEY` environment variable to override the default development key.

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

## Packaging

You can create standalone executables for Windows, macOS and Linux using [PyInstaller](https://www.pyinstaller.org/). The repository includes a `natal_chart.spec` file that bundles the templates and license.
Binary icon assets are not included in the repository (some tools cannot display them in diffs). Provide your own icon files inside the `icons/` directory (e.g. `icon.ico` for Windows and `icon.icns` for macOS) if you want a custom installer graphic.

Install PyInstaller and run it with the spec file:

```bash
pip install pyinstaller
pyinstaller natal_chart.spec
```

The resulting executable will be placed in the `dist/` directory. If you added `icons/icon.ico` before building on Windows (or `icon.icns` on macOS) the installer will include it automatically.
