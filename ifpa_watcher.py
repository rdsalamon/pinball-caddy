import json, re, urllib.request
from datetime import datetime

OUT_FILE = "tournaments.json"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

VENUES = [
    {
        "name": "Morristown Game Vault",
        "address": "22 South St, Morristown, NJ 07960",
        "feed_url": "https://ifpapinball.com",
        "match_terms": ["morristown game vault", "22 south"]
    }
]

def unfold_ics(text):
    return re.sub(r"\r?\n[ \t]", "", text)

def parse_ics_date(val):
    m = re.search(r"(\d{4})(\d{2})(\d{2})", val or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""

all_tournaments = []
seen_ids = set()

for v in VENUES:
    req = urllib.request.Request(v["feed_url"], headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/calendar,text/plain,*/*"
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read().decode("utf-8", errors="ignore")
        print(f"Feed {v['name']}: HTTP {r.status}, bytes={len(raw)}, has_vcal={'BEGIN:VCALENDAR' in raw}")

    if "BEGIN:VCALENDAR" not in raw:
        print("Warning: Feed did not return VCALENDAR. Preview:", repr(raw[:150]))
        continue

    raw_ics = unfold_ics(raw)
    blocks = raw_ics.split("BEGIN:VEVENT")[1:]
    print(f"Total VEVENTs in feed for {v['name']}: {len(blocks)}")

    for blk in blocks:
        ev_text = blk.split("END:VEVENT")[0]
        fields = {}
        for line in ev_text.splitlines():
            if ":" in line:
                k, val = line.split(":", 1)
                fields[k.split(";")[0].strip().upper()] = val.replace("\\n", " ").replace("\\,", ",").strip()

        summary = fields.get("SUMMARY", "")
        location = fields.get("LOCATION", "")
        desc = fields.get("DESCRIPTION", "")
        ev_url = fields.get("URL", "")
        uid = fields.get("UID", summary + fields.get("DTSTART", ""))

        blob = f"{summary} {location} {desc}".lower()
        if any(term in blob for term in v["match_terms"]):
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            start_d = parse_ics_date(fields.get("DTSTART", ""))
            end_d = parse_ics_date(fields.get("DTEND", "")) or start_d
            if end_d and end_d < TODAY:
                continue
            all_tournaments.append({
                "tournament_id": uid,
                "venue_id": v["name"],
                "name": summary or "IFPA Tournament",
                "start_date": start_d,
                "end_date": end_d,
                "requires_reg": "prereg" in blob or "pre-reg" in blob or "registration required" in blob,
                "details": (location or desc)[:180],
                "url": ev_url if ev_url.startswith("http") else "https://ifpapinball.com"
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
