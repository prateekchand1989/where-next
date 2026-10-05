import json
import urllib.request
from datetime import datetime, timezone

def get_alerts(lat, lon, timeout=15):
    """Point query: explicitly not county-wide or route-wide weather coverage."""
    url = f'https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}'
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'WhereNext/0.1 (public portfolio demo)', 'Accept':'application/geo+json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        if payload.get('type') != 'FeatureCollection' or not isinstance(payload.get('features'),list):
            raise ValueError('Unexpected NWS response format')
        return {'status':'ok','url':url,'checked_utc':datetime.now(timezone.utc).isoformat(),
                'alerts':[{'event':f['properties'].get('event'), 'headline':f['properties'].get('headline'),
                           'expires':f['properties'].get('expires'), 'area':f['properties'].get('areaDesc')} for f in payload['features']]}
    except Exception as exc:
        return {'status':'unavailable','url':url,'error':type(exc).__name__}
