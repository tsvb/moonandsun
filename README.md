# Moon and Sun Natal Chart

This project is a simple Flask web application that generates planetary positions for a natal chart using the [Swiss Ephemeris](https://www.astro.com/swisseph/).

## Setup

1. Install Python 3.12 or later.
2. Create a virtual environment (recommended) and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for running tests
```

## Running

Run the Flask app with:

```bash
python app.py
```

Visit `http://localhost:5000` in your browser and enter your birth details to generate the planetary positions.

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
