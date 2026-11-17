import json, re, os, urllib.request
from datetime import datetime
from bs4 import BeautifulSoup

DB_FILE = "updates.json"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
HEADERS = {"User-Agent": "Mozilla/5.0 (PinballCaddyBot/1.0)"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="ignore")

data = json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {"last_checked": "", "seen_keys": [], "code_releases": [], "rulesheet_updates": []}
seen = set(data.setdefault("seen_keys", []))
new_alerts = []

def add_code(key, game, mfg, ver, date_str, url, notes):
    k = key.lower().strip()
    if k in seen:
        return
    seen.add(k)
    data["code_releases"].insert(0, {
        "game": game, "mfg": mfg, "version": ver,
        "date": date_str or TODAY, "url": url, "notes": notes
    })
    new_alerts.append(f"⚡ **Code Release:** {game} `{ver}` ({mfg}) — {url}")

def add_rule(key, game, rtype, url):
    k = key.lower().strip()
    if k in seen:
        return
    seen.add(k)
    data["rulesheet_updates"].insert(0, {
        "game": game, "type": rtype, "date": TODAY, "url": url
    })
    new_alerts.append(f"📝 **Rulesheet {rtype}:** {game} — {url}")

# 1. Stern Pinball Game Code
try:
    soup = BeautifulSoup(fetch("https://sternpinball.com"), "html.parser")
    text = soup.get_text("\n", strip=True)
    for m in re.finditer(r"([A-Z0-9][A-Za-z0-9 :&'\-()]+?)\s+(v\d+\.\d+(?:\.\d+)?)", text):
        game, ver = m.group(1).strip(), m.group(2).strip()
        if 3 <= len(game) <= 55 and "code" not in game.lower():
            add_code(f"stern|{game}|{ver}", game, "Stern Pinball", ver, TODAY,
                     "https://sternpinball.com",
                     f"Official Stern Pinball code release {ver}. Visit the Stern Game Code Library link for full Read Me notes.")
            if len([a for a in new_alerts if "Stern Pinball" in a]) >= 5:
                break
except Exception as e:
    print("Stern check warning:", e)

# 2. Spooky Pinball
try:
    soup = BeautifulSoup(fetch("https://spookypinball.com"), "html.parser")
    for m in re.finditer(r"([A-Za-z0-9 :'\-]+?)\s+(v20\d{2}\.\d{2}\.\d{2})", soup.get_text(" ", strip=True)):
        game, ver = m.group(1).strip()[-40:], m.group(2).strip()
        add_code(f"spooky|{game}|{ver}", game, "Spooky Pinball", ver, TODAY,
                 "https://spookypinball.com",
                 f"Official Spooky Pinball software update {ver}. Check Spooky Game Support for full release notes.")
except Exception as e:
    print("Spooky check warning:", e)

# 3. Barrels of Fun
try:
    soup = BeautifulSoup(fetch("https://kollectfun.com"), "html.parser")
    for m in re.finditer(r"(Labyrinth|Dune|Winchester Mystery House|Bon Jovi)[^0-9]{0,25}(v?\d+\.\d+(?:\.\d+)?)", soup.get_text(" ", strip=True), re.I):
        game, ver = m.group(1).strip(), m.group(2).strip()
        if not ver.startswith("v"):
            ver = "v" + ver
        add_code(f"bof|{game}|{ver}", game, "Barrels of Fun", ver, TODAY,
                 "https://kollectfun.com",
                 f"Official Barrels of Fun software update {ver}.")
except Exception as e:
    print("Barrels of Fun check warning:", e)

# 4. Chicago Gaming Company
try:
    soup = BeautifulSoup(fetch("https://chicago-gaming.com"), "html.parser")
    for m in re.finditer(r"(Medieval Madness|Attack From Mars|Monster Bash|Cactus Canyon|Pulp Fiction)[^0-9]{0,30}(v?\d+\.\d+(?:\.\d+)?)", soup.get_text(" ", strip=True), re.I):
        game, ver = m.group(1).strip(), m.group(2).strip()
        if not ver.startswith("v"):
            ver = "v" + ver
        add_code(f"cgc|{game}|{ver}", game, "Chicago Gaming", ver, TODAY,
                 "https://chicago-gaming.com",
                 f"Official Chicago Gaming Company software update {ver}.")
except Exception as e:
    print("Chicago Gaming check warning:", e)

# 5. Tilt Forums Code Wiki (Catch-All Safety Net for JJP, Multimorphic, American, etc.)
try:
    tf = json.loads(fetch("https://tiltforums.com"))
    cooked = tf["post_stream"]["posts"][0]["cooked"]
    soup = BeautifulSoup(cooked, "html.parser")
    skip_brands = ("stern", "spooky", "barrels of fun", "chicago gaming")
    current_mfg = "Other Manufacturer"
    for el in soup.find_all(["h2", "h3", "li", "p", "tr"]):
        txt = el.get_text(" ", strip=True)
        if el.name in ("h2", "h3") and len(txt) < 45:
            current_mfg = txt
            continue
        if any(b in current_mfg.lower() for b in skip_brands):
            continue
        m = re.match(r"^([A-Za-z0-9 :&'\-()]+?)\s*[-–:]\s*(v?\d+\.\d+(?:\.\d+)?)", txt)
        if m:
            game, ver = m.group(1).strip(), m.group(2).strip()
            if not ver.startswith("v"):
                ver = "v" + ver
            if 3 <= len(game) <= 50:
                add_code(f"tf|{game}|{ver}", game, current_mfg, ver, TODAY,
                         "https://tiltforums.com",
                         f"Detected via Tilt Forums Code Wiki ({current_mfg}): {game} updated to {ver}.")
except Exception as e:
    print("Tilt Forums check warning:", e)

# 6. PinballRulesheets.com Master List
try:
    soup = BeautifulSoup(fetch("https://pinballrulesheets.com"), "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 3 or href.startswith("#"):
            continue
        full_url = href if href.startswith("http") else "https://pinballrulesheets.com" + ("" if href.startswith("/") else "/") + href
        if "pinballrulesheets.com" in full_url and "/master-list" not in full_url and "/contribute" not in full_url and "/other" not in full_url and full_url.rstrip("/") != "https://pinballrulesheets.com":
            add_rule(f"rule|{full_url}", title, "Added / Listed", full_url)
except Exception as e:
    print("PinballRulesheets check warning:", e)

data["last_checked"] = TODAY
data["seen_keys"] = sorted(seen)
with open(DB_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

if new_alerts:
    with open("alert.md", "w", encoding="utf-8") as f:
        f.write("## Pinball Code & Rulesheet Updates Found\n\n" + "\n".join(f"- {a}" for a in new_alerts))
    print(f"Found {len(new_alerts)} new update(s)!")
else:
    print("No new updates today.")
