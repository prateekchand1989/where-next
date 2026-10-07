import json
import tomllib
import urllib.request
import urllib.error

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

body = {
    "model": "gpt-4.1-mini",
    "input": "Reply with exactly: API WORKING"
}

request = urllib.request.Request(
    "https://api.openai.com/v1/responses",
    data=json.dumps(body).encode(),
    headers={
        "Authorization": "Bearer " + secrets["OPENAI_API_KEY"],
        "Content-Type": "application/json",
    },
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        print("STATUS:", response.status)
        print(response.read().decode()[:2000])

except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read().decode()[:3000])

except Exception as e:
    print(type(e).__name__, str(e))