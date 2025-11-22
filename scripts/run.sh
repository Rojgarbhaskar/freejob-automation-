#!/bin/bash
set -euo pipefail

echo "---- FreeJobAlert Scraper Started ----"

# Check required secrets
: "${WP_SITE_URL:?Missing}"
: "${WP_USERNAME:?Missing}"
: "${WP_APP_PASSWORD:?Missing}"

# Install Python dependencies
python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null

# Run Python scraper
python3 - << 'PY'
import os, requests, time
from bs4 import BeautifulSoup

WP = os.environ["WP_SITE_URL"].rstrip("/")
USER = os.environ["WP_USERNAME"]
PASS = os.environ["WP_APP_PASSWORD"]

SOURCE = "https://www.freejobalert.com/latest-notifications/"

def fetch(url):
    print("Fetching FreeJobAlert...")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    return r.text

def parse(html):
    soup = BeautifulSoup(html, "lxml")
    items = []
    for h in soup.find_all(["h2","h3"], limit=40):
        a = h.find("a")
        if a and a.get("href"):
            items.append({
                "title": a.get_text(strip=True),
                "link": a.get("href")
            })
    return items[:10]

def already_exists(title):
    url = f"{WP}/wp-json/wp/v2/posts"
    r = requests.get(url, params={"search": title}, auth=(USER,PASS))
    if r.status_code == 200:
        for p in r.json():
            if p["title"]["rendered"].strip().lower() == title.strip().lower():
                return True
    return False

def post_to_wp(title, link):
    data = {
        "title": title,
        "content": f"{title}<br><br>Official Link: <a href='{link}'>{link}</a><br><br>Source: FreeJobAlert",
        "status": "publish"
    }
    url = f"{WP}/wp-json/wp/v2/posts"
    r = requests.post(url, json=data, auth=(USER,PASS))
    return r.status_code in (200,201)

def main():
    html = fetch(SOURCE)
    items = parse(html)
    print(f"Found {len(items)} items")
    posted = 0

    for it in items:
        title = it["title"]
        link = it["link"]
        print("Checking:", title)

        if already_exists(title):
            print("Already posted")
            continue

        ok = post_to_wp(title, link)
        print("POSTED:", title) if ok else print("FAILED")
        time.sleep(3)
        posted += 1

    print("Total new posts:", posted)

main()
PY

echo "---- Script Finished ----"
