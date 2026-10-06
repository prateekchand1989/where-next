"""County hazard context, deliberately independent of screening calculations."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
ITEM_URL = 'https://www.arcgis.com/sharing/rest/content/items/39485e8035d446a5bff03259508ae355'
LAYER_URL = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0'
# Verified against the current FEMA layer's field names and aliases.
FIELDS = {
    'RISK_SCORE': 'Overall FEMA risk score',
    'RISK_RATNG': 'Overall FEMA risk rating',
    'EAL_VALT': 'County expected annual loss (USD/year)',
    'IFLD_RISKS': 'Inland flooding risk score',
    'IFLD_RISKR': 'Inland flooding risk rating',
    'CFLD_RISKS': 'Coastal flooding risk score',
    'CFLD_RISKR': 'Coastal flooding risk rating',
    'WNTW_RISKS': 'Winter weather risk score',
    'WNTW_RISKR': 'Winter weather risk rating',
    'HRCN_RISKS': 'Hurricane risk score',
    'HRCN_RISKR': 'Hurricane risk rating',
    'NRI_VER': 'FEMA source release',
}
NUMERIC_FIELDS = [field for field in FIELDS if field.endswith(('SCORE', 'RISKS', 'VALT'))]


def normalize_fips(values):
    result = values.astype('string').str.strip()
    if not result.str.fullmatch(r'[0-9]{1,5}').fillna(False).all():
        raise ValueError('FEMA join requires valid county FIPS codes (1–5 digits).')
    return result.str.zfill(5).astype(str)


def join_fema(counties, source):
    """Left join on FIPS only. Reject duplicates instead of multiplying counties."""
    required = {'STCOFIPS', *FIELDS}
    if missing := required - set(source.columns):
        raise ValueError(f'FEMA schema missing fields: {sorted(missing)}')
    left = counties.copy()
    right = source[['STCOFIPS', *FIELDS]].copy()
    left['fips'] = normalize_fips(left['fips'])
    right['STCOFIPS'] = normalize_fips(right['STCOFIPS'])
    for label, codes in [('Where Next', left.fips), ('FEMA', right.STCOFIPS)]:
        duplicates = sorted(codes[codes.duplicated(keep=False)].unique().tolist())
        if duplicates:
            raise ValueError(f'{label} duplicate FIPS: {duplicates}; join aborted.')
    for field in NUMERIC_FIELDS:
        right[field] = pd.to_numeric(right[field], errors='raise')
        if (right[field].dropna() < 0).any():
            raise ValueError(f'Unexpected negative FEMA value in {field}; review schema.')
        if field != 'EAL_VALT' and (right[field].dropna() > 100).any():
            raise ValueError(f'Unexpected FEMA score outside 0–100 in {field}.')
    for field in set(FIELDS) - set(NUMERIC_FIELDS):
        right[field] = right[field].astype('string').str.strip().replace('', pd.NA)
    joined = left.merge(right, how='left', left_on='fips', right_on='STCOFIPS',
                        validate='one_to_one', indicator='_fema_join')
    matched = int(joined['_fema_join'].eq('both').sum())
    report = {'matched': matched, 'unmatched': len(left) - matched,
              'duplicate_fips': [], 'unmatched_fips': joined.loc[
                  joined['_fema_join'].eq('left_only'), 'fips'].tolist()}
    return joined.drop(columns=['STCOFIPS', '_fema_join']), report


def load_fema_context(counties, directory=None):
    """Read only local snapshots; missing/invalid FEMA must not prevent screening."""
    directory = Path(directory) if directory is not None else ROOT / 'data'
    try:
        source = pd.read_csv(directory / 'fema_counties.csv', dtype={'STCOFIPS': 'string'})
        metadata = json.loads((directory / 'fema_sources.json').read_text())
        required_metadata = ('version', 'retrieved_utc', 'source_data_updated_utc', 'source_url')
        if (not isinstance(metadata, dict)
                or any(not isinstance(metadata.get(field), str) or not metadata[field]
                       for field in required_metadata)):
            raise ValueError('FEMA snapshot has missing or invalid source metadata.')
        joined, report = join_fema(counties[['fips']], source)
        return joined, {**metadata, **report, 'status': 'ok'}
    except (OSError, ValueError, KeyError) as exc:
        return pd.DataFrame(), {'status': 'unavailable', 'error': str(exc)}
