#!/bin/bash
set -euo pipefail

echo "Starting FreeJobAlert → WordPress Auto Scraper..."

# Required GitHub Secrets:
# WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD

# Python dependencies install
if ! python3 -c "import bs4,requests" >/dev/null 2>&1; then
    echo "Installing dependencies..."
    python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null
fi

# Run Python scraper
python3 << 'PY'

import requests
from bs4 import BeautifulSoup
import base64
import os
import time

WP_USER = os.environ.get("WP_USERNAME")
WP_PASS = os.environ.get("WP_APP_PASSWORD")
WP_SITE = os.environ.get("WP_SITE_URL").rstrip("/")

auth = (WP_USER, WP_PASS)

# FreeJobAlert categories
URLS = {
    "Latest Jobs": "https://www.freejobalert.com/latest-notification/",
    "Admit Cards": "https://www.freejobalert.com/admit-card/",
    "Results": "https://www.freejobalert.com/results/"
}

def wp_post_exists(title):
    try:
        url = f"{WP_SITE}/wp-json/wp/v2/posts"
        r = requests.get(url, params={"search": title}, auth=auth, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for p in data:
                if p["title"]["rendered"].strip().lower() == title.lower().strip():
                    return True
        return False
    except Exception as e:
        print("WP Search Error:", e)
        return False

def wp_create(title, content):
    try:
        url = f"{WP_SITE}/wp-json/wp/v2/posts"
        payload = {
            "title": title,
            "content": content,
            "status": "publish"
        }
        r = requests.post(url, json=payload, auth=auth, timeout=20)
        if r.status_code in (200, 201):
            return r.json()
        else:
            print("WP Create Error:", r.status_code, r.text)
            return None
    except Exception as e:
        print("WP Create Exception:", e)
        return None

def scrape(url):
    print(f"Scraping: {url}")
    try:
        r = requests.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")

        items = []
        for a in soup.select("ul li a"):
            title = a.get_text(strip=True)
            link = a.get("href")
            if title and link and link.startswith("http"):
                items.append({"title": title, "link": link})
        return items[:20]  # limit to 20 items
    except Exception as e:
        print("Scrape Failed:", e)
        return []

def main():

    print("\n============== AUTO SCRAPER ==============\n")

    posted = 0

    for name, url in URLS.items():
        print(f"\n===== {name} =====")

        items = scrape(url)

        for item in items:
            title = item["title"]
            link = item["link"]

            if wp_post_exists(title):
                print("Already Posted:", title)
                continue

            body = f"{title}\n\nOfficial Link: <a href=\"{link}\">{link}</a>\n\nSource: FreeJobAlert"

            res = wp_create(title, body)
            if res:
                print("✔ Posted:", res.get("link"))
                posted += 1
            else:
                print("✘ Failed to post:", title)

            time.sleep(3)

    print(f"\nDone. Posted {posted} new posts.\n")

if __name__ == "__main__":
    main()

PY

echo "Script finished."
