#!/bin/bash
set -euo pipefail

# FreeJobAlert -> WordPress multi-category scraper + autopost
# Requires env secrets: WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD
# Put this script at scripts/run.sh and run in Ubuntu runner (GitHub Actions)

echo "---- FreeJobAlert Scraper Started ----"

# --- CONFIG ---
# base list of category pages to scrape (you can add more category URLs)
CATEGORIES=(
  "https://www.freejobalert.com/latest-notifications/"   # Latest (general)
  "https://www.freejobalert.com/bank-jobs/"
  "https://www.freejobalert.com/railway-jobs/"
  "https://www.freejobalert.com/police-jobs/"
  "https://www.freejobalert.com/ssc-jobs/"
  "https://www.freejobalert.com/defence-jobs/"
  # add more category listing pages if needed
)

MAX_PER_CATEGORY=${MAX_PER_CATEGORY:-10}   # max articles to process per category (env override)
SLEEP_BETWEEN_POSTS=${SLEEP_BETWEEN_POSTS:-3}
USER_AGENT="Mozilla/5.0 (compatible; RojgarBhaskarBot/1.0; +https://rojgarbhaskar.com)"

# required envs
: "${WP_SITE_URL:?Need WP_SITE_URL env (e.g. https://rojgarbhaskar.com)}"
: "${WP_USERNAME:?Need WP_USERNAME env}"
: "${WP_APP_PASSWORD:?Need WP_APP_PASSWORD env}"

echo "WP_SITE_URL: ${WP_SITE_URL}"
echo "MAX_PER_CATEGORY: ${MAX_PER_CATEGORY}"
echo "SLEEP_BETWEEN_POSTS: ${SLEEP_BETWEEN_POSTS}"

# install python deps if missing
if ! python3 -c "import bs4,requests" >/dev/null 2>&1; then
  echo "Installing python dependencies..."
  python3 -m pip install --user --upgrade pip >/dev/null
  python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null
fi

# --- Python scraper + poster ---
python3 - <<'PY'
import os, time, requests
from bs4 import BeautifulSoup

WP_SITE = os.environ.get("WP_SITE_URL").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME")
WP_PASS = os.environ.get("WP_APP_PASSWORD")
UA = os.environ.get("USER_AGENT", "Mozilla/5.0 (compatible; RojgarBhaskarBot/1.0)")
MAX_PER_CAT = int(os.environ.get("MAX_PER_CATEGORY", "10"))
SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))

CATEGORIES = [
  "https://www.freejobalert.com/latest-notifications/",
  "https://www.freejobalert.com/bank-jobs/",
  "https://www.freejobalert.com/railway-jobs/",
  "https://www.freejobalert.com/police-jobs/",
  "https://www.freejobalert.com/ssc-jobs/",
  "https://www.freejobalert.com/defence-jobs/",
]

session = requests.Session()
session.headers.update({"User-Agent": UA})

def fetch(url):
    print("Fetching:", url)
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def extract_article_links(list_html, base_url):
    soup = BeautifulSoup(list_html, "lxml")
    links = []
    # prefer "Get Details" anchors in table/list
    # common pattern: <a href="...">Get Details</a>
    for a in soup.find_all("a", href=True):
        txt = a.get_text(strip=True).lower()
        href = a['href']
        if "get details" in txt or "read more" in txt or "details" in txt:
            if href.startswith("http"):
                links.append(href)
            else:
                links.append(requests.compat.urljoin(base_url, href))
    # fallback: find anchors that point to freejobalert and look like article URLs (contain '-')
    if not links:
        for a in soup.find_all("a", href=True):
            href = a['href']
            if "freejobalert.com" in href and href.count("-") >= 2:
                links.append(href)
    # dedupe preserving order
    seen = set()
    uniq = []
    for u in links:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq

def parse_article(html):
    soup = BeautifulSoup(html, "lxml")
    # Title - common: an h1 or .entry-title or .post-title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        t = soup.select_one(".entry-title") or soup.select_one(".post-title")
        if t:
            title = t.get_text(strip=True)
    # Content: try article or .entry-content, else first big <div>
    content_el = soup.select_one(".entry-content") or soup.select_one(".post-content") or soup.select_one("article")
    if content_el:
        # remove script/style
        for s in content_el(["script","style","noscript"]):
            s.decompose()
        content_html = str(content_el)
    else:
        # fallback: collect paragraphs under the main container
        ps = soup.find_all("p")
        if ps:
            content_html = "\n".join("<p>%s</p>" % p.get_text(strip=True) for p in ps[:50])
        else:
            content_html = ""
    # if still empty, grab significant text
    if not title:
        title = soup.title.string.strip() if soup.title else "FreeJobAlert Item"
    return title, content_html

def wp_search_exists(title):
    url = f"{WP_SITE}/wp-json/wp/v2/posts"
    params = {"search": title, "per_page": 5}
    try:
        r = session.get(url, params=params, auth=(WP_USER, WP_PASS), timeout=20)
        if r.status_code == 200:
            posts = r.json()
            for p in posts:
                if p.get("title",{}).get("rendered","").strip().lower() == title.strip().lower():
                    return True
    except Exception as e:
        print("WP search error:", e)
    return False

def wp_create_post(title, content, categories=None):
    url = f"{WP_SITE}/wp-json/wp/v2/posts"
    body = {"title": title, "content": content, "status": "publish"}
    if categories:
        body["categories"] = categories
    try:
        r = session.post(url, json=body, auth=(WP_USER, WP_PASS), timeout=30)
        if r.status_code in (200,201):
            return r.json()
        else:
            print("WP create error:", r.status_code, r.text)
            return None
    except Exception as e:
        print("WP create exception:", e)
        return None

def safe_text(s):
    return (s or "").strip()

def process_category(url):
    try:
        html = fetch(url)
    except Exception as e:
        print("Failed fetch category:", e)
        return 0
    links = extract_article_links(html, url)
    if not links:
        print("No article links found on", url)
        return 0
    print("Found", len(links), "links, will process up to", MAX_PER_CAT)
    done = 0
    for link in links[:MAX_PER_CAT]:
        try:
            art_html = fetch(link)
            title, content_html = parse_article(art_html)
            title = safe_text(title)
            if not title:
                print("Skipping link (no title):", link)
                continue
            print("Checking:", title)
            if wp_search_exists(title):
                print("   already posted, skipping.")
                continue
            # build content with link reference
            body = f"<p>{title}</p>\n{content_html}\n<p>Official Link: <a href=\"{link}\">{link}</a></p>\n<p>Source: FreeJobAlert</p>"
            res = wp_create_post(title, body)
            if res:
                print("   POSTED:", res.get("link"))
                done += 1
            else:
                print("   Post failed for", title)
            time.sleep(SLEEP)
        except Exception as e:
            print("   Exception while processing", link, e)
    return done

def main():
    total = 0
    for cat in CATEGORIES:
        print("\n--- Category:", cat)
        try:
            n = process_category(cat)
            total += n
        except Exception as e:
            print("Category processing exception:", e)
    print("Done. Total new posts:", total)

if __name__ == "__main__":
    main()

PY

echo "---- Script finished ----"
