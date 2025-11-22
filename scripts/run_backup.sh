#!/bin/bash
set -euo pipefail

echo "Starting MULTI-WEBSITE ADVANCED scraper -> WordPress autopost..."

: "${WP_SITE_URL:?Missing}"
: "${WP_USERNAME:?Missing}"
: "${WP_APP_PASSWORD:?Missing}"

python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null 2>&1 || true

python3 - << 'PY'
import os, requests, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

WP = os.environ["WP_SITE_URL"].rstrip("/")
USER = os.environ["WP_USERNAME"]
PASS = os.environ["WP_APP_PASSWORD"]

HEADERS = {"User-Agent": "Mozilla/5.0 (RojgarBhaskarBot)"}

SITES = {
    "sarkariresult_cm": "https://sarkariresult.com.cm/",
    "sarkariresult_im": "https://sarkariresult.com.im/",
    "testbook": "https://testbook.com/",
    "freejobalert": "https://www.freejobalert.com/latest-notifications/"
}

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except:
        return ""

def extract_basic_links(html, base):
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        link = urljoin(base, a["href"])
        if len(title) < 5: continue
        if not link.startswith("http"): continue
        if "javascript:" in link: continue
        links.append({"title": title, "link": link, "source": base})
    return links[:20]

def extract_structured_fields(html, url):
    soup = BeautifulSoup(html, "lxml")

    # Overview
    overview_block = soup.find("article") or soup.find("div", class_="content")
    overview_html = str(overview_block) if overview_block else ""

    # Important Dates (pattern based)
    imp = soup.find_all("table")
    important_dates_html = ""
    vacancy_html = ""
    fee_html = ""
    age_html = ""
    sel_html = ""
    how_html = ""

    if imp:
        important_dates_html = str(imp[0])
        if len(imp) > 1: vacancy_html = str(imp[1])
        if len(imp) > 2: fee_html = str(imp[2])
        if len(imp) > 3: age_html = str(imp[3])
        if len(imp) > 4: sel_html = str(imp[4])

    # How to apply (fallback paragraphs)
    paras = soup.find_all("p")
    how_html = "".join(str(p) for p in paras[-3:]) if paras else ""

    # Important links
    apply_online = ""
    download_notification = ""
    official_website = ""
    admit_card_link = ""

    for a in soup.find_all("a", href=True):
        t = a.get_text(strip=True).lower()
        href = a["href"]

        if "apply" in t:
            apply_online = href
        if "notification" in t:
            download_notification = href
        if "official" in t or "website" in t:
            official_website = href
        if "admit" in t:
            admit_card_link = href

    return {
        "overview_html": overview_html,
        "important_dates_html": important_dates_html,
        "vacancy_html": vacancy_html,
        "application_fee_html": fee_html,
        "age_limit_html": age_html,
        "selection_process_html": sel_html,
        "how_to_apply_html": how_html,
        "apply_online": apply_online,
        "download_notification": download_notification,
        "official_website": official_website,
        "admit_card_link": admit_card_link,
        "source_url": url
    }

def wp_post(title, fields):
    url = f"{WP}/wp-json/wp/v2/posts"
    body = {
        "title": title,
        "status": "publish",
        "meta": fields
    }
    try:
        r = requests.post(url, json=body, auth=(USER, PASS), timeout=20)
        print("WP:", r.status_code)
        if r.status_code in (200,201):
            print("POSTED:", r.json().get("link"))
            return True
    except Exception as e:
        print("WP Error:", e)
    return False

# SCRAPING
all_items = []
for name, url in SITES.items():
    html = fetch(url)
    items = extract_basic_links(html, url)
    all_items.extend(items)

if not all_items:
    print("NO DATA FOUND")
    exit()

latest = all_items[0]
print("LATEST:", latest["title"], latest["link"])

# FETCH FULL POST
html = fetch(latest["link"])
fields = extract_structured_fields(html, latest["link"])

wp_post(latest["title"], fields)

PY

echo "Script Completed."
