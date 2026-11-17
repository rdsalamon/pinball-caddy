import json, os, urllib.request, urllib.parse
from datetime import datetime

API_KEY = os.environ.get("IFPA_API_KEY", "").strip()
OUT_FILE = "tournaments.json"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

VENUES = [
    {
        "name": "Morristown Game Vault",
        "address": "22 South St, Morristown, NJ 07960",
        "zip": "07960",
        "state": "NJ",
        "match_terms": ["morristown game vault", "22 south"]
    }
]

if not API_KEY:
    raise RuntimeError("IFPA_API_KEY secret is missing.")

all_tournaments = []
seen_ids = set()

for v in VENUES:
    endpoints = [
        f"https://ifpapinball.com?{urllib.parse.urlencode({'api_key': API_KEY, 'address': v['zip'], 'distance': 10, 'units': 'm'})}",
        f"https://ifpapinball.com?{urllib.parse.urlencode({'api_key': API_KEY, 'country': 'US', 'stateprov': v['state']})}"
    ]
    events = []
    for url in endpoints:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (PinballCaddyBot/1.0)",
            "Accept": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read().decode("utf-8", errors="ignore").strip()
                print(f"Tried {url.split('?')[0]} -> HTTP {r.status}, bytes={len(raw)}, starts={repr(raw[:60])}")
                if raw.startswith("{") or raw.startswith("["):
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        events = payload.get("calendar") or payload.get("tournaments") or payload.get("tournament") or payload.get("search") or []
                    elif isinstance(payload, list):
                        events = payload
                    if events:
                        break
        except Exception as e:
            print(f"Endpoint error ({url.split('?')[0]}):", e)

    print(f"Parsed {len(events)} total events for {v['name']}")

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
            if end_d and end_d < TODAY:
                continue
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
