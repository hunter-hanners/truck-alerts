import os
import json
import re
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

# ── Configuration ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")
LOG_FILE  = os.path.join(BASE_DIR, "truck_log.txt")
FB_PROFILE = os.path.join(BASE_DIR, "fb_profile")

DISCORD_WEBHOOK = "********"

SEARCHES = [
    # TOYOTA TACOMA (2013-2015 sweet spot)
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2013&maxYear=2015",
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%20trd&minPrice=5000&maxPrice=20000&radius=200&minYear=2013&maxYear=2015",
    # TOYOTA TACOMA (2018-2021)
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2018&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%20trd&minPrice=5000&maxPrice=20000&radius=200&minYear=2018&maxYear=2021",
    # TOYOTA TUNDRA (2014-2021)
    "https://www.facebook.com/marketplace/gadsden/search?query=tundra%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=tundra%20crewmax&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2021",
    # NISSAN FRONTIER (2014-2019)
    "https://www.facebook.com/marketplace/gadsden/search?query=frontier%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2019",
    "https://www.facebook.com/marketplace/gadsden/search?query=frontier%20pro-4x&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2019",
    # TOYOTA 4RUNNER (2005-2021)
    "https://www.facebook.com/marketplace/gadsden/search?query=4runner%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2005&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=4runner%20trd&minPrice=5000&maxPrice=20000&radius=200&minYear=2005&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=4runner%20v8&minPrice=5000&maxPrice=20000&radius=200&minYear=2005&maxYear=2009",
    # LEXUS GX460 (2010-2019)
    "https://www.facebook.com/marketplace/gadsden/search?query=gx460&minPrice=5000&maxPrice=20000&radius=200&minYear=2010&maxYear=2019",
    "https://www.facebook.com/marketplace/gadsden/search?query=lexus%20gx%20460&minPrice=5000&maxPrice=20000&radius=200&minYear=2010&maxYear=2019",
    # LEXUS GX470 (2003-2009)
    "https://www.facebook.com/marketplace/gadsden/search?query=gx470&minPrice=5000&maxPrice=20000&radius=200&minYear=2003&maxYear=2009",
    "https://www.facebook.com/marketplace/gadsden/search?query=lexus%20gx470&minPrice=5000&maxPrice=20000&radius=200&minYear=2003&maxYear=2009",
    "https://www.facebook.com/marketplace/gadsden/search?query=lexus%20gx&minPrice=5000&maxPrice=20000&radius=200&minYear=2003&maxYear=2009",
]

SKIP_KEYWORDS = [
    "salvage", "rebuilt", "rebuildable", "wrecked", "parts only",
    "parts car", "damaged", "flood", "bumper", "grille", "headlight",
    "taillight", "mirror", "hood", "fender", "door panel",
    "2wd", "2 wheel drive", "rwd", "rear wheel drive",
    "250k", "275k", "300k", "325k", "350k",
    "transmission only", "engine only", "motor only",
    "dealer", "financing available", "buy here pay here",
    "manual", "6-speed manual", "5-speed manual", "stick shift"
]

BAD_PRICES = ["$1", "$9", "$99", "$100", "$123", "$321", "$999", "$1,000", "$1,234"]

VALID_KEYWORDS = [
    "tacoma", "tundra", "frontier",
    "toyota pickup", "trd off road", "trd sport", "trd pro",
    "4runner", "gx460", "gx470", "gx 460", "gx 470", "lexus gx"
]

# ── Helpers ─────────────────────────────────────────────────────
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def is_high_mileage(title):
    match = re.search(r'(\d{2,3})\s*k', title.lower())
    if match and int(match.group(1)) > 220:
        return True
    return False

def is_bad_listing(title):
    t = title.lower()
    if not any(w in t for w in VALID_KEYWORDS):
        return True
    if any(w in t for w in SKIP_KEYWORDS):
        return True
    if is_high_mileage(title):
        return True
    return False

def send_discord(title, price, location, url):
    timestamp = datetime.now().strftime("%m/%d/%Y at %I:%M %p")
    payload = {
        "embeds": [{
            "title": "🚨 New Truck Alert!",
            "description": f"**{title}**",
            "color": 3066993,
            "fields": [
                {"name": "💰 Price",    "value": price,     "inline": True},
                {"name": "📍 Location", "value": location,  "inline": True},
                {"name": "🕐 Found",    "value": timestamp, "inline": False}
            ],
            "url": url,
            "footer": {"text": "Hunter's Truck Alert System"}
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        log(f"✅ Alert sent: {title} — {price}")
    except Exception as e:
        log(f"Discord send failed: {e}")

def send_discord_warning(message):
    payload = {"content": f"⚠️ **Truck Alert System Warning:**\n{message}"}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    except Exception:
        pass

def parse_listings(html):
    listings = []
    seen_ids = set()
    block_pattern = r'{"id":"\d{10,}".*?"marketplace_listing_title":"[^"]+".*?}'
    for block in re.findall(block_pattern, html):
        try:
            id_m    = re.search(r'"id":"(\d{10,})"', block)
            title_m = re.search(r'"marketplace_listing_title":"([^"]+)"', block)
            price_m = re.search(r'"amount":"([^"]+)"', block)
            city_m  = re.search(r'"city":"([^"]+)"', block)
            if id_m and title_m:
                lid = id_m.group(1)
                if lid in seen_ids:
                    continue
                seen_ids.add(lid)
                listings.append({
                    "id":       lid,
                    "title":    title_m.group(1),
                    "price":    f"${price_m.group(1)}" if price_m else "See listing",
                    "location": city_m.group(1) if city_m else "Nearby",
                    "url":      f"https://www.facebook.com/marketplace/item/{lid}/"
                })
        except Exception:
            continue
    return listings

# ── Main ────────────────────────────────────────────────────────
def main():
    log("=== Truck alert run started ===")
    seen = load_seen()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            FB_PROFILE,
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        # ── Login check ────────────────────────────────────────
        log("Checking Facebook login status...")
        try:
            page.goto("https://www.facebook.com/marketplace/",
                      wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
        except Exception as e:
            log(f"Failed to load Facebook: {e}")
            send_discord_warning("Could not load Facebook. Check your internet connection.")
            context.close()
            return

        # If session expired, alert Discord and exit cleanly instead of hanging
        content = page.content()
        if "login" in page.url.lower() or "log in to facebook" in content.lower():
            log("⚠️ Facebook session expired. Manual re-login required.")
            send_discord_warning(
    "Your Facebook session expired. To fix:\n"
    "1. Open monitor.py and change headless=True to headless=False\n"
    "2. Run python3 ~/truck-alerts/monitor.py in Terminal\n"
    "3. Log into Facebook in the browser window that opens\n"
    "4. Change headless back to True\n"
    "Crontab will resume automatically after that."
)
            context.close()
            return

        log("✅ Facebook session active. Starting searches...")

        # ── Search loop ────────────────────────────────────────
        for search_url in SEARCHES:
            log("Checking search...")
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(random.uniform(5.0, 10.0))

                # Scroll down to trigger lazy-load
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(2)

                html = page.content()
            except Exception as e:
                log(f"Page load error: {e}")
                continue

            listings = parse_listings(html)
            log(f"Found {len(listings)} raw results")

            state_changed = False
            for listing in listings:
                if listing["id"] not in seen:
                    if is_bad_listing(listing["title"]):
                        log(f"Filtered: {listing['title']}")
                        seen.add(listing["id"])
                        state_changed = True
                        continue
                    if listing["price"] in BAD_PRICES:
                        log(f"Bad price filtered: {listing['price']}")
                        seen.add(listing["id"])
                        state_changed = True
                        continue
                    send_discord(
                        listing["title"],
                        listing["price"],
                        listing["location"],
                        listing["url"]
                    )
                    seen.add(listing["id"])
                    state_changed = True

            if state_changed:
                save_seen(seen)

        # Send heartbeat every 90 minutes
        now = datetime.now()
        minutes_since_midnight = now.hour * 60 + now.minute
        if minutes_since_midnight % 90 < 31:
            send_discord_warning("✅ Truck Alert System is running normally. No issues detected.")
        context.close()
    log("=== Run complete ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_discord_warning(f"Script crashed unexpectedly:\n`{e}`")
        except Exception:
            pass
        raise
