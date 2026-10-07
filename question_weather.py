"""On-submission operational weather enrichment, independent of county scoring."""
import re
from datetime import datetime, timezone

from interpretation import weather_evidence


def weather_targets(question, context):
    # A plain shortlist/ranking request doesn't need five point forecasts.
    if context['kind'] == 'current_shortlist' and not re.search(
            r'\b(risk|risks|weather|forecast|forecasts|alert|alerts|storm|storms|flood|hazard|hazards|disruption)\b',
            question, re.I):
        return []
    targets = list(dict.fromkeys(context['fips']))
    return targets[:3] if context['kind'] == 'selected_comparison' else targets


def enrich_weather(question, context, data, session_weather, alerts, forecast, now=None):
    """Caller must guard with explicit submission. Reuse fresh session/cache results."""
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    points = data.set_index('fips')
    for fips in weather_targets(question, context):
        if fips not in points.index:
            continue
        row = points.loc[fips]
        saved = session_weather.setdefault(fips, {})
        for kind, fetch in [('alerts', alerts), ('forecast', forecast)]:
            if weather_evidence(saved.get(kind), kind, now)['status'] == 'ok':
                continue
            lat, lon = float(row.lat), float(row.lon)
            try:
                result = fetch(lat, lon)
                # Cached check time can expire before the cache entry's own TTL.
                checked_at = fixed_now or datetime.now(timezone.utc)
                if weather_evidence(result, kind, checked_at)['status'] == 'stale':
                    if hasattr(fetch, 'clear'):
                        fetch.clear(lat, lon)
                    result = fetch(lat, lon)
                saved[kind] = result
            except Exception:
                saved[kind] = {'status': 'unavailable'}
    return session_weather
