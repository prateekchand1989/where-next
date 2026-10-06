import json
import urllib.request
from urllib.parse import urlsplit
import math
import ssl
import socket
import errno
from http.client import responses as http_responses
from urllib.error import HTTPError, URLError
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


def get_forecast(lat, lon, timeout=15):
    """Fetch an NWS representative-point forecast; callers may cache for 15 minutes.

    This is not county-wide or route-wide weather coverage and is not scoring data.
    """
    points_url = f'https://api.weather.gov/points/{lat:.4f},{lon:.4f}'
    url = points_url
    stage = 'points'
    http_status = None
    try:
        def fetch(target):
            nonlocal http_status
            request = urllib.request.Request(target, headers={
                'User-Agent': 'WhereNext/0.1 (public portfolio demo)',
                'Accept': 'application/geo+json',
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                http_status = getattr(response, 'status', None)
                payload = json.load(response)
            if (not isinstance(payload, dict) or payload.get('type') != 'Feature'
                    or not isinstance(payload.get('properties'), dict)):
                raise ValueError('Unexpected NWS response format')
            return payload['properties']

        points = fetch(points_url)
        forecast_url = points.get('forecast')
        if not isinstance(forecast_url, str):
            raise ValueError('Missing NWS forecast URL')
        parsed = urlsplit(forecast_url)
        if (parsed.scheme != 'https' or parsed.netloc != 'api.weather.gov'
                or not parsed.path or parsed.fragment):
            raise ValueError('Unexpected NWS forecast URL')
        url = forecast_url
        stage = 'forecast'
        http_status = None
        forecast = fetch(url)
        periods = forecast.get('periods')
        if not isinstance(periods, list) or not periods:
            raise ValueError('Missing NWS forecast periods')
        fields = ('name', 'temperatureUnit', 'shortForecast', 'windSpeed', 'windDirection')
        for period in periods:
            if (not isinstance(period, dict)
                    or any(not isinstance(period.get(field), str) or not period[field].strip()
                           for field in fields)
                    or isinstance(period.get('temperature'), bool)
                    or not isinstance(period.get('temperature'), (int, float))
                    or not math.isfinite(period['temperature'])):
                raise ValueError('Unexpected NWS forecast period')
        for field in ('updated', 'generatedAt', 'updateTime'):
            if forecast.get(field) is not None:
                if not isinstance(forecast[field], str):
                    raise ValueError('Unexpected NWS forecast timestamp')
                datetime.fromisoformat(forecast[field].replace('Z', '+00:00'))
        return {
            'status': 'ok', 'url': url, 'points_url': points_url,
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'updated': forecast.get('updated') or forecast.get('updateTime'),
            'generated_at': forecast.get('generatedAt'),
            'periods': [{field: period[field] for field in (*fields, 'temperature')}
                        for period in periods],
        }
    except Exception as exc:
        # Use controlled messages, never response bodies, headers, proxy settings,
        # or arbitrary exception text that could contain credentials.
        if isinstance(exc, HTTPError):
            http_status = exc.code
            message = f'HTTP {exc.code}: {http_responses.get(exc.code, "Request failed")}'
        else:
            reason = exc.reason if isinstance(exc, URLError) else exc
            if isinstance(reason, ssl.SSLCertVerificationError):
                message = 'TLS certificate verification failed'
            elif isinstance(reason, ssl.SSLError):
                message = 'TLS connection failed'
            elif isinstance(reason, TimeoutError):
                message = 'Request timed out'
            elif isinstance(reason, socket.gaierror):
                message = 'DNS resolution failed'
            elif isinstance(exc, URLError):
                message = 'Network connection unavailable'
                if isinstance(reason, OSError) and reason.errno is not None:
                    message += ': ' + errno.errorcode.get(reason.errno, f'OS error {reason.errno}')
            elif isinstance(exc, json.JSONDecodeError):
                message = 'Response was not valid JSON'
            elif isinstance(exc, ValueError):
                message = 'NWS response failed validation'
            else:
                message = 'NWS request failed'
        return {'status': 'unavailable', 'url': url, 'points_url': points_url,
                'error': type(exc).__name__, 'stage': stage,
                'http_status': http_status, 'message': message}
