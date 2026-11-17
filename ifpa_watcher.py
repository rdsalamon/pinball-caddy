import json, re
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT_FILE = "tournaments.json"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

VENUES = [
    {
        "name": "Morristown Game Vault",
        "address": "22 South St, Morristown, NJ 07960",
        "search_loc": "Morristown, NJ 07960",
        "match_terms": ["morristown game vault", "22 south"]
    }
]

all_tournaments = []
seen_ids = set()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900}
    )
    page = context.new_page()

    captured_json = []
    def handle_resp(resp):
        try:
            if "ifpapinball.com" in resp.url and resp.status == 200:
                ct = resp.headers.get("content-type", "")
                if "json" in ct or "calendar" in resp.url or "tournament" in resp.url:
                    txt = resp.text()
                    if txt.strip().startswith(("{", "[")):
                        captured_json.append((resp.url, json.loads(txt)))
        except Exception:
            pass

    page.on("response", handle_resp)

    for v in VENUES:
        page.goto("https://ifpapinball.com", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        by_loc = page.locator("text=By Location").first
        if by_loc.count() > 0:
            by_loc.click()
            page.wait_for_timeout(1000)

        vis_inputs = page.locator("input:visible")
        print(f"Visible inputs: {vis_inputs.count()}")
        if vis_inputs.count() > 0:
            inp = vis_inputs.first
            inp.click()
            inp.fill(v["search_loc"])
            page.wait_for_timeout(1500)
            inp.press("ArrowDown")
            inp.press("Enter")
            page.wait_for_timeout(1000)

        for sel in ["button:visible:has-text('Search')", "input:visible[type='submit']", "input:visible[value*='Search']", "a:visible:has-text('Search')"]:
            btn = page.locator(sel).last
            if btn.count() > 0:
                btn.click()
                print(f"Clicked search via: {sel}")
                break

        page.wait_for_timeout(5000)
        print(f"Captured {len(captured_json)} JSON responses from IFPA")

        for u, payload in captured_json:
            events = payload if isinstance(payload, list) else (payload.get("calendar") or payload.get("tournaments") or payload.get("tournament") or payload.get("results") or [])
            if isinstance(events, list):
                print(f"JSON from {u} has {len(events)} items")
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    tid = str(ev.get("tournament_id") or ev.get("id") or "")
                    if not tid or tid in seen_ids:
                        continue
                    blob = json.dumps(ev).lower()
                    if any(term in blob for term in v["match_terms"]):
                        seen_ids.add(tid)
                        start_d = str(ev.get("event_start_date") or ev.get("start_date") or "")[:10]
                        end_d = str(ev.get("event_end_date") or ev.get("end_date") or start_d)[:10]
                        all_tournaments.append({
                            "tournament_id": tid,
                            "venue_id": v["name"],
                            "name": ev.get("tournament_name") or ev.get("name") or "IFPA Tournament",
                            "start_date": start_d,
                            "end_date": end_d,
                            "requires_reg": str(ev.get("registration_required", "")).upper() in ("Y", "YES", "TRUE", "1"),
                            "details": str(ev.get("details") or ev.get("address1") or "").strip()[:180],
                            "url": f"https://ifpapinball.com{tid}"
                        })

        body_txt = page.locator("body").inner_text()
        print("Page text snippet:", repr(" ".join(body_txt.split())[:300]))

    browser.close()

all_tournaments.sort(key=lambda x: x.get("start_date") or "9999-99-99")

out = {
    "last_checked": TODAY,
    "venues": [{"name": v["name"], "address": v["address"]} for v in VENUES],
    "tournaments": all_tournaments
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print(f"Saved {len(all_tournaments)} upcoming tournament(s) for {len(VENUES)} venue(s).")
