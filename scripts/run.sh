#!/bin/bash
set -euo pipefail

# Simple scraper -> WordPress auto-post script
# Requires environment variables (set as GitHub Secrets):
# WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD
# Run on Ubuntu GitHub Actions runner. Uses python3 + pip to run BeautifulSoup.

echo "Starting FreeJobAlert -> WP scraper..."

# --- config ---
SOURCE_URL="https://www.freejobalert.com/latest-notifications/"
# How many items to check (most recent)
MAX_ITEMS=10
# Wait seconds between WP requests (be polite)
SLEEP_BETWEEN_POSTS=3
# ----------------

# check envs
: "${WP_SITE_URL:?Need WP_SITE_URL env (e.g. https://rojgarbhaskar.com)}"
: "${WP_USERNAME:?Need WP_USERNAME env}"
: "${WP_APP_PASSWORD:?Need WP_APP_PASSWORD env}"

# install python deps if not present
if ! python3 -c "import bs4,requests" >/dev/null 2>&1; then
  echo "Installing python dependencies..."
  python3 -m pip install --user --upgrade pip >/dev/null
  python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null
fi

# Use Python to scrape & post (keeps parsing robust)
python3 - <<'PY'
import os,sys,requests, time
from bs4 import BeautifulSoup

WP_SITE = os.environ.get("WP_SITE_URL").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME")
WP_PASS = os.environ.get("WP_APP_PASSWORD")

SRC = "https://www.freejobalert.com/latest-notifications/"

def fetch_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RojgarBhaskarBot/1.0; +https://rojgarbhaskar.com)"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def parse_items(html):
    soup = BeautifulSoup(html, "lxml")
    items = []
    # Strategy: look for article titles / h3 links used by site theme
    # fallback: collect first few <a> tags that point to freejobalert.com
    # Primary: h3 tags (common in theme)
    for h in soup.find_all(["h3","h2"], limit=40):
        a = h.find("a")
        if a and a.get("href") and "freejobalert.com" in a.get("href"):
            title = a.get_text(strip=True)
            link = a.get("href").strip()
            if title and link:
                items.append({"title": title, "link": link})
    # If not enough items, fallback to anchor scan
    if len(items) < 5:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "freejobalert.com" in href and href.startswith("http"):
                title = a.get_text(strip=True) or href
                items.append({"title": title, "link": href})
    # dedupe preserving order
    seen = set()
    uniq = []
    for it in items:
        key = (it["title"], it["link"])
        if key not in seen:
            uniq.append(it)
            seen.add(key)
    return uniq

def wp_has_post(title):
    # Use WP REST API search param to check if similar title exists
    url = f"{WP_SITE}/wp-json/wp/v2/posts"
    params = {"search": title, "per_page": 5}
    r = requests.get(url, params=params, auth=(WP_USER, WP_PASS), timeout=20)
    if r.status_code == 200:
        posts = r.json()
        for p in posts:
            if p.get("title",{}).get("rendered","").strip().lower() == title.strip().lower():
                return True
    else:
        print("Warning: WP search returned", r.status_code, r.text)
    return False

def wp_create_post(title, content, categories=None):
    url = f"{WP_SITE}/wp-json/wp/v2/posts"
    body = {"title": title, "content": content, "status": "publish"}
    if categories:
        body["categories"] = categories
    r = requests.post(url, json=body, auth=(WP_USER, WP_PASS), timeout=30)
    if r.status_code in (200,201):
        return r.json()
    else:
        print("Error creating post:", r.status_code, r.text)
        return None

def main():
    html = fetch_page(SRC)
    items = parse_items(html)
    max_items = int(os.environ.get("MAX_ITEMS", "10"))
    items = items[:max_items]
    print(f"Found {len(items)} candidate items.")
    posted = 0
    for it in items:
        title = it["title"]
        link = it["link"]
        print("-> Checking:", title)
        try:
            if wp_has_post(title):
                print("   already posted, skipping.")
                continue
            # Prepare content: short excerpt + official link
            content = f"{title}\n\nOfficial Link: <a href=\"{link}\">{link}</a>\n\nSource: FreeJobAlert"
            res = wp_create_post(title, content)
            if res:
                print("   Posted:", res.get("link"))
                posted += 1
            else:
                print("   Post failed.")
            time.sleep(int(os.environ.get("SLEEP_BETWEEN_POSTS", "3")))
        except Exception as e:
            print("   Exception:", e)
    print(f"Done. Posted {posted} new items.")

if __name__ == "__main__":
    main()

PY

echo "Script finished."
