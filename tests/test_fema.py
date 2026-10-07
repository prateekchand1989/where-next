"""Offline FEMA tests; sample rows are from the official December 2025 layer."""
import json
from pathlib import Path

import pandas as pd
import pytest

from core import METRICS, PRESETS, load_data, score_counties
from fema import FIELDS, join_fema, load_fema_context, normalize_fips


@pytest.fixture
def source():
    return pd.read_csv(Path(__file__).parent / 'fixtures/fema_sample.csv',
                       dtype={'STCOFIPS': 'string'})


def test_fips_join_preserves_counties_and_order(source):
    counties = pd.DataFrame({'fips': ['42069', '24001', '01001'],
                             'county': ['Deliberately unrelated name'] * 3})
    joined, report = join_fema(counties, source)
    assert joined.fips.tolist() == counties.fips.tolist()
    assert joined.fips.is_unique
    assert report == {'matched': 2, 'unmatched': 1, 'duplicate_fips': [],
                      'unmatched_fips': ['01001']}
    assert joined.loc[0, 'RISK_SCORE'] == source.set_index('STCOFIPS').loc['42069', 'RISK_SCORE']
    assert joined.loc[2, list(FIELDS)].isna().all()


def test_leading_zeros_preserved_in_join(source):
    # Synthetic identifier change only, exercising FIPS normalization offline.
    source.loc[0, 'STCOFIPS'] = '1001'
    joined, report = join_fema(pd.DataFrame({'fips': ['01001']}), source)
    assert joined.fips.tolist() == ['01001']
    assert report['matched'] == 1
    assert normalize_fips(pd.Series(['01001', '1001'])).tolist() == ['01001', '01001']


@pytest.mark.parametrize('side', ['source', 'counties'])
def test_duplicate_counties_fail_clearly(source, side):
    counties = pd.DataFrame({'fips': ['24001']})
    if side == 'source':
        source = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    else:
        counties = pd.concat([counties, counties], ignore_index=True)
    with pytest.raises(ValueError, match='duplicate FIPS.*join aborted'):
        join_fema(counties, source)


def test_missing_values_stay_missing(source):
    source.loc[source.STCOFIPS.eq('24001'), ['RISK_SCORE', 'EAL_VALT', 'HRCN_RISKS']] = None
    source.loc[source.STCOFIPS.eq('24001'), 'CFLD_RISKR'] = 'Not Applicable'
    joined, _ = join_fema(pd.DataFrame({'fips': ['24001']}), source)
    assert joined[['RISK_SCORE', 'EAL_VALT', 'HRCN_RISKS']].isna().all().all()
    assert joined.loc[0, 'CFLD_RISKR'] == 'Not Applicable'


def test_hazard_fields_do_not_affect_scoring(source):
    counties, _ = load_data()
    enriched, _ = join_fema(counties, source)
    for field in FIELDS:
        if field.endswith(('SCORE', 'RISKS', 'VALT')):
            enriched[field] = 100
    for weights in PRESETS.values():
        baseline = score_counties(counties, weights)
        actual = score_counties(enriched, weights)
        pd.testing.assert_frame_equal(actual[baseline.columns], baseline)
    assert list(METRICS) == ['reach_250mi', 'annual_pay', 'employment', 'electricity_cents_kwh']


def test_missing_source_schema_fails(source):
    with pytest.raises(ValueError, match='schema missing fields'):
        join_fema(pd.DataFrame({'fips': ['24001']}), source.drop(columns='IFLD_RISKS'))


def test_loader_reports_unavailable_without_zero_values(tmp_path):
    context, metadata = load_fema_context(pd.DataFrame({'fips': ['24001']}), tmp_path)
    assert context.empty and metadata['status'] == 'unavailable'


@pytest.mark.parametrize('metadata', [{}, [], {'version': 'December 2025'}])
def test_loader_handles_invalid_metadata(source, tmp_path, metadata):
    source.to_csv(tmp_path / 'fema_counties.csv', index=False)
    (tmp_path / 'fema_sources.json').write_text(json.dumps(metadata))
    context, result = load_fema_context(pd.DataFrame({'fips': ['24001']}), tmp_path)
    assert context.empty and result['status'] == 'unavailable'
    assert 'invalid source metadata' in result['error']


def test_app_usable_without_fema(monkeypatch, tmp_path):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    def unavailable(counties):
        return load_fema_context(counties, tmp_path)

    monkeypatch.setattr('fema.load_fema_context', unavailable)
    st.cache_data.clear()
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.session_state['experience_mode'] = 'analysis'
    app.run()
    assert not app.exception
    assert any('FEMA hazard data unavailable' in element.value for element in app.info)
    assert any(frame.value.columns.tolist()[0] == 'County' for frame in app.dataframe)
    baseline_metrics = [metric.value for metric in app.metric]
    next(widget for widget in app.selectbox if widget.label == 'Map view').select('FEMA risk context').run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == baseline_metrics
    assert any('FEMA risk context unavailable' in element.value for element in app.info)
    next(widget for widget in app.selectbox if widget.label == 'Map view').select('Warehouse screening score').run()
    assert not app.exception
    st.cache_data.clear()


def test_app_fema_context_and_map_with_fixture(monkeypatch, source, tmp_path):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    source.to_csv(tmp_path / 'fema_counties.csv', index=False)
    (tmp_path / 'fema_sources.json').write_text(json.dumps({
        'version': 'December 2025 (1.20.0)', 'retrieved_utc': '2026-10-06T00:00:00Z',
        'source_data_updated_utc': '2025-12-16T07:37:01Z',
        'source_url': 'https://services.arcgis.com/example'}))
    monkeypatch.setattr('fema.load_fema_context', lambda counties: load_fema_context(counties, tmp_path))
    st.cache_data.clear()
    app = AppTest.from_file('../app.py', default_timeout=60)
    app.session_state['experience_mode'] = 'analysis'
    app.run()
    next(widget for widget in app.multiselect if widget.label == 'Choose up to three counties').set_value(['42069']).run()
    assert not app.exception
    panel = next(frame.value for frame in app.dataframe if 'Overall FEMA risk score' in frame.value.columns)
    assert panel.iloc[0]['County'] == 'Lackawanna County, PA'
    assert panel.iloc[0]['Overall FEMA risk score'] != 'Unavailable'
    baseline_metrics = [metric.value for metric in app.metric]
    next(widget for widget in app.selectbox if widget.label == 'Map view').select('FEMA risk context').run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == baseline_metrics
    st.cache_data.clear()
