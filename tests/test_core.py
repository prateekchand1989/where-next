import numpy as np
import pytest
from core import METRICS, PRESETS, load_data, score_counties, distance_miles, annual_electricity_expense
from prepare_data import validate_bytes
from weather import get_alerts
from core import sensitivity_weights, weight_sensitivity


@pytest.mark.parametrize('weights,factor,change,expected', [
    ([40, 30, 20, 10], 0, 10, [50, 25, 50/3, 25/3]),
    ([40, 30, 20, 10], 0, -10, [30, 35, 70/3, 35/3]),
    ([5, 45, 30, 20], 0, -10, [0, 4500/95, 3000/95, 2000/95]),
    ([95, 3, 1, 1], 0, 10, [100, 0, 0, 0]),
    ([0, 50, 25, 25], 0, -10, [0, 50, 25, 25]),
    ([100, 0, 0, 0], 0, 10, [100, 0, 0, 0]),
    ([100, 0, 0, 0], 0, -10, [90, 10/3, 10/3, 10/3]),
    ([80, 60, 40, 20], 0, 10, [50, 25, 50/3, 25/3]),
])
def test_sensitivity_adjustments(weights, factor, change, expected):
    result = sensitivity_weights(weights, factor, change)
    assert result == pytest.approx(expected)
    assert sum(result) == pytest.approx(100)
    assert all(0 <= weight <= 100 for weight in result)
    assert result == sensitivity_weights(weights, factor, change)


def test_sensitivity_all_factors_and_rounding():
    data, _ = load_data()
    for factor in range(4):
        scenarios = weight_sensitivity(data, [1, 1, 1, 0], factor, ['PA'])
        repeat = weight_sensitivity(data, [1, 1, 1, 0], factor, ['PA'])
        for scenario, repeated in zip(scenarios, repeat):
            assert sum(scenario['display_weights']) == pytest.approx(100)
            assert sum(round(w * 100) for w in scenario['display_weights']) == 10000
            assert scenario['weights'] == repeated['weights']
            assert scenario['top_five'].equals(repeated['top_five'])
            assert scenario['top_three_changes'].equals(repeated['top_three_changes'])
            expected = score_counties(data, scenario['weights'])
            expected = expected[expected.complete & expected.state.eq('PA')].head(5)
            assert scenario['top_five'].fips.tolist() == expected.fips.tolist()
            assert scenario['top_five'].score.tolist() == expected.score.tolist()
            assert scenario['top_five']['rank'].tolist() == [1, 2, 3, 4, 5]
            assert scenario['top_five'].complete.all()
        baseline = score_counties(data, [1, 1, 1, 0])
        baseline = baseline[baseline.complete & baseline.state.eq('PA')].head(5)
        assert scenarios[0]['top_five'].score.tolist() == pytest.approx(baseline.score.tolist())
        current_ids = set(scenarios[0]['top_five'].head(3).fips)
        for scenario in scenarios:
            top_ids = set(scenario['top_five'].head(3).fips)
            changes = scenario['top_three_changes'].set_index('fips')['change'].to_dict()
            assert set(changes) == current_ids | top_ids
            for fips in current_ids | top_ids:
                expected = ('Remains top three' if fips in current_ids & top_ids
                            else 'Drops out of top three' if fips in current_ids
                            else 'Enters top three')
                assert changes[fips] == expected


@pytest.mark.parametrize('weights', [[0, 0, 0, 0], [-1, 30, 20, 10],
                                     [101, 0, 0, 0], [np.nan, 1, 1, 1], [1, 2, 3]])
def test_sensitivity_invalid_weights(weights):
    with pytest.raises(ValueError):
        sensitivity_weights(weights, 0, 10)


def test_sensitivity_no_complete_candidates():
    data, _ = load_data()
    data['annual_pay'] = np.nan
    for scenario in weight_sensitivity(data, [40, 30, 20, 10], 0, ['PA']):
        assert scenario['top_five'].empty
        assert scenario['top_three_changes'].empty

def test_real_data_and_geometry_are_complete():
    data, geometry=load_data()
    assert len(data)==262 and data.fips.is_unique
    assert set(data.fips)<=set(f['id'] for f in geometry['features'])
    assert data.population.notna().all()

def test_missing_is_not_cheap():
    data,_=load_data()
    scored=score_counties(data,PRESETS['General merchandise'])
    assert scored.score.notna().sum()==121
    assert scored.loc[~scored.complete,'score'].isna().all()
    broken=data.copy();broken.loc[0,'annual_pay']=np.nan
    assert not score_counties(broken,[40,30,20,10]).set_index('fips').loc[broken.loc[0,'fips'],'complete']

def test_cost_direction_and_weight_validation():
    data,_=load_data()
    s=score_counties(data,[0,100,0,0]); valid=s[s.complete]
    assert valid.iloc[0].annual_pay==valid.annual_pay.min()
    with pytest.raises(ValueError):score_counties(data,[0,0,0,0])
    with pytest.raises(ValueError):score_counties(data,[-1,30,20,10])

def test_reference_and_determinism():
    data,_=load_data()
    a=score_counties(data,[40,30,20,10]);b=score_counties(data,[40,30,20,10])
    assert a.equals(b)
    assert a[a.state=='PA'].score.equals(b[b.state=='PA'].score)
    assert a.loc[a.complete,'score'].between(0,100).all()
    assert not a.score.equals(score_counties(data,[30,25,15,30]).score)

def test_annual_electricity_expense():
    assert annual_electricity_expense(1000, 10) == pytest.approx(100)
    assert np.isnan(annual_electricity_expense(1000, np.nan))


def test_distance_identity_and_known_scale():
    assert distance_miles(40,-75,np.array([40]),np.array([-75]))[0]==0
    assert 68<distance_miles(0,0,np.array([1]),np.array([0]))[0]<70

def test_html_rejected_even_if_http_success():
    with pytest.raises(ValueError):validate_bytes('population.csv',b'<html>'+b'x'*200)

def test_weather_failure_is_not_no_alerts(monkeypatch):
    def fail(*args,**kwargs):raise TimeoutError()
    monkeypatch.setattr('urllib.request.urlopen',fail)
    result=get_alerts(40,-75)
    assert result['status']=='unavailable' and 'alerts' not in result
