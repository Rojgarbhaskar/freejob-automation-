#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-site job scraper -> WordPress autopost (final updated)
Supports:
 - sarkariresult.com.cm
 - sarkariresult.com.im
 - freejobalert.com (latest-notifications)
 - services.india.gov.in (listing)
Behavior:
 - Collect items from multiple sites
 - For each item fetch detail page and build SarkariResult-style content
 - Detect "Admit Card" / "Hall Ticket" / "Admit" links if present and add section
 - Post to WP via REST API using Application Password
 - Avoid duplicates using WP REST search
Environment variables (required):
 - WP_SITE_URL (e.g. https://rojgarbhaskar.com)
 - WP_USERNAME
 - WP_APP_PASSWORD
 - MAX_ITEMS (optional, default 10)
 - SLEEP_BETWEEN_POSTS (optional, default 3)
"""

import os
import time
import re
import requests
from bs4 import BeautifulSoup

# ---- Config ----
USER_AGENT = "Mozilla/5.0 (compatible; RojgarBhaskarBot/1.0; +https://rojgarbhaskar.com)"
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 20

# ---- WordPress helpers ----
def wp_search_exists(site, user, app_pass, title):
    """Search WP posts for exact title (to avoid duplicates)"""
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        params = {"search": title, "per_page": 5}
        r = requests.get(url, params=params, auth=(user, app_pass), timeout=TIMEOUT, headers=HEADERS)
        if r.status_code == 200:
            posts = r.json()
            for p in posts:
                t = p.get("title", {}).get("rendered", "")
                if t.strip().lower() == title.strip().lower():
                    return True
        else:
            print("WP search warning:", r.status_code, r.text)
    except Exception as e:
        print("WP search error:", e)
    return False

def wp_create_post(site, user, app_pass, title, content, status="publish", categories=None):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        body = {"title": title, "content": content, "status": status}
        if categories:
            body["categories"] = categories
        r = requests.post(url, json=body, auth=(user, app_pass), timeout=30, headers=HEADERS)
        if r.status_code in (200, 201):
            return r.json()
        else:
            print("WP create error:", r.status_code, r.text)
    except Exception as e:
        print("WP create exception:", e)
    return None

# ---- utility scraping helpers ----
def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Fetch error:", url, e)
        return ""

def clean_text(t):
    if not t:
        return ""
    return re.sub(r"\s+", " ", t).strip()

def detect_admit_links(soup, base_url):
    """Find common admit/hall-ticket links and return list"""
    admit = []
    # search for anchor text keywords
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True).lower()
        if any(k in txt for k in ["admit", "hall ticket", "hallticket", "call letter", "download admit", "download hall"]):
            href = a["href"]
            if href.startswith("/"):
                href = base_url.rstrip("/") + href
            admit.append((clean_text(a.get_text()), href))
    # also search for strong headings that mention admit card and then nearest link
    return admit

# ---- site specific scrapers ----

def scrape_sarkariresult_generic(base_url):
    """Scrape list & detail from sarkariresult domains (both .cm and .im)
       Strategy: find candidate anchors in main content with job titles, then fetch detail.
    """
    html = fetch(base_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")

    candidates = []
    # Try common patterns
    # 1) anchors inside tables / lists
    for sel in ["div.entry-content a", "div.content a", "table a", "ul a", "div#content a"]:
        for a in soup.select(sel):
            href = a.get("href")
            title = clean_text(a.get_text())
            if not href or not title:
                continue
            # only external / internal job-like links
            if href.startswith("#") or title.lower() in ("read more","more details","click here"):
                continue
            if href.startswith("/"):
                href = base_url.rstrip("/") + href.lstrip("/")
            # only site links
            if base_url.split("//")[-1] in href:
                candidates.append((title, href))
        if candidates:
            break

    # dedupe preserving order
    seen = set()
    uniq = []
    for t,l in candidates:
        k = (t.strip().lower(), l)
        if k not in seen:
            uniq.append((t,l))
            seen.add(k)
    return uniq[:10]

def scrape_freejobalert():
    url = "https://www.freejobalert.com/latest-notifications/"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items = []
    # Common pattern: article lists with anchors: h3 a, .blog-list a etc.
    selectors = ["article h3 a", ".bloglist a", ".td-module-thumb a", "h3 a", "h2 a", "a[href*='freejobalert.com']"]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            title = clean_text(a.get_text())
            if href and title:
                items.append((title, href))
        if items:
            break
    # fallback: first anchors in main area
    if not items:
        for a in soup.find_all("a", href=True)[:40]:
            href = a["href"]
            title = clean_text(a.get_text())
            if "freejobalert.com" in href and title:
                items.append((title, href))
    # dedupe
    seen = set(); uniq=[]
    for t,l in items:
        if t.lower() not in seen:
            uniq.append((t,l)); seen.add(t.lower())
    return uniq[:10]

def scrape_services_india():
    base = "https://services.india.gov.in/service/listing?ln=en&cat_id=2"
    html = fetch(base)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    items = []
    # look for table rows / anchors
    for a in soup.select("a[href]"):
        txt = clean_text(a.get_text())
        href = a.get("href")
        if not txt or txt.lower() in ("read more","view"):
            continue
        # service links are often internal path
        if href and href.startswith("/"):
            href = "https://services.india.gov.in" + href
        if "service" in href or "/service/" in href:
            items.append((txt, href))
    # fallback top anchors
    return items[:10]

# ---- detail fetch & content builder ----
def fetch_detail_and_build(title, link):
    html = fetch(link)
    if not html:
        # create minimal content
        content = f"<h2>{title}</h2>\n<p>Official Link: <a href='{link}' target='_blank'>{link}</a></p>"
        return content
    soup = BeautifulSoup(html, "lxml")
    # Title priority: page title or given title
    page_title = soup.title.string if soup.title else ""
    main_title = clean_text(page_title) or title

    # Attempt to build SarkariResult-like content:
    # - short excerpt (first paragraph)
    excerpt = ""
    # find main content container candidates
    for sel in ["div.entry-content", "div#content", "article", "div.post", "div.blog-post"]:
        block = soup.select_one(sel)
        if block:
            # get first <p>
            p = block.find("p")
            if p:
                excerpt = clean_text(p.get_text())
            break
    if not excerpt:
        # fallback first paragraph on page
        p = soup.find("p")
        if p:
            excerpt = clean_text(p.get_text())

    # Build details table if available: find tables inside content
    table_html = ""
    main_block = soup.select_one("div.entry-content") or soup.select_one("article") or soup
    if main_block:
        # try to extract first table (if it looks like vacancy details)
        t = main_block.find("table")
        if t:
            table_html = str(t)

    # Detect admit/hall ticket links
    admit_list = detect_admit_links(main_block, link)

    # Compose final HTML (SarkariResult style)
    content_parts = []
    content_parts.append(f"<h1>{main_title}</h1>")
    if excerpt:
        content_parts.append(f"<p>{excerpt}</p>")

    # include table if present (sanitized)
    if table_html:
        content_parts.append("<h3>Vacancy Details</h3>")
        content_parts.append(table_html)

    # Admit card section
    if admit_list:
        content_parts.append("<h3>Admit Card / Hall Ticket</h3><ul>")
        for t, href in admit_list:
            content_parts.append(f"<li><a href='{href}' target='_blank'>{clean_text(t)}</a></li>")
        content_parts.append("</ul>")

    # Always add Official link
    content_parts.append(f"<p><b>Official Link:</b> <a href='{link}' target='_blank'>{link}</a></p>")

    # Social follow footer
    content_parts.append("<hr>")
    content_parts.append("<p><strong>Follow for latest updates:</strong><br>"
                         "<a href='https://www.whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47'>WhatsApp</a> | "
                         "<a href='https://t.me/+gjQIJRUl1a8wYzM1'>Telegram</a> | "
                         "<a href='https://www.youtube.com/@Rojgar_bhaskar'>YouTube</a></p>")

    return "\n".join(content_parts)

# ---- orchestrator ----
def collect_all_sites():
    results = []
    # sarkariresult .cm
    try:
        results += scrape_sarkariresult_generic("https://sarkariresult.com.cm/")
    except Exception as e:
        print("SR CM error:", e)
    # sarkariresult .im
    try:
        results += scrape_sarkariresult_generic("https://sarkariresult.com.im/")
    except Exception as e:
        print("SR IM error:", e)
    # freejobalert
    try:
        results += scrape_freejobalert()
    except Exception as e:
        print("FreeJobAlert error:", e)
    # services.india (optional)
    try:
        results += scrape_services_india()
    except Exception as e:
        print("Services India error:", e)

    # dedupe by link and title
    final = []
    seen = set()
    for t,l in results:
        key = (l.strip())
        if key and key not in seen:
            final.append((clean_text(t), l))
            seen.add(key)
    return final

def main():
    WP_SITE = os.environ.get("WP_SITE_URL")
    WP_USER = os.environ.get("WP_USERNAME")
    WP_PASS = os.environ.get("WP_APP_PASSWORD")
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
    SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))

    if not (WP_SITE and WP_USER and WP_PASS):
        print("Missing WP credentials. Set WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD in env.")
        return

    print("Collecting items from sites...")
    items = collect_all_sites()
    print("Found", len(items), "candidates.")
    items = items[:MAX_ITEMS]

    posted = 0
    for title, link in items:
        try:
            print("Checking:", title)
            # avoid dup
            if wp_search_exists(WP_SITE, WP_USER, WP_PASS, title):
                print(" Already posted — skipping:", title)
                continue
            # build detail content
            content = fetch_detail_and_build(title, link)
            res = wp_create_post(WP_SITE, WP_USER, WP_PASS, title, content)
            if res:
                print(" POSTED:", res.get("link"))
                posted += 1
            else:
                print(" Post failed for:", title)
            time.sleep(SLEEP)
        except Exception as e:
            print(" Exception for", title, e)

    print("Done. Posted", posted, "new items.")

if __name__ == "__main__":
    main()
