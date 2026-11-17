import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta

API_KEY = os.environ.get("IFPA_API_KEY", "").strip()
OUT_FILE = "tournaments.json"
NOW = datetime.utcnow()
TODAY = NOW.strftime("%Y-%m-%d")
END_DATE = (NOW + timedelta(days=365)).strftime("%Y-%m-%d")

VENUES = [
    {
        "name": "Morristown Game Vault",
        "address": "22 South St, Morristown, NJ 07960",
        "lat": 40.7968,
        "lon": -74.4815,
        "radius": 5,
        "match_terms": ["morristown game vault", "22 south"]
    }
]

if not API_KEY:
    raise RuntimeError("IFPA_API_KEY secret is missing.")

all_tournaments = []
seen_ids = set()

for v in VENUES:
    params = urllib.parse.urlencode({
        "api_key": API_KEY,
        "latitude": v["lat"],
        "longitude": v["lon"],
        "radius": v["radius"],
        "distance_type": "m",
        "start_date": TODAY,
        "end_date": END_DATE
    })
    url = f"https://ifpapinball.com?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "PinballCaddyIFPABot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = json.loads(r.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"IFPA API HTTP {e.code}: {err_body}")

    events = []
    if isinstance(payload, dict):
        events = payload.get("tournaments") or payload.get("tournament") or payload.get("calendar") or []

    for ev in events:
        tid = str(ev.get("tournament_id", ""))
        if not tid or tid in seen_ids:
            continue
        blob = " ".join([
            str(ev.get("tournament_name", "")),
            str(ev.get("address1", "")),
            str(ev.get("address2", "")),
            str(ev.get("city", "")),
            str(ev.get("raw_address", "")),
            str(ev.get("details", ""))
        ]).lower()

        if any(term in blob for term in v["match_terms"]):
            seen_ids.add(tid)
            start_d = str(ev.get("event_start_date") or ev.get("start_date") or "")[:10]
            end_d = str(ev.get("event_end_date") or ev.get("end_date") or "")[:10]
            all_tournaments.append({
                "tournament_id": tid,
                "venue_id": v["name"],
                "name": ev.get("tournament_name", "IFPA Tournament"),
                "start_date": start_d,
                "end_date": end_d,
                "requires_reg": str(ev.get("registration_required", "")).upper() in ("Y", "YES", "TRUE", "1"),
                "details": (ev.get("details") or "").strip()[:180],
                "url": f"https://ifpapinball.com{tid}"
            })

all_tournaments.sort(key=lambda x: x.get("start_date") or "9999-99-99")

out = {
    "last_checked": TODAY,
    "venues": [{"name": v["name"], "address": v["address"]} for v in VENUES],
    "tournaments": all_tournaments
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print(f"Saved {len(all_tournaments)} upcoming tournament(s) for {len(VENUES)} venue(s).")
