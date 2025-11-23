#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Auto-Scraper (Optimized Original)
- Bulk Scrapes from FreeJobAlert, SarkariResult, SarkariNaukri, FreshersLive
- Generates SarkariResult-style HTML (Red/Green/Blue)
- Auto-Posts to WordPress
- No Arguments Needed (Runs via GitHub Actions)
"""

import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import random

# ---- Config ----
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

TIMEOUT = 30

# ---- User's Category IDs ----
CATEGORIES = {
    "latest_jobs": 18,
    "results": 19,
    "admit_card": 20,
    "answer_key": 21,
    "syllabus": 22,
    "admission": 23
}

# Map internal keys to Category IDs
CAT_MAP = {
    'job': 18,
    'result': 19,
    'admit': 20,
    'key': 21,
    'syllabus': 22,
    'admission': 23
}

# ---- Utility ----
def log(msg):
    print(f"[LOG] {msg}")

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

def fetch(url):
    try:
        log(f"Fetching: {url}")
        time.sleep(random.uniform(1.0, 2.0))
        r = requests.get(url, headers=get_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        log(f"  → Error: {e}")
        return ""

def clean(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', text).strip()

def make_absolute(url, base):
    if not url:
        return ""
    if url.startswith(('http://', 'https://')):
        return url
    return urljoin(base, url)

def is_aggregator_domain(url):
    aggregators = [
        'freejobalert.com', 'sarkariexam.com', 'rojgarlive.com', 
        'sarkarinaukri.com', 'fresherslive.com', 'sarkariresult.com.cm',
        'sarkariresult.com', 'jagranjosh.com', 'careerpower.in'
    ]
    domain = urlparse(url).netloc.lower()
    for agg in aggregators:
        if agg in domain:
            return True
    return False

# ---- WordPress ----
def wp_exists(site, user, pwd, title):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        search_term = title[:30]
        r = requests.get(url, params={"search": search_term, "per_page": 5}, auth=(user, pwd), timeout=15)
        if r.status_code == 200:
            for p in r.json():
                remote_title = clean(p.get("title", {}).get("rendered", "")).lower()
                local_title = clean(title).lower()
                if local_title in remote_title or remote_title in local_title:
                    return True
    except:
        pass
    return False

def wp_post(site, user, pwd, title, content, cat_id):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        data = {
            "title": title,
            "content": content,
            "status": "publish",
            "categories": [cat_id]
        }
        r = requests.post(url, json=data, auth=(user, pwd), timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        log(f"WP Error: {r.status_code} - {r.text}")
    except Exception as e:
        log(f"WP Exception: {e}")
    return None

# ========== SCRAPERS ==========

def scrape_generic(url, base_domain, cat_type):
    """Generic scraper for list pages"""
    items = []
    log(f"Scraping {cat_type} from {url}...")
    
    html = fetch(url)
    if not html: return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for a in links:
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if len(text) < 5: continue
        
        # Domain check
        if base_domain not in href and not href.startswith('/'): continue
        
        # Skip junk
        if any(x in text.lower() for x in ['click here', 'more info', 'app', 'join', 'privacy', 'contact']):
            continue
            
        full_url = make_absolute(href, url)
        items.append((text, full_url, cat_type))
        
    return items[:15] # Limit per category

def collect_all_items():
    all_items = []
    
    # 1. FreeJobAlert (Specific Categories)
    fja_sources = [
        ("https://www.freejobalert.com/latest-notifications/", 'job'),
        ("https://www.freejobalert.com/admit-card/", 'admit'),
        ("https://www.freejobalert.com/exam-results/", 'result'),
        ("https://www.freejobalert.com/answer-key/", 'key'),
        ("https://www.freejobalert.com/syllabus/", 'syllabus'),
        ("https://www.freejobalert.com/admission/", 'admission')
    ]
    for url, cat in fja_sources:
        all_items.extend(scrape_generic(url, 'freejobalert.com', cat))
        
    # 2. SarkariResult.cm (Homepage Mixed)
    sr_items = scrape_generic("https://www.sarkariresult.com.cm/", 'sarkariresult.com.cm', 'job')
    # Try to guess category for mixed items
    for i, (t, l, c) in enumerate(sr_items):
        t_lower = t.lower()
        if 'admit' in t_lower: sr_items[i] = (t, l, 'admit')
        elif 'result' in t_lower: sr_items[i] = (t, l, 'result')
        elif 'key' in t_lower: sr_items[i] = (t, l, 'key')
    all_items.extend(sr_items)
    
    # 3. SarkariNaukri
    all_items.extend(scrape_generic("https://www.sarkarinaukri.com/", 'sarkarinaukri.com', 'job'))
    
    # 4. FreshersLive
    all_items.extend(scrape_generic("https://www.fresherslive.com/government-jobs", 'fresherslive.com', 'job'))
    
    return all_items

# ========== EXTRACTION & BUILDER ==========

def extract_dates(soup):
    dates = []
    keywords = ['application begin', 'start date', 'last date', 'exam date', 'admit card', 'result available']
    text_nodes = soup.find_all(string=True)
    for node in text_nodes:
        clean_node = clean(node).lower()
        if any(k in clean_node for k in keywords) and len(clean_node) < 50:
            parent = node.parent
            if parent.name in ['td', 'th']:
                sibling = parent.find_next_sibling('td')
                if sibling: dates.append(f"<strong>{clean(node)}:</strong> {clean(sibling.get_text())}")
            else:
                if re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', clean_node): dates.append(clean_node)
    return dates[:6]

def extract_fees(soup):
    fees = []
    keywords = ['general', 'obc', 'ews', 'sc', 'st', 'ph', 'female']
    text_nodes = soup.find_all(string=True)
    for node in text_nodes:
        clean_node = clean(node).lower()
        if any(k in clean_node for k in keywords) and ('rs' in clean_node or '₹' in clean_node or '/' in clean_node):
             if len(clean_node) < 60: fees.append(clean(node))
    return list(set(fees))[:5]

def extract_age(soup):
    age = []
    keywords = ['minimum age', 'maximum age', 'min age', 'max age', 'age limit']
    text_nodes = soup.find_all(string=True)
    for node in text_nodes:
        clean_node = clean(node).lower()
        if any(k in clean_node for k in keywords):
            parent = node.parent
            if parent.name in ['td', 'th']:
                sibling = parent.find_next_sibling('td')
                if sibling: age.append(f"<strong>{clean(node)}:</strong> {clean(sibling.get_text())}")
            elif len(clean_node) < 50: age.append(clean_node)
    return list(set(age))[:4]

def extract_vacancy(soup):
    best_table = None
    max_score = 0
    for table in soup.find_all('table'):
        score = 0
        headers = [clean(th.get_text()).lower() for th in table.find_all(['th', 'td'])]
        if any('post' in h for h in headers): score += 2
        if any('total' in h for h in headers): score += 2
        if any('eligibility' in h or 'qualification' in h for h in headers): score += 2
        if score > max_score:
            max_score = score
            best_table = table
    if best_table:
        for tag in best_table.find_all(True): tag.attrs = {}
        best_table['style'] = "width:100%;border-collapse:collapse;border:1px solid #ccc;margin-top:10px;"
        for td in best_table.find_all(['td', 'th']):
            td['style'] = "border:1px solid #ccc;padding:8px;text-align:left;"
        return str(best_table)
    return "<p>See Notification for Vacancy Details</p>"

def extract_links(soup, base_url, cat_type):
    """Smart Link Extraction based on Category"""
    links = []
    
    # Define targets based on category
    targets = []
    
    # Common links
    targets.append(('Official Website', ['official website', 'official site']))
    targets.append(('Download Notification', ['notification', 'official pdf', 'advertisement']))
    
    # Category specific links
    if cat_type == 'job':
        targets.insert(0, ('Apply Online', ['apply online', 'registration', 'login']))
    elif cat_type == 'admit':
        targets.insert(0, ('Download Admit Card', ['admit card', 'hall ticket', 'call letter', 'download']))
    elif cat_type == 'result':
        targets.insert(0, ('Download Result', ['result', 'merit list', 'score card', 'cutoff']))
    elif cat_type == 'key':
        targets.insert(0, ('Download Answer Key', ['answer key', 'solution', 'sheet']))
    elif cat_type == 'syllabus':
        targets.insert(0, ('Download Syllabus', ['syllabus', 'pattern', 'pdf']))
    else:
        targets.insert(0, ('Click Here', ['click here', 'link', 'apply']))

    found_urls = set()
    
    for label, keywords in targets:
        best_link = None
        for a in soup.find_all('a', href=True):
            text = clean(a.get_text()).lower()
            href = a.get('href', '')
            full_url = make_absolute(href, base_url)
            
            if is_aggregator_domain(full_url): continue
            
            if any(k in text for k in keywords):
                if full_url not in found_urls:
                    best_link = full_url
                    break
        if best_link:
            links.append((label, best_link))
            found_urls.add(best_link)
            
    return links

def build_content(title, link, cat_type):
    html = fetch(link)
    if not html: return None, title
    
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    actual_title = clean(h1.get_text()) if h1 else title
    
    dates = extract_dates(soup)
    fees = extract_fees(soup)
    age = extract_age(soup)
    vacancy_html = extract_vacancy(soup)
    imp_links = extract_links(soup, link, cat_type)
    
    RED = "#ab1e1e"
    GREEN = "#008000"
    BLUE = "#000080"
    
    content = f"""
<div style="font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; border: 2px solid {RED};">
    <div style="text-align: center; background-color: {RED}; color: white; padding: 15px;">
        <h1 style="margin: 0; font-size: 22px; font-weight: bold;">{actual_title}</h1>
        <p style="margin: 8px 0 0; font-size: 14px; font-weight: bold;">RojgarBhaskar.com : Short Details of Notification</p>
    </div>
    <table style="width: 100%; border-collapse: collapse; margin-top: 0;">
        <tr>
            <td style="width: 50%; vertical-align: top; border-right: 2px solid {RED}; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">Important Dates</div>
                <div style="padding: 15px;">
                    <ul style="list-style: none; padding: 0; margin: 0;">{''.join([f'<li style="margin-bottom: 8px;">• {d}</li>' for d in dates]) or '<li>• Check Notification</li>'}</ul>
                </div>
            </td>
            <td style="width: 50%; vertical-align: top; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">Application Fee</div>
                <div style="padding: 15px;">
                    <ul style="list-style: none; padding: 0; margin: 0;">{''.join([f'<li style="margin-bottom: 8px;">• {f}</li>' for f in fees]) or '<li>• Check Notification</li>'}</ul>
                </div>
            </td>
        </tr>
    </table>
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {GREEN}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">{actual_title} : Age Limit Details</div>
        <div style="padding: 15px;">
            <ul style="list-style: none; padding: 0; margin: 0;">{''.join([f'<li style="margin-bottom: 8px;">• {a}</li>' for a in age]) or '<li>• As per Rules</li>'}</ul>
        </div>
    </div>
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {BLUE}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">Vacancy Details</div>
        <div style="padding: 15px; overflow-x: auto;">{vacancy_html}</div>
    </div>
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">Important Links</div>
        <div style="padding: 15px;">
            <table style="width: 100%; border-collapse: collapse;">
    """
    for label, url in imp_links:
        content += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold; font-size: 16px;">{label}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">
                        <a href="{url}" target="_blank" style="background-color: {RED}; color: white; padding: 8px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Click Here</a>
                    </td>
                </tr>
        """
    content += """
            </table>
        </div>
    </div>
    <div style="text-align: center; padding: 15px; border-top: 1px solid #ddd; color: #666; font-size: 13px;">
        Note: Interested Candidates Can Read the Full Notification Before Apply Online.
    </div>
</div>
"""
    return content, actual_title

# ========== MAIN ==========

def main():
    log("=" * 60)
    log("RojgarBhaskar Auto-Poster Starting...")
    log("=" * 60)
    
    WP_SITE = os.environ.get("WP_SITE_URL", "").strip()
    WP_USER = os.environ.get("WP_USERNAME", "").strip()
    WP_PASS = os.environ.get("WP_APP_PASSWORD", "").strip()
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
    SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))
    
    log("Config:")
    log(f" - WP Site: {WP_SITE}")
    log(f" - Max Items: {MAX_ITEMS}")
    log(f" - Sleep Between Posts: {SLEEP}s")
    
    if not all([WP_SITE, WP_USER, WP_PASS]):
        log("ERROR: Missing credentials! Check GitHub Secrets.")
        sys.exit(1)
    
    # 1. Collect
    all_items = collect_all_items()
    
    # 2. Dedupe
    seen = set()
    unique = []
    for t, l, c in all_items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l, c))
            
    log(f"Total Unique Items Found: {len(unique)}")
    
    # 3. Post
    posted = 0
    skipped = 0
    
    for title, link, cat_type in unique[:MAX_ITEMS]:
        try:
            log(f"Processing [{cat_type}]: {title[:40]}...")
            
            if wp_exists(WP_SITE, WP_USER, WP_PASS, title):
                log("  → Already exists")
                skipped += 1
                continue
                
            content, actual_title = build_content(title, link, cat_type)
            if not content: continue
            
            if actual_title != title and wp_exists(WP_SITE, WP_USER, WP_PASS, actual_title):
                log("  → Already exists (Actual Title)")
                skipped += 1
                continue
                
            cat_id = CAT_MAP.get(cat_type, 18)
            res = wp_post(WP_SITE, WP_USER, WP_PASS, actual_title, content, cat_id)
            
            if res:
                log(f"  ✅ Posted: {res.get('link')}")
                posted += 1
