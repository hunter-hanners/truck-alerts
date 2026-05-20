import requests
import json
import os
import re
import time
import random
from datetime import datetime

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

SEARCHES = [
    # TOYOTA TACOMA (2013-2015 sweet spot)
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2013&maxYear=2015",
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%20trd&minPrice=5000&maxPrice=20000&radius=200&minYear=2013&maxYear=2015",
    # TOYOTA TACOMA (2018-2021 best 3rd gen)
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2018&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=tacoma%20trd&minPrice=5000&maxPrice=20000&radius=200&minYear=2018&maxYear=2021",
    # TOYOTA TUNDRA (2014-2021 reliable years)
    "https://www.facebook.com/marketplace/gadsden/search?query=tundra%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2021",
    "https://www.facebook.com/marketplace/gadsden/search?query=tundra%20crewmax&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2021",
    # NISSAN FRONTIER (2014-2019 safe years only)
    "https://www.facebook.com/marketplace/gadsden/search?query=frontier%204x4&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2019",
    "https://www.facebook.com/marketplace/gadsden/search?query=frontier%20pro-4x&minPrice=5000&maxPrice=20000&radius=200&minYear=2014&maxYear=2019",
]

SEEN_FILE = "seen.json"
LOG_FILE = "truck_log.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

SKIP_KEYWORDS = [
    "salvage", "rebuilt", "rebuildable", "wrecked", "parts only",
    "parts car", "damaged", "flood", "bumper", "grille", "headlight",
    "taillight", "mirror", "hood", "fender", "door panel",
    "2wd", "2 wheel drive", "rwd", "rear wheel drive",
    "250k", "275k", "300k", "325k", "350k",
    "transmission only", "engine only", "motor only",
    "dealer", "financing available", "buy here pay here",
    "bhph", "no credit", "bad credit"
]

BAD_PRICES = ["$1", "$9", "$99", "$100", "$123", "$321", "$999", "$1,000", "$1,234"]

VALID_KEYWORDS = [
    "tacoma", "tundra", "frontier",
    "toyota pickup", "trd off road", "trd sport", "trd pro"
]

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
    # Catches: 230k, 230k miles, 230k mi, 230 k miles
    mileage_match = re.search(r'(\d{2,3})\s*k', title.lower())
    if mileage_match:
        mileage = int(mileage_match.group(1))
        if mileage > 220:
            return True
    return False

def is_bad_price(price):
    return price in BAD_PRICES

def is_bad_listing(title):
    title_lower = title.lower()
    if not any(word in title_lower for word in VALID_KEYWORDS):
        return True
    if any(word in title_lower for word in SKIP_KEYWORDS):
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
                {"name": "💰 Price", "value": price, "inline": True},
                {"name": "📍 Location", "value": location, "inline": True},
                {"name": "🕐 Found", "value": timestamp, "inline": False}
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

def check_marketplace(url):
    try:
        time.sleep(random.uniform(8.0, 15.0))
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            return resp.text
        else:
            log(f"Status {resp.status_code} received")
            return ""
    except Exception as e:
        log(f"Fetch error: {e}")
        return ""

def parse_listings(html):
    listings = []
    seen_ids = set()

    # Block isolation — parse each listing chunk independently
    # so a missing field in one listing doesn't corrupt the others
    block_pattern = r'{"id":"\d{10,}".*?"marketplace_listing_title":"[^"]+".*?}'
    blocks = re.findall(block_pattern, html)

    for block in blocks:
        try:
            id_match = re.search(r'"id":"(\d{10,})"', block)
            title_match = re.search(r'"marketplace_listing_title":"([^"]+)"', block)
            price_match = re.search(r'"amount":"([^"]+)"', block)
            city_match = re.search(r'"city":"([^"]+)"', block)

            if id_match and title_match:
                listing_id = id_match.group(1)
                if listing_id in seen_ids:
                    continue
                seen_ids.add(listing_id)

                title = title_match.group(1)
                price = f"${price_match.group(1)}" if price_match else "See listing"
                city = city_match.group(1) if city_match else "Nearby"

                listings.append({
                    "id": listing_id,
                    "title": title,
                    "price": price,
                    "location": city,
                    "url": f"https://www.facebook.com/marketplace/item/{listing_id}/"
                })
        except Exception:
            continue

    return listings

def main():
    log("=== Truck alert run started ===")
    seen = load_seen()

    for search_url in SEARCHES:
        log(f"Checking search...")
        html = check_marketplace(search_url)
        if not html:
            log("Empty response, skipping.")
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
                if is_bad_price(listing["price"]):
                    log(f"Bad price filtered: {listing['price']} — {listing['title']}")
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

    log("=== Run complete ===")

if __name__ == "__main__":
    main()
