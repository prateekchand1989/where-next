"""Download official files and prepare a reproducible 2024 baseline.
Run: python prepare_data.py
Valid existing raw downloads are reused; delete an individual raw file to refresh.
The bundled processed data lets app.py run without any download or API key.
"""
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import shapefile
from core import distance_miles

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data/raw'
SOURCES = {
 'population.csv': 'https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv',
 'qcew.csv': 'https://data.bls.gov/cew/data/api/2024/a/industry/493.csv',
 'gazetteer.zip': 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip',
 'counties.zip': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_20m.zip',
 'energy.xlsx': 'https://www.eia.gov/electricity/sales_revenue_price/xls/table_4.xlsx',
}
STATES = {'24':'MD', '34':'NJ', '36':'NY', '39':'OH', '42':'PA'}

def validate_bytes(name, content):
    if len(content) < 100 or content.lstrip().lower().startswith((b'<html', b'<!doctype')):
        raise ValueError(f'{name}: source returned an empty file or HTML, not data.')
    if name.endswith(('.zip', '.xlsx')) and not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError(f'{name}: source did not return a valid ZIP/XLSX.')

def prepare():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url in SOURCES.items():
        path = RAW / name
        if path.exists():
            content = path.read_bytes()
        else:
            request = urllib.request.Request(url, headers={'User-Agent':'WhereNext/0.1 (public data portfolio prototype)'})
            with urllib.request.urlopen(request, timeout=45) as response:
                content = response.read()
            validate_bytes(name, content)
            path.write_bytes(content)
        validate_bytes(name, content)
        manifest.append({'file':name, 'url':url, 'observation_period':'2024', 'sha256':hashlib.sha256(content).hexdigest(),
                         'local_file_timestamp_utc':datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
        print(f'OK {name}: {len(content):,} bytes')

    pop = pd.read_csv(RAW/'population.csv', encoding='latin-1')
    pop = pop[pop.SUMLEV.eq(50)].copy()
    pop['fips'] = pop.STATE.astype(str).str.zfill(2) + pop.COUNTY.astype(str).str.zfill(3)
    with zipfile.ZipFile(RAW/'gazetteer.zip') as z:
        gaz = pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('.txt'))), sep='\t', dtype={'GEOID':str})
    gaz.columns = gaz.columns.str.strip()
    national = pop.merge(gaz[['GEOID','INTPTLAT','INTPTLONG']], left_on='fips', right_on='GEOID', validate='one_to_one')
    if national[['INTPTLAT','INTPTLONG','POPESTIMATE2024']].isna().any().any():
        raise ValueError('Population/location join has missing values.')
    if len(national) < 3000:
        raise ValueError('Population/location join unexpectedly lost most U.S. counties.')
    data = national[national.fips.str[:2].isin(STATES)].copy()
    data['state'] = data.fips.str[:2].map(STATES)
    data['county'] = data.CTYNAME
    data['lat'], data['lon'], data['population'] = data.INTPTLAT, data.INTPTLONG, data.POPESTIMATE2024
    data['reach_250mi'] = [int(national.loc[distance_miles(r.lat,r.lon,national.INTPTLAT.values,national.INTPTLONG.values)<=250,'POPESTIMATE2024'].sum()) for r in data.itertuples()]

    q = pd.read_csv(RAW/'qcew.csv', dtype={'area_fips':str, 'industry_code':str, 'disclosure_code':str})
    q = q[q.own_code.eq(5) & q.industry_code.eq('493') & q.agglvl_code.eq(75) & q.size_code.eq(0)].copy()
    hidden = q.disclosure_code.fillna('').str.strip().ne('')
    q['employment'] = q.annual_avg_emplvl.where(~hidden & q.annual_avg_emplvl.gt(0))
    q['annual_pay'] = q.avg_annual_pay.where(~hidden & q.avg_annual_pay.gt(0))
    q['labor_status'] = np.where(hidden, 'Suppressed by BLS', 'Available')
    data = data.merge(q[['area_fips','employment','annual_pay','labor_status']], left_on='fips', right_on='area_fips', how='left', validate='one_to_one')
    data['labor_status'] = data.labor_status.fillna('No matching published BLS row')
    energy = pd.read_excel(RAW/'energy.xlsx', header=None)
    if not str(energy.iloc[0,0]).startswith('2024 '):
        raise ValueError('EIA table changed its year. Review the new period before replacing the 2024 baseline.')
    header_rows = energy.index[energy.iloc[:,0].astype(str).str.strip().eq('State')]
    if len(header_rows) != 1:
        raise ValueError('EIA header changed; inspect table_4.xlsx.')
    i = header_rows[0]
    energy.columns = energy.iloc[i].astype(str).str.strip()
    energy = energy.iloc[i+1:].copy()
    energy['State'] = energy.State.astype(str).str.strip()
    prices = pd.to_numeric(energy.set_index('State')['Commercial'], errors='coerce')
    data['electricity_cents_kwh'] = data.STNAME.map(prices)
    if data.electricity_cents_kwh.isna().any():
        raise ValueError('Missing EIA commercial rate for a candidate state.')
    columns = ['fips','county','state','lat','lon','population','reach_250mi','employment','annual_pay','electricity_cents_kwh','labor_status']
    data = data[columns].sort_values('fips')
    if len(data) != 262 or data.fips.duplicated().any():
        raise ValueError(f'Expected 262 unique candidate counties; got {len(data)}.')
    with zipfile.ZipFile(RAW/'counties.zip') as z:
        find = lambda suffix: io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(suffix))))
        reader = shapefile.Reader(shp=find('.shp'), shx=find('.shx'), dbf=find('.dbf'))
        features = []
        for record in reader.iterShapeRecords():
            props = record.record.as_dict()
            # Contiguous U.S. backdrop; analysis still covers five states only.
            if props['STATEFP'] not in {'02','15','60','66','69','72','78'}:
                features.append({'type':'Feature','id':props['GEOID'], 'properties':{'name':props['NAMELSAD'],'state':props['STUSPS']}, 'geometry':record.shape.__geo_interface__})
    if not set(data.fips).issubset({f['id'] for f in features}):
        raise ValueError('Some candidate counties do not match the map.')
    data.to_csv(ROOT/'data/counties.csv', index=False)
    (ROOT/'data/counties.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}, separators=(',',':')))
    (ROOT/'data/sources.json').write_text(json.dumps({'prepared_utc':datetime.now(timezone.utc).isoformat(),'sources':manifest}, indent=2))
    print(f'READY: {len(data)} counties; {data[["employment","annual_pay"]].notna().all(axis=1).sum()} complete labor records; all map joins matched.')

if __name__ == '__main__':
    prepare()
