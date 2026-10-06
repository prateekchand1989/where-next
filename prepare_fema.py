"""Refresh a separate official FEMA county snapshot: python prepare_fema.py.

Never rebuild or modify the warehouse baseline. Inspect live metadata/schema on
every run and stop if the selected fields or release metadata have changed.
"""
import hashlib
import json
import re
import urllib.request
from urllib.parse import urlencode
from datetime import datetime, timezone

import pandas as pd

from fema import ROOT, ITEM_URL, LAYER_URL, FIELDS, join_fema, normalize_fips


def fetch_json(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'WhereNext/0.1 (public data portfolio prototype)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or 'error' in payload:
        raise ValueError('FEMA service returned an invalid response or API error.')
    return payload, raw


def prepare():
    item, _ = fetch_json(ITEM_URL + '?f=json')
    if item.get('owner') != 'FEMA_NationalRiskIndex':
        raise ValueError('Expected the official FEMA National Risk Index publisher.')
    version = re.search(r'National Risk Index Data Version:\s*([^<]+)', item.get('description', ''))
    if not version:
        raise ValueError('FEMA release metadata changed; inspect the current item.')
    schema, _ = fetch_json(LAYER_URL + '?f=json')
    fields = {field['name']: field for field in schema['fields']}
    selected = ['STCOFIPS', *FIELDS]
    if missing := set(selected) - set(fields):
        raise ValueError(f'Current FEMA schema missing fields: {sorted(missing)}')
    counties = pd.read_csv(ROOT / 'data/counties.csv', dtype={'fips': 'string'})
    # Query the five candidate states; the actual join still uses county FIPS only.
    states = sorted(counties.fips.str[:2].unique())
    where = 'STATEFIPS IN (' + ','.join(f"'{state}'" for state in states) + ')'
    params = {'f': 'json', 'where': where, 'outFields': ','.join(selected),
              'returnGeometry': 'false', 'orderByFields': 'STCOFIPS', 'resultRecordCount': 1000}
    query_url = LAYER_URL + '/query?' + urlencode(params)
    payload, raw = fetch_json(query_url)
    if payload.get('exceededTransferLimit'):
        raise ValueError('FEMA response truncated; implement pagination before proceeding.')
    features = payload.get('features')
    if not isinstance(features, list) or not features:
        raise ValueError('FEMA service returned no county records.')
    source = pd.DataFrame([feature['attributes'] for feature in features])
    joined, report = join_fema(counties[['fips']], source)
    snapshot = joined[joined.fips.isin(normalize_fips(source.STCOFIPS))].rename(
        columns={'fips': 'STCOFIPS'})
    metadata = {
        'source': 'FEMA National Risk Index Counties', 'source_url': LAYER_URL,
        'item_url': ITEM_URL, 'query_url': query_url,
        'version': version.group(1).strip(),
        'retrieved_utc': datetime.now(timezone.utc).isoformat(),
        'source_data_updated_utc': datetime.fromtimestamp(
            schema['editingInfo']['dataLastEditDate'] / 1000, timezone.utc).isoformat(),
        'fields': {name: fields[name]['alias'] for name in selected},
        'response_sha256': hashlib.sha256(raw).hexdigest(),
        'source_counties': len(source), **report,
    }
    # Keep raw evidence outside Git; bundled outputs let the app work offline.
    raw_dir = ROOT / 'data/raw'
    raw_dir.mkdir(exist_ok=True)
    (raw_dir / 'fema_response.json').write_bytes(raw)
    snapshot.to_csv(ROOT / 'data/fema_counties.csv', index=False)
    (ROOT / 'data/fema_sources.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    prepare()
