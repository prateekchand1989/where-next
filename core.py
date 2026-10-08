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

def sensitivity_weights(weights, factor, change):
    """Normalize current weights, then move one factor by percentage points."""
    current = np.asarray(weights, dtype=float)
    if (current.shape != (4,) or not np.isfinite(current).all()
            or (current < 0).any() or (current > 100).any() or current.sum() <= 0):
        raise ValueError('Use four weights between 0 and 100 with a positive total.')
    if factor not in range(4) or not np.isfinite(change):
        raise ValueError('Use a factor index from 0 to 3 and a finite change.')
    current = current / current.sum() * 100
    others = [i for i in range(4) if i != factor]
    adjusted = current.copy()
    adjusted[factor] = np.clip(current[factor] + change, 0, 100)
    remainder = 100 - adjusted[factor]
    other_total = current[others].sum()
    if other_total > 0:
        adjusted[others] = current[others] / other_total * remainder
    else:
        # No existing proportions: split any released weight equally.
        adjusted[others] = remainder / 3
    recipient = others[int(np.argmax(adjusted[others]))]
    adjusted[recipient] += 100 - adjusted.sum()
    return adjusted.tolist()


def weight_sensitivity(data, weights, factor, states, current_scored=None):
    """Rank all complete candidates before filtering; compare top-three membership."""
    scenarios = []
    for name, change in [('Current weight', 0), ('Selected factor minus 10 percentage points', -10),
                         ('Selected factor plus 10 percentage points', 10)]:
        adjusted = sensitivity_weights(weights, factor, change)
        scored = current_scored if change == 0 and current_scored is not None else score_counties(data, adjusted)
        ranked = scored[scored.complete & scored.state.isin(states)].copy()
        ranked['rank'] = np.arange(1, len(ranked) + 1)
        # Largest-remainder rounding for display only: exactly 10,000 basis points.
        scaled = np.asarray(adjusted) * 100
        rounded = np.floor(scaled).astype(int)
        order = np.argsort(-(scaled - rounded), kind='stable')
        for i in order[:10000 - rounded.sum()]:
            rounded[i] += 1
        scenarios.append({'name': name, 'weights': adjusted,
                          'display_weights': (rounded / 100).tolist(), 'ranked': ranked})
    current_ids = set(scenarios[0]['ranked'].head(3).fips)
    for scenario in scenarios:
        ranked = scenario.pop('ranked')
        top_ids = set(ranked.head(3).fips)
        tracked = ranked[ranked.fips.isin(current_ids | top_ids)].copy()
        tracked['change'] = [
            'Remains top three' if fips in current_ids and fips in top_ids
            else 'Drops out of top three' if fips in current_ids
            else 'Enters top three' for fips in tracked.fips]
        scenario['top_five'] = ranked.head(5)
        scenario['top_three_changes'] = tracked
    return scenarios


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
