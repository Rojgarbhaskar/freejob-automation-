#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Scraper - FINAL OPTIMIZED VERSION
- Strict Link Cleaning (No Aggregator Redirects)
- Exact SarkariResult Styling (Red/Green/Blue Headers)
- Enhanced Table Layouts
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

# ---- RojgarBhaskar Category IDs ----
CATEGORIES = {
    "latest_jobs": 18,
    "results": 19,
    "admit_card": 20,
    "answer_key": 21,
    "syllabus": 22,
    "admission": 23
}

CATEGORY_KEYWORDS = {
    20: ["admit card", "admit", "hall ticket", "call letter", "e-admit"],
    19: ["result", "merit list", "cut off", "cutoff", "score card", "scorecard", "merit"],
    21: ["answer key", "answer sheet", "objection"],
    22: ["syllabus", "exam pattern"],
    23: ["admission", "counselling", "counseling", "seat allotment"],
    18: ["recruitment", "vacancy", "bharti", "jobs", "notification", "apply", "online form", "post"]
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
    """Check if URL belongs to known aggregators"""
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

def detect_category(title):
    t = title.lower()
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return cat_id
    return CATEGORIES["latest_jobs"]

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

def scrape_freejobalert():
    items = []
    base = "https://www.freejobalert.com"
    url = f"{base}/latest-notifications/"
    
    log("FreeJobAlert: Fetching...")
    html = fetch(url)
    if not html: return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for a in links:
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if len(text) < 4: continue
        if 'freejobalert.com' not in href: continue
        
        if any(x in text.lower() for x in ['click here', 'more info', 'app download', 'join channel']):
            continue
            
        valid_keywords = ['apply', 'online', 'form', 'recruitment', 'vacancy', 'jobs', 'result', 'admit card', 'key', 'notification']
        if any(k in text.lower() for k in valid_keywords) or any(k in href.lower() for k in valid_keywords):
             full_url = make_absolute(href, base)
             items.append((text, full_url))

    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
            
    log(f"FreeJobAlert: {len(unique)} items")
    return unique[:20]

def scrape_sarkariresult_cm():
    items = []
    base = "https://www.sarkariresult.com.cm"
    
    log("SarkariResult.cm: Fetching...")
    html = fetch(base)
    if not html: html = fetch(base + "/")
    if not html: return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if len(text) < 4: continue
        
        skip_words = ['home', 'about', 'contact', 'privacy', 'disclaimer', 'dmca']
        if any(s in text.lower() for s in skip_words): continue
        
        if 'sarkariresult.com.cm' in href or href.startswith('/'):
            full_url = make_absolute(href, base)
            if full_url.count('/') > 3: 
                items.append((text, full_url))

    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
            
    log(f"SarkariResult.cm: {len(unique)} items")
    return unique[:20]

# ========== ADVANCED EXTRACTION ==========

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
                if sibling:
                    dates.append(f"<strong>{clean(node)}:</strong> {clean(sibling.get_text())}")
            else:
                if re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', clean_node):
                    dates.append(clean_node)
    
    if not dates:
        for header in soup.find_all(['h2', 'h3', 'h4', 'strong', 'b']):
            if 'date' in header.get_text().lower():
                curr = header.find_next()
                count = 0
                while curr and count < 5:
                    t = clean(curr.get_text())
                    if t and len(t) > 5 and any(c.isdigit() for c in t):
                        dates.append(t)
                    curr = curr.find_next()
                    count += 1
                break
                
    return dates[:6]

def extract_fees(soup):
    fees = []
    keywords = ['general', 'obc', 'ews', 'sc', 'st', 'ph', 'female']
    
    text_nodes = soup.find_all(string=True)
    for node in text_nodes:
        clean_node = clean(node).lower()
        if any(k in clean_node for k in keywords) and ('rs' in clean_node or '₹' in clean_node or '/' in clean_node):
             if len(clean_node) < 60:
                 fees.append(clean(node))
                 
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
                if sibling:
                    age.append(f"<strong>{clean(node)}:</strong> {clean(sibling.get_text())}")
            elif len(clean_node) < 50:
                age.append(clean_node)
                
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
        for tag in best_table.find_all(True):
            tag.attrs = {}
            
        best_table['style'] = "width:100%;border-collapse:collapse;border:1px solid #ccc;margin-top:10px;"
        for td in best_table.find_all(['td', 'th']):
            td['style'] = "border:1px solid #ccc;padding:8px;text-align:left;"
            
        return str(best_table)
    return "<p>See Notification for Vacancy Details</p>"

def extract_links(soup, base_url):
    """
    Strict Link Extraction:
    - Must NOT be an aggregator domain.
    - Must look like an official link or PDF.
    """
    links = []
    
    targets = [
        ('Apply Online', ['apply online', 'registration', 'login']),
        ('Download Notification', ['notification', 'official pdf', 'advertisement']),
        ('Official Website', ['official website', 'official site'])
    ]
    
    found_urls = set()
    
    for label, keywords in targets:
        best_link = None
        for a in soup.find_all('a', href=True):
            text = clean(a.get_text()).lower()
            href = a.get('href', '')
            
            full_url = make_absolute(href, base_url)
            
            # CRITICAL: Skip if link is to an aggregator
            if is_aggregator_domain(full_url):
                continue
                
            if any(k in text for k in keywords):
                if full_url not in found_urls:
                    best_link = full_url
                    break
        
        if best_link:
            links.append((label, best_link))
            found_urls.add(best_link)
            
    return links

# ========== SARKARIRESULT STYLE BUILDER (EXACT MATCH) ==========

def build_content(title, link):
    html = fetch(link)
    if not html: return None, title
    
    soup = BeautifulSoup(html, 'html.parser')
    
    h1 = soup.find('h1')
    actual_title = clean(h1.get_text()) if h1 else title
    
    dates = extract_dates(soup)
    fees = extract_fees(soup)
    age = extract_age(soup)
    vacancy_html = extract_vacancy(soup)
    imp_links = extract_links(soup, link)
    
    # Colors from Screenshots
    RED = "#ab1e1e"
    GREEN = "#008000"
    BLUE = "#000080"
    
    content = f"""
<div style="font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; border: 2px solid {RED};">

    <!-- Header -->
    <div style="text-align: center; background-color: {RED}; color: white; padding: 15px;">
        <h1 style="margin: 0; font-size: 22px; font-weight: bold;">{actual_title}</h1>
        <p style="margin: 8px 0 0; font-size: 14px; font-weight: bold;">RojgarBhaskar.com : Short Details of Notification</p>
    </div>

    <!-- Important Dates & Application Fee (Side by Side) -->
    <table style="width: 100%; border-collapse: collapse; margin-top: 0;">
        <tr>
            <!-- Dates -->
            <td style="width: 50%; vertical-align: top; border-right: 2px solid {RED}; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">
                    Important Dates
                </div>
                <div style="padding: 15px;">
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        {''.join([f'<li style="margin-bottom: 8px;">• {d}</li>' for d in dates]) or '<li>• Check Notification</li>'}
                    </ul>
                </div>
            </td>
            
            <!-- Fees -->
            <td style="width: 50%; vertical-align: top; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">
                    Application Fee
                </div>
                <div style="padding: 15px;">
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        {''.join([f'<li style="margin-bottom: 8px;">• {f}</li>' for f in fees]) or '<li>• Check Notification</li>'}
                    </ul>
                </div>
            </td>
        </tr>
    </table>

    <!-- Age Limit (Green Header) -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {GREEN}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">
            {actual_title} : Age Limit Details
        </div>
        <div style="padding: 15px;">
            <ul style="list-style: none; padding: 0; margin: 0;">
                 {''.join([f'<li style="margin-bottom: 8px;">• {a}</li>' for a in age]) or '<li>• As per Rules</li>'}
            </ul>
        </div>
    </div>

    <!-- Vacancy Details (Blue Header) -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {BLUE}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">
            Vacancy Details
        </div>
        <div style="padding: 15px; overflow-x: auto;">
            {vacancy_html}
        </div>
    </div>

    <!-- Important Links (Red Header) -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center; font-size: 18px;">
            Important Links
        </div>
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
    
    <!-- Footer Note -->
    <div style="text-align: center; padding: 15px; border-top: 1px solid #ddd; color: #666; font-size: 13px;">
        Note: Interested Candidates Can Read the Full Notification Before Apply Online.
    </div>

</div>
"""
    return content, actual_title

# ========== MAIN ==========

def main():
    log("=" * 60)
    log("RojgarBhaskar Scraper - Final Version")
    log("=" * 60)
    
    WP_SITE = os.environ.get("WP_SITE_URL", "").strip()
    WP_USER = os.environ.get("WP_USERNAME", "").strip()
    WP_PASS = os.environ.get("WP_APP_PASSWORD", "").strip()
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "15"))
    
    if not all([WP_SITE, WP_USER, WP_PASS]):
        log("ERROR: Missing credentials!")
        sys.exit(1)
    
    all_items = []
    all_items.extend(scrape_freejobalert())
    all_items.extend(scrape_sarkariresult_cm())
    
    seen = set()
    unique = []
    for t, l in all_items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
            
    log(f"Total Unique Items: {len(unique)}")
    
    posted = 0
    for title, link in unique[:MAX_ITEMS]:
        try:
            log(f"Processing: {title[:40]}...")
            
            if wp_exists(WP_SITE, WP_USER, WP_PASS, title):
                log("  → Already exists")
                continue
                
            content, actual_title = build_content(title, link)
            if not content: continue
            
            if actual_title != title and wp_exists(WP_SITE, WP_USER, WP_PASS, actual_title):
                log("  → Already exists (Actual Title)")
                continue
                
            cat_id = detect_category(actual_title)
            res = wp_post(WP_SITE, WP_USER, WP_PASS, actual_title, content, cat_id)
            
            if res:
                log(f"  ✅ Posted: {res.get('link')}")
                posted += 1
            else:
                log("  ❌ Failed")
                
        except Exception as e:
            log(f"  ❌ Error: {e}")
            
    log(f"Done. Posted {posted} new items.")

if __name__ == "__main__":
    main()
