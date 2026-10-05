"""Deterministic, inspectable screening calculations; no model calls."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
METRICS = ['reach_250mi', 'annual_pay', 'employment', 'electricity_cents_kwh']
LABELS = ['Market reach', 'Lower labor benchmark', 'Workforce depth', 'Lower electricity benchmark']
PRESETS = {'General merchandise': [40, 30, 20, 10], 'Temperature-controlled': [30, 25, 15, 30]}

def load_data():
    data = pd.read_csv(ROOT / 'data/counties.csv', dtype={'fips': str})
    geometry = json.loads((ROOT / 'data/counties.geojson').read_text())
    return data, geometry

def score_counties(data, weights):
    """Normalize against all complete five-state candidates BEFORE filtering."""
    weights = np.asarray(weights, dtype=float)
    if len(weights) != 4 or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('Use four nonnegative weights with at least one above zero.')
    out = data.copy()
    complete = out[METRICS].notna().all(axis=1) & (out[METRICS] > 0).all(axis=1)
    out['complete'] = complete
    for metric, inverse in zip(METRICS, [False, True, False, True]):
        values = out.loc[complete, metric]
        if len(values) > 1:
            component = 100 * (values.rank(method='average') - 1) / (len(values) - 1)
        else:
            component = pd.Series(50.0, index=values.index)
        out.loc[complete, metric + '_score'] = 100 - component if inverse else component
    out['score'] = np.nan
    columns = [m + '_score' for m in METRICS]
    out.loc[complete, 'score'] = (out.loc[complete, columns] * (weights / weights.sum())).sum(axis=1)
    return out.sort_values(['score', 'fips'], ascending=[False, True], na_position='last').reset_index(drop=True)

def annual_electricity_expense(annual_kwh, electricity_cents_kwh):
    """Illustrative dollars using a state average, not a property tariff."""
    return annual_kwh * electricity_cents_kwh / 100


def distance_miles(lat, lon, latitudes, longitudes):
    a, b = np.radians(latitudes), np.radians(longitudes)
    p, q = np.radians(lat), np.radians(lon)
    h = np.sin((a-p)/2)**2 + np.cos(p)*np.cos(a)*np.sin((b-q)/2)**2
    return 3958.7613 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))

def evidence_brief(row):
    if not row['complete']:
        return 'Incomplete labor data: this county is shown on the map but is not ranked.'
    return (
        f"{row['county']}, {row['state']}: screening score {row['score']:.1f}/100 under the current weights. "
        f"The 2024 county-point approximation places {row['reach_250mi']:,.0f} people within 250 straight-line miles. "
        f"Private warehousing/storage employment is {row['employment']:,.0f}; average annual pay is ${row['annual_pay']:,.0f}. "
        f"The 2024 state commercial electricity benchmark is {row['electricity_cents_kwh']:.2f} cents/kWh. "
        'These are screening indicators, not a hiring forecast, delivery promise, site quote, or validated optimum.'
    )
