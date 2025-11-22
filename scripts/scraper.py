#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Multi-Site Job Scraper
Fixed version - Real working selectors
Sources: sarkariresult.com, freejobalert.com, sarkariexam.com
"""

import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ---- Config ----
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
TIMEOUT = 25

# ---- Utility Functions ----
def log(msg):
    print(f"[LOG] {msg}")

def fetch(url):
    """Fetch URL with error handling"""
    try:
        log(f"Fetching: {url}")
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=True)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except requests.exceptions.RequestException as e:
        log(f"Fetch error for {url}: {e}")
        return ""

def clean(text):
    """Clean text - remove extra whitespace"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def make_absolute(url, base):
    """Convert relative URL to absolute"""
    if not url:
        return ""
    if url.startswith(('http://', 'https://')):
        return url
    return urljoin(base, url)

# ---- WordPress Functions ----
def wp_post_exists(site, user, pwd, title):
    """Check if post with same title exists"""
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        params = {"search": title[:50], "per_page": 10, "status": "publish,draft"}
        r = requests.get(url, params=params, auth=(user, pwd), timeout=TIMEOUT)
        if r.status_code == 200:
            for post in r.json():
                existing = post.get("title", {}).get("rendered", "")
                if clean(existing).lower() == clean(title).lower():
                    return True
    except Exception as e:
        log(f"WP search error: {e}")
    return False

def wp_create_post(site, user, pwd, title, content, status="publish"):
    """Create WordPress post"""
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        data = {
            "title": title,
            "content": content,
            "status": status
        }
        r = requests.post(url, json=data, auth=(user, pwd), timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        else:
            log(f"WP create error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"WP create exception: {e}")
    return None

# ---- Site Scrapers ----

def scrape_rojgarlive():
    """Scrape from rojgarlive.com"""
    items = []
    base = "https://www.rojgarlive.com"
    url = f"{base}/government-jobs"
    
    html = fetch(url)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 10:
            continue
        if any(skip in text.lower() for skip in ['view more', 'read more', 'click here', 'home', 'contact']):
            continue
        
        full_url = make_absolute(href, base)
        if 'rojgarlive.com' in full_url and full_url != url:
            if '/category/' not in full_url and '/tag/' not in full_url:
                items.append((text, full_url))
    
    seen = set()
    unique = []
    for title, link in items:
        key = link.lower()
        if key not in seen:
            seen.add(key)
            unique.append((title, link))
    
    log(f"RojgarLive: Found {len(unique)} items")
    return unique[:15]

def scrape_freejobalert():
    """Scrape from freejobalert.com"""
    items = []
    base = "https://www.freejobalert.com"
    url = f"{base}/latest-notifications/"
    
    html = fetch(url)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # FreeJobAlert structure: Find post links
    # Usually in widget areas or main content
    
    # Method 1: Look for article/post links
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 10:
            continue
        if any(skip in text.lower() for skip in ['view more', 'read more', 'click here', 'home']):
            continue
        
        # Check if freejobalert link with job content
        if 'freejobalert.com' in href and href != url:
            # Avoid category/tag pages
            if '/category/' in href or '/tag/' in href:
                continue
            items.append((text, href))
    
    # Deduplicate
    seen = set()
    unique = []
    for title, link in items:
        key = link.lower()
        if key not in seen:
            seen.add(key)
            unique.append((title, link))
    
    log(f"FreeJobAlert: Found {len(unique)} items")
    return unique[:15]

def scrape_sarkariexam():
    """Scrape from sarkariexam.com"""
    items = []
    base = "https://www.sarkariexam.com"
    
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 10:
            continue
        if any(skip in text.lower() for skip in ['view more', 'read more', 'click here', 'home']):
            continue
        
        # Job related links
        if 'sarkariexam.com' in href:
            if '/category/' in href or '/tag/' in href or href == base + '/':
                continue
            items.append((text, href))
    
    seen = set()
    unique = []
    for title, link in items:
        key = link.lower()
        if key not in seen:
            seen.add(key)
            unique.append((title, link))
    
    log(f"SarkariExam: Found {len(unique)} items")
    return unique[:10]

# ---- Content Builder ----

def build_post_content(title, link):
    """Fetch detail page and build SarkariResult-style content"""
    
    html = fetch(link)
    
    # Default content if fetch fails
    if not html:
        return f"""
<div class="job-post">
<h2>{title}</h2>
<p><strong>Source:</strong> <a href="{link}" target="_blank" rel="noopener">{link}</a></p>
<hr>
<p><strong>RojgarBhaskar को Follow करें:</strong><br>
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank">📱 WhatsApp</a> | 
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank">📢 Telegram</a> | 
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank">🎥 YouTube</a></p>
</div>
"""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract page title
    page_title = ""
    if soup.title:
        page_title = clean(soup.title.string)
    final_title = page_title if page_title else title
    
    # Extract excerpt (first paragraph)
    excerpt = ""
    content_selectors = ['div.entry-content', 'article', 'div.post-content', 'div.content', 'div#content']
    main_content = None
    
    for sel in content_selectors:
        main_content = soup.select_one(sel)
        if main_content:
            break
    
    if not main_content:
        main_content = soup.body if soup.body else soup
    
    # Get first meaningful paragraph
    for p in main_content.find_all('p'):
        text = clean(p.get_text())
        if len(text) > 50:
            excerpt = text[:300] + "..." if len(text) > 300 else text
            break
    
    # Extract tables (vacancy details)
    tables_html = ""
    tables = main_content.find_all('table')
    if tables:
        # Take first 2 tables max
        for t in tables[:2]:
            tables_html += str(t) + "\n"
    
    # Find important links (Apply, Admit Card, etc.)
    important_links = []
    keywords = ['apply', 'admit', 'hall ticket', 'result', 'notification', 'official', 'download']
    
    for a in main_content.find_all('a', href=True):
        text = clean(a.get_text()).lower()
        href = a.get('href', '')
        if any(kw in text for kw in keywords) and href.startswith('http'):
            important_links.append((clean(a.get_text()), href))
    
    # Remove duplicates from important links
    seen_links = set()
    unique_links = []
    for t, l in important_links:
        if l not in seen_links:
            seen_links.add(l)
            unique_links.append((t, l))
    
    # Build final HTML content
    parts = []
    
    # Title
    parts.append(f'<h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:10px;">{final_title}</h2>')
    
    # Excerpt
    if excerpt:
        parts.append(f'<p>{excerpt}</p>')
    
    # Vacancy Table
    if tables_html:
        parts.append('<h3 style="color:#d32f2f;">📋 Vacancy Details / Important Dates</h3>')
        parts.append(f'<div class="table-responsive">{tables_html}</div>')
    
    # Important Links
    if unique_links:
        parts.append('<h3 style="color:#388e3c;">🔗 Important Links</h3>')
        parts.append('<ul>')
        for text, href in unique_links[:10]:
            parts.append(f'<li><a href="{href}" target="_blank" rel="noopener">{text}</a></li>')
        parts.append('</ul>')
    
    # Official Source
    parts.append(f'<p><strong>📌 Official Source:</strong> <a href="{link}" target="_blank" rel="noopener">{link}</a></p>')
    
    # Social Follow Section
    parts.append('<hr style="margin:20px 0;">')
    parts.append('''
<div style="background:#f5f5f5;padding:15px;border-radius:8px;text-align:center;">
<p style="margin:0;font-weight:bold;color:#333;">📢 RojgarBhaskar को Follow करें - Latest Jobs के लिए!</p>
<p style="margin:10px 0 0 0;">
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank" style="margin:0 10px;">📱 WhatsApp</a>
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank" style="margin:0 10px;">📢 Telegram</a>
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank" style="margin:0 10px;">🎥 YouTube</a>
</p>
</div>
''')
    
    return '\n'.join(parts)

# ---- Main Function ----

def main():
    log("="*50)
    log("RojgarBhaskar Scraper Started")
    log("="*50)
    
    # Get environment variables
    WP_SITE = os.environ.get("WP_SITE_URL", "").strip()
    WP_USER = os.environ.get("WP_USERNAME", "").strip()
    WP_PASS = os.environ.get("WP_APP_PASSWORD", "").strip()
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
    SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))
    
    # Validate credentials
    if not WP_SITE or not WP_USER or not WP_PASS:
        log("ERROR: Missing WordPress credentials!")
        log("Set WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD as environment variables")
        sys.exit(1)
    
    log(f"WordPress Site: {WP_SITE}")
    log(f"Max Items: {MAX_ITEMS}")
    
    # Collect from all sources
    all_items = []
    
    # Source 1: SarkariResult
    try:
        all_items.extend(scrape_sarkariresult())
    except Exception as e:
        log(f"SarkariResult scraper error: {e}")
    
    # Source 2: FreeJobAlert  
    try:
        all_items.extend(scrape_freejobalert())
    except Exception as e:
        log(f"FreeJobAlert scraper error: {e}")
    
    # Source 3: SarkariExam
    try:
        all_items.extend(scrape_sarkariexam())
    except Exception as e:
        log(f"SarkariExam scraper error: {e}")
    
    log(f"Total items collected: {len(all_items)}")
    
    # Global deduplication
    seen = set()
    unique_items = []
    for title, link in all_items:
        key = clean(title).lower()[:50]
        if key not in seen and len(key) > 5:
            seen.add(key)
            unique_items.append((title, link))
    
    log(f"After dedup: {len(unique_items)} items")
    
    # Limit items
    items_to_process = unique_items[:MAX_ITEMS]
    
    # Post to WordPress
    posted_count = 0
    skipped_count = 0
    
    for title, link in items_to_process:
        try:
            log(f"Processing: {title[:50]}...")
            
            # Check duplicate in WordPress
            if wp_post_exists(WP_SITE, WP_USER, WP_PASS, title):
                log(f"  → Already exists, skipping")
                skipped_count += 1
                continue
            
            # Build content
            content = build_post_content(title, link)
            
            # Create post
            result = wp_create_post(WP_SITE, WP_USER, WP_PASS, title, content)
            
            if result:
                post_link = result.get('link', 'N/A')
                log(f"  ✅ POSTED: {post_link}")
                posted_count += 1
            else:
                log(f"  ❌ Failed to post")
            
            # Sleep between posts
            time.sleep(SLEEP)
            
        except Exception as e:
            log(f"  ❌ Error: {e}")
    
    log("="*50)
    log(f"COMPLETED!")
    log(f"Posted: {posted_count} | Skipped: {skipped_count}")
    log("="*50)

if __name__ == "__main__":
    main()
