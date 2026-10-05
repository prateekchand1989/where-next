import numpy as np
import pytest
from core import METRICS, PRESETS, load_data, score_counties, distance_miles, annual_electricity_expense
from prepare_data import validate_bytes
from weather import get_alerts

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
