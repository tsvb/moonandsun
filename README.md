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
