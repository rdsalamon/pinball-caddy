import json, re
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT_FILE = "tournaments.json"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

VENUES = [
    {
        "name": "Morristown Game Vault",
        "address": "22 South St, Morristown, NJ 07960",
        "search_loc": "07960",
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

    for v in VENUES:
        page.goto("https://ifpapinball.com", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(2000)

        loc_inputs = page.locator("input[type='text']")
        count = loc_inputs.count()
        print(f"Found {count} text inputs on IFPA calendar page")
        for i in range(count):
            ph = (loc_inputs.nth(i).get_attribute("placeholder") or "").lower()
            nm = (loc_inputs.nth(i).get_attribute("name") or "").lower()
            id_attr = (loc_inputs.nth(i).get_attribute("id") or "").lower()
            if any(k in (ph + nm + id_attr) for k in ("loc", "addr", "city", "zip", "where")) or i == count - 1:
                loc_inputs.nth(i).fill(v["search_loc"])
                break

        search_btns = page.locator("button:has-text('Search'), input[value*='Search']")
        if search_btns.count() > 0:
            search_btns.last.click()
        page.wait_for_timeout(4000)

        links = page.locator("a[href*='tournaments/view.php']")
        lcount = links.count()
        print(f"Found {lcount} IFPA tournament links near {v['search_loc']}")

        for i in range(lcount):
            a = links.nth(i)
            href = a.get_attribute("href") or ""
            m_id = re.search(r"t=(\d+)", href)
            tid = m_id.group(1) if m_id else href
            if not tid or tid in seen_ids:
                continue

            row_text = a.evaluate("el => (el.closest('tr, .event, .tournament, li, div') || el.parentElement).innerText")
            clean_row = " ".join(row_text.split())
            if any(term in clean_row.lower() for term in v["match_terms"]):
                seen_ids.add(tid)
                t_name = a.inner_text().strip() or "IFPA Tournament"
                dates = re.findall(r"\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4}", clean_row)
                start_d = dates if dates else TODAY
                end_d = dates[-1] if len(dates) > 1 else start_d
                full_url = href if href.startswith("http") else "https://ifpapinball.com" + ("" if href.startswith("/") else "/") + href
                all_tournaments.append({
                    "tournament_id": tid,
                    "venue_id": v["name"],
                    "name": t_name,
                    "start_date": start_d,
                    "end_date": end_d,
                    "requires_reg": "registration" in clean_row.lower() or "pre-reg" in clean_row.lower(),
                    "details": clean_row[:180],
                    "url": full_url
                })

    browser.close()

out = {
    "last_checked": TODAY,
    "venues": [{"name": v["name"], "address": v["address"]} for v in VENUES],
    "tournaments": all_tournaments
}

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print(f"Saved {len(all_tournaments)} upcoming tournament(s) for {len(VENUES)} venue(s).")
