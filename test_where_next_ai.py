import tomllib
from interpretation import OpenAIProvider

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

provider = OpenAIProvider(
    secrets["OPENAI_API_KEY"],
    secrets.get("OPENAI_MODEL", "gpt-4.1-mini"),
)

evidence = {
    "schema_version": 1,
    "baseline_year": 2024,
    "scenario": "Diagnostic test",
    "candidate_states": ["PA"],
    "priority_weights_pct": {
        "Market reach": 40,
        "Lower labor benchmark": 30,
        "Workforce depth": 20,
        "Lower electricity benchmark": 10,
    },
    "current_leader": "Unavailable",
    "selected_counties": [],
    "annual_electricity_consumption_kwh": "Unavailable",
    "fema_source": {"status": "Unavailable"},
    "sensitivity": {
        "factor": "Market reach",
        "scenarios": []
    }
}

try:
    result = provider.explain(evidence)
    print("SUCCESS")
    print(result)

except Exception as e:
    print("ERROR TYPE:", type(e).__name__)
    print("ERROR MESSAGE:", str(e))