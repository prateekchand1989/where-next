"""Independent illustrative costs; no scoring, model calls, or network access."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

PAY_CONVERSION_HOURS = 2080  # 40 paid hours/week × 52 weeks; illustrative only.


@lru_cache(maxsize=1)
def load_lease_data():
    return json.loads((Path(__file__).parent / 'data/warehouse_leases.json').read_text(encoding='utf-8'))


def lease_benchmark(fips, scenario, dataset=None):
    """Exact, documented county mappings only; never a statewide/nearest fallback."""
    dataset = load_lease_data() if dataset is None else dataset
    for observation in dataset['observations']:
        if observation['warehouse_type'] == scenario and str(fips) in observation['county_fips']:
            source = dataset['sources'][observation['source_id']]
            return {**source, **observation, 'county_value_kind': 'modeled estimate',
                    'county_confidence': observation['mapping_confidence']}
    return None


@dataclass(frozen=True)
class CostAssumptions:
    facility_sqft: float | None
    labor_hours: float | None
    labor_burden_pct: float | None
    annual_kwh: float | None
    other_occupancy_psf: float | None


def _valid(value, positive=False):
    try:
        return value is not None and math.isfinite(value) and (value > 0 if positive else value >= 0)
    except TypeError:
        return False


def estimate_operating_cost(county, benchmark, assumptions):
    """Keep missing components missing; a partial subtotal is never a total."""
    a = assumptions
    pay = county.get('annual_pay') if county is not None else None
    electricity = county.get('electricity_cents_kwh') if county is not None else None
    rent = benchmark.get('asking_rent_psf_year') if benchmark else None
    basis_ok = benchmark is not None and benchmark.get('rent_basis') == 'Net asking; NNN detail not specified'
    sqft_ok = _valid(a.facility_sqft, positive=True)
    hourly = pay / PAY_CONVERSION_HOURS if _valid(pay, positive=True) else None
    components = {
        'Facility rent': a.facility_sqft * rent if sqft_ok and basis_ok and _valid(rent, positive=True) else None,
        'Workforce': a.labor_hours * hourly * (1 + a.labor_burden_pct / 100)
        if _valid(a.labor_hours) and hourly is not None and _valid(a.labor_burden_pct) else None,
        'Electricity': a.annual_kwh * electricity / 100
        if _valid(a.annual_kwh) and _valid(electricity, positive=True) else None,
        'Other occupancy': a.facility_sqft * a.other_occupancy_psf
        if sqft_ok and _valid(a.other_occupancy_psf) else None,
    }
    missing = [name for name, value in components.items() if value is None or not _valid(value)]
    total = sum(components.values()) if not missing else None
    return {'components': components, 'missing': missing, 'hourly_labor': hourly,
            'total_annual': total, 'annual_psf': total / a.facility_sqft if total is not None and sqft_ok else None}
