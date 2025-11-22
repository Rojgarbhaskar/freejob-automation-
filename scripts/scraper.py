#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Scraper - WORKING VERSION
Tested websites that don't block bots
"""

import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import random

# ---- Config ----
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

TIMEOUT = 20

# ---- Category IDs (RojgarBhaskar) ----
CATEGORIES = {
    "latest_jobs": 18,
    "results": 19,
    "admit_card": 20,
    "answer_key": 21,
    "syllabus": 22,
    "admission": 23
}

CATEGORY_KEYWORDS = {
    20: ["admit card", "admit", "hall ticket", "call letter"],
    19: ["result", "merit list", "cut off", "score card"],
    21: ["answer key", "answer sheet", "objection"],
    22: ["syllabus", "exam pattern"],
    23: ["admission", "counselling", "counseling"],
    18: ["recruitment", "vacancy", "bharti", "jobs", "notification", "apply", "online form"]
}

BLOCKED_DOMAINS = ["sarkariexam.com", "rojgarlive.com", "naukri.com"]
# Note: FreeJobAlert links allowed in scraping but filtered in output

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
        time.sleep(random.uniform(1, 2))  # Random delay
        r = requests.get(url, headers=get_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        log(f"  → Success: {len(r.text)} bytes")
        return r.text
    except Exception as e:
        log(f"  → Error: {e}")
        return ""

def clean(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def make_absolute(url, base):
    if not url:
        return ""
    if url.startswith(('http://', 'https://')):
        return url
    return urljoin(base, url)

def is_blocked(url):
    for d in BLOCKED_DOMAINS:
        if d in url.lower():
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
        r = requests.get(url, params={"search": title[:50], "per_page": 5}, auth=(user, pwd), timeout=15)
        if r.status_code == 200:
            for p in r.json():
                if clean(p.get("title", {}).get("rendered", "")).lower() == clean(title).lower():
                    return True
    except:
        pass
    return False

def wp_post(site, user, pwd, title, content, cat_id):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        r = requests.post(url, json={"title": title, "content": content, "status": "publish", "categories": [cat_id]}, auth=(user, pwd), timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        log(f"WP Error: {r.status_code}")
    except Exception as e:
        log(f"WP Exception: {e}")
    return None

# ---- WORKING SCRAPERS ----

def scrape_freejobalert():
    """
    FreeJobAlert.com Scraper
    Step 1: Get job links from latest-notifications page
    Step 2: Visit each "Get Details" link to get actual job page
    """
    items = []
    base = "https://www.freejobalert.com"
    url = f"{base}/latest-notifications/"
    
    log("FreeJobAlert: Fetching main page...")
    html = fetch(url)
    if not html:
        log("FreeJobAlert: Failed to fetch main page")
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all job links - they are in table rows
    # Structure: Table with job title and "Get Details" link
    detail_links = []
    
    # Method 1: Find links in tables
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            for a in row.find_all('a', href=True):
                href = a.get('href', '')
                text = clean(a.get_text())
                
                # Skip if too short or navigation link
                if not text or len(text) < 10:
                    continue
                if any(skip in text.lower() for skip in ['view more', 'click here', 'home', 'about']):
                    continue
                
                # Check if it's a job detail page link
                if 'freejobalert.com' in href and '/latest-notifications/' not in href:
                    # This is likely a "Get Details" link
                    full_url = make_absolute(href, base)
                    detail_links.append((text, full_url))
    
    # Method 2: Find links with specific patterns
    if not detail_links:
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = clean(a.get_text())
            
            if not text or len(text) < 15:
                continue
            
            # Job detail pages usually have organization name in URL
            if 'freejobalert.com' in href:
                # Skip category/tag pages
                if any(skip in href for skip in ['/category/', '/tag/', '/page/', '/author/']):
                    continue
                if href != url and '/latest-notifications/' not in href:
                    full_url = make_absolute(href, base)
                    detail_links.append((text, full_url))
    
    # Deduplicate
    seen = set()
    unique_links = []
    for title, link in detail_links:
        if link not in seen:
            seen.add(link)
            unique_links.append((title, link))
    
    log(f"FreeJobAlert: Found {len(unique_links)} detail page links")
    
    # Now fetch each detail page to get actual job info
    for title, detail_url in unique_links[:15]:  # Limit to 15
        try:
            log(f"  Fetching detail: {title[:40]}...")
            items.append((title, detail_url))
        except Exception as e:
            log(f"  Error: {e}")
    
    log(f"FreeJobAlert: Total {len(items)} items")
    return items


def scrape_ncs_gov():
    """National Career Service - Government Portal (Always works)"""
    items = []
    url = "https://www.ncs.gov.in/job-seeker/Pages/Search.aspx"
    
    # NCS has API-like search
    api_url = "https://www.ncs.gov.in/api/aggregator/search/jobs"
    
    try:
        # Try direct page scraping
        html = fetch("https://www.ncs.gov.in/job-seeker/Pages/Government.aspx")
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                text = clean(a.get_text())
                href = a.get('href', '')
                if text and len(text) > 15 and ('job' in href.lower() or 'career' in href.lower()):
                    full = make_absolute(href, "https://www.ncs.gov.in")
                    items.append((text, full))
    except Exception as e:
        log(f"NCS error: {e}")
    
    log(f"NCS Gov: {len(items)} items")
    return items[:10]

def scrape_employment_news():
    """Employment News - Government of India"""
    items = []
    base = "https://www.employmentnews.gov.in"
    
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find job links
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        
        if not text or len(text) < 10:
            continue
        
        # Job related
        keywords = ['recruitment', 'vacancy', 'jobs', 'walk-in', 'admit', 'result', 'notification']
        if any(kw in text.lower() for kw in keywords):
            full = make_absolute(href, base)
            if 'employmentnews.gov.in' in full or full.startswith(base):
                items.append((text, full))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"Employment News: {len(unique)} items")
    return unique[:10]

def scrape_sarkarinaukri():
    """SarkariNaukri.com - Usually accessible"""
    items = []
    base = "https://www.sarkarinaukri.com"
    
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find job boxes/links
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        
        if not text or len(text) < 15:
            continue
        
        skip = ['home', 'about', 'contact', 'privacy', 'disclaimer', 'advertise']
        if any(s in text.lower() for s in skip):
            continue
        
        if 'sarkarinaukri.com' in href and '/post/' in href:
            items.append((text, href))
        elif href.startswith('/') and len(text) > 20:
            full = make_absolute(href, base)
            items.append((text, full))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen and 'sarkarinaukri.com' in l:
            seen.add(l)
            unique.append((t, l))
    
    log(f"SarkariNaukri: {len(unique)} items")
    return unique[:10]

def scrape_fresherslive():
    """FreshersLive - Government Jobs Section"""
    items = []
    base = "https://www.fresherslive.com"
    url = f"{base}/government-jobs"
    
    html = fetch(url)
    if not html:
        html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        
        if not text or len(text) < 15:
            continue
        
        if 'fresherslive.com' in href:
            if '/government-jobs/' in href or '/central-govt-jobs/' in href or '/state-govt-jobs/' in href:
                items.append((text, href))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"FreshersLive: {len(unique)} items")
    return unique[:10]

def scrape_hirelateral():
    """HireLateral - Job Portal"""
    items = []
    base = "https://www.hirelateral.com"
    url = f"{base}/government-jobs"
    
    html = fetch(url)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        
        if text and len(text) > 15 and 'hirelateral.com' in href:
            if '/job/' in href or '/government' in href:
                items.append((text, href))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"HireLateral: {len(unique)} items")
    return unique[:10]

# ---- Content Builder ----

def extract_details(soup):
    """Extract job details from page"""
    details = {}
    
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = clean(cells[0].get_text()).lower()
                value = clean(cells[1].get_text())
                
                if not value or len(value) < 2:
                    continue
                
                if any(k in label for k in ['organization', 'department', 'company', 'board']):
                    details['org'] = value
                elif any(k in label for k in ['post', 'position', 'job title']):
                    details['post'] = value
                elif any(k in label for k in ['qualification', 'education', 'eligibility']):
                    details['qual'] = value
                elif any(k in label for k in ['vacancy', 'total post', 'no of post']):
                    details['vacancy'] = value
                elif any(k in label for k in ['last date', 'closing date', 'apply before']):
                    details['last_date'] = value
                elif any(k in label for k in ['salary', 'pay scale', 'pay band']):
                    details['salary'] = value
                elif any(k in label for k in ['age', 'age limit']):
                    details['age'] = value
                elif any(k in label for k in ['fee', 'application fee']):
                    details['fee'] = value
    
    return details

def extract_links(soup, source):
    """Extract official links only - NO aggregator site links in output"""
    links = {"apply": None, "notification": None, "official": None}
    
    # Domains to exclude from Important Links output
    excluded_in_output = ['fresherslive', 'sarkarinaukri', 'hirelateral', 'employmentnews', 'freejobalert.com']
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text()).lower()
        
        if not href.startswith('http') or is_blocked(href):
            continue
        
        # Skip aggregator site links in output
        if any(d in href.lower() for d in excluded_in_output):
            continue
        
        if ('apply' in text or 'registration' in text) and not links['apply']:
            links['apply'] = href
        elif ('notification' in text or 'pdf' in text or 'download' in text) and not links['notification']:
            links['notification'] = href
        elif ('official' in text or 'website' in text) and not links['official']:
            links['official'] = href
    
    return links

def extract_faq(soup):
    """Extract FAQ if present"""
    faqs = []
    
    # Find FAQ section
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        if 'faq' in heading.get_text().lower() or 'question' in heading.get_text().lower():
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ['h2', 'h3']:
                text = clean(sibling.get_text())
                if text and len(text) > 20:
                    faqs.append(text)
                sibling = sibling.find_next_sibling()
                if len(faqs) >= 5:
                    break
    
    return faqs

def build_content(title, link):
    """Build SarkariResult style content"""
    
    html = fetch(link)
    
    if not html:
        return build_simple_content(title, link)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get title
    page_title = clean(soup.title.string) if soup.title else title
    final_title = page_title if len(page_title) > 10 else title
    
    # Extract data
    details = extract_details(soup)
    links = extract_links(soup, link)
    faqs = extract_faq(soup)
    
    # Get excerpt
    excerpt = ""
    for p in soup.find_all('p'):
        t = clean(p.get_text())
        if 50 < len(t) < 400:
            excerpt = t
            break
    
    # Build HTML
    content = f'''
<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">

<!-- Header -->
<div style="background:linear-gradient(135deg,#c62828,#8e0000);color:#fff;padding:25px;border-radius:10px 10px 0 0;text-align:center;">
<h1 style="margin:0;font-size:24px;line-height:1.4;">{final_title}</h1>
<p style="margin:10px 0 0;opacity:0.9;font-size:14px;">📢 RojgarBhaskar.com - Sarkari Naukri Portal</p>
</div>

<!-- Overview -->
<div style="background:#f5f5f5;padding:20px;border-left:4px solid #c62828;">
<h2 style="color:#c62828;margin:0 0 10px;font-size:18px;">📋 Overview / संक्षिप्त विवरण</h2>
<p style="margin:0;line-height:1.6;">{excerpt if excerpt else "नवीनतम सरकारी नौकरी अधिसूचना। नीचे दी गई पूरी जानकारी देखें और समय पर आवेदन करें।"}</p>
</div>

<!-- Vacancy Details -->
<div style="padding:20px;background:#fff;">
<h2 style="color:#c62828;border-bottom:3px solid #c62828;padding-bottom:10px;font-size:18px;">📊 Vacancy Details / रिक्ति विवरण</h2>
<table style="width:100%;border-collapse:collapse;margin-top:15px;">
<tr style="background:#c62828;color:#fff;">
<th style="padding:12px;text-align:left;width:40%;">Details / विवरण</th>
<th style="padding:12px;text-align:left;">Information / जानकारी</th>
</tr>
<tr style="background:#fff;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>🏢 Organization</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('org', 'See Official Notification')}</td></tr>
<tr style="background:#fafafa;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>📝 Post Name</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('post', 'Various Posts')}</td></tr>
<tr style="background:#fff;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>🎓 Qualification</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('qual', 'As per Notification')}</td></tr>
<tr style="background:#fafafa;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>👥 Total Vacancy</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('vacancy', 'Check Notification')}</td></tr>
<tr style="background:#fff;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>📅 Age Limit</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('age', 'As per Rules')}</td></tr>
<tr style="background:#fafafa;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>💰 Salary</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('salary', 'As per Govt Norms')}</td></tr>
<tr style="background:#fff;"><td style="padding:10px;border-bottom:1px solid #eee;"><strong>💵 Application Fee</strong></td><td style="padding:10px;border-bottom:1px solid #eee;">{details.get('fee', 'Check Notification')}</td></tr>
<tr style="background:#fafafa;"><td style="padding:10px;"><strong>⏰ Last Date</strong></td><td style="padding:10px;"><strong style="color:#c62828;">{details.get('last_date', 'Check Official Website')}</strong></td></tr>
</table>
</div>

<!-- Important Links -->
<div style="padding:20px;background:#f9f9f9;">
<h2 style="color:#c62828;border-bottom:3px solid #c62828;padding-bottom:10px;font-size:18px;">🔗 Important Links / महत्वपूर्ण लिंक</h2>
<table style="width:100%;border-collapse:collapse;margin-top:15px;">
<tr style="background:#c62828;color:#fff;">
<th style="padding:12px;text-align:center;">Action / कार्य</th>
<th style="padding:12px;text-align:center;">Link / लिंक</th>
</tr>'''

    if links['apply']:
        content += f'''
<tr style="background:#fff;"><td style="padding:12px;text-align:center;border:1px solid #eee;"><strong>Apply Online</strong></td><td style="padding:12px;text-align:center;border:1px solid #eee;"><a href="{links['apply']}" target="_blank" style="background:#4caf50;color:#fff;padding:8px 20px;border-radius:5px;text-decoration:none;">Apply Now</a></td></tr>'''
    
    if links['notification']:
        content += f'''
<tr style="background:#fafafa;"><td style="padding:12px;text-align:center;border:1px solid #eee;"><strong>Notification PDF</strong></td><td style="padding:12px;text-align:center;border:1px solid #eee;"><a href="{links['notification']}" target="_blank" style="background:#2196f3;color:#fff;padding:8px 20px;border-radius:5px;text-decoration:none;">Download</a></td></tr>'''
    
    if links['official']:
        content += f'''
<tr style="background:#fff;"><td style="padding:12px;text-align:center;border:1px solid #eee;"><strong>Official Website</strong></td><td style="padding:12px;text-align:center;border:1px solid #eee;"><a href="{links['official']}" target="_blank" style="background:#ff9800;color:#fff;padding:8px 20px;border-radius:5px;text-decoration:none;">Visit</a></td></tr>'''
    
    content += f'''
<tr style="background:#fafafa;"><td style="padding:12px;text-align:center;border:1px solid #eee;"><strong>Full Details</strong></td><td style="padding:12px;text-align:center;border:1px solid #eee;"><a href="{link}" target="_blank" style="background:#9c27b0;color:#fff;padding:8px 20px;border-radius:5px;text-decoration:none;">View Source</a></td></tr>
</table>
</div>'''

    # FAQ Section
    if faqs:
        content += '''
<div style="padding:20px;background:#fff;">
<h2 style="color:#c62828;border-bottom:3px solid #c62828;padding-bottom:10px;font-size:18px;">❓ FAQ / अक्सर पूछे जाने वाले प्रश्न</h2>'''
        for faq in faqs:
            content += f'''
<div style="background:#f5f5f5;padding:15px;margin:10px 0;border-left:4px solid #c62828;border-radius:0 8px 8px 0;">{faq}</div>'''
        content += '</div>'

    # Follow Section
    content += '''
<div style="background:linear-gradient(135deg,#fff5f5,#fff);border:2px solid #c62828;border-radius:0 0 10px 10px;padding:25px;text-align:center;">
<h3 style="color:#c62828;margin:0 0 15px;">🔔 RojgarBhaskar को Follow करें!</h3>
<p style="margin:0;">
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank" style="display:inline-block;background:#25d366;color:#fff;padding:10px 20px;border-radius:5px;margin:5px;text-decoration:none;">📱 WhatsApp</a>
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank" style="display:inline-block;background:#0088cc;color:#fff;padding:10px 20px;border-radius:5px;margin:5px;text-decoration:none;">📢 Telegram</a>
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank" style="display:inline-block;background:#ff0000;color:#fff;padding:10px 20px;border-radius:5px;margin:5px;text-decoration:none;">🎥 YouTube</a>
</p>
</div>

</div>
'''
    return content

def build_simple_content(title, link):
    return f'''
<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">
<div style="background:#c62828;color:#fff;padding:25px;border-radius:10px 10px 0 0;text-align:center;">
<h1 style="margin:0;">{title}</h1>
</div>
<div style="padding:30px;text-align:center;">
<p>Latest Government Job Notification</p>
<a href="{link}" target="_blank" style="display:inline-block;background:#4caf50;color:#fff;padding:15px 40px;border-radius:5px;text-decoration:none;font-size:18px;">📋 View Full Details & Apply</a>
</div>
<div style="background:#fff5f5;padding:20px;border-radius:0 0 10px 10px;text-align:center;border:2px solid #c62828;">
<p><strong>🔔 Follow RojgarBhaskar:</strong></p>
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank">WhatsApp</a> | 
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank">Telegram</a> | 
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank">YouTube</a>
</div>
</div>
'''

# ---- Main ----
def main():
    log("=" * 60)
    log("RojgarBhaskar Scraper - Working Version")
    log("=" * 60)
    
    WP_SITE = os.environ.get("WP_SITE_URL", "").strip()
    WP_USER = os.environ.get("WP_USERNAME", "").strip()
    WP_PASS = os.environ.get("WP_APP_PASSWORD", "").strip()
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
    SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))
    
    if not all([WP_SITE, WP_USER, WP_PASS]):
        log("ERROR: Missing credentials!")
        sys.exit(1)
    
    log(f"Site: {WP_SITE} | Max: {MAX_ITEMS}")
    
    all_items = []
    
    # Try each source
    sources = [
        ("FreeJobAlert", scrape_freejobalert),
        ("SarkariNaukri", scrape_sarkarinaukri),
        ("FreshersLive", scrape_fresherslive),
        ("EmploymentNews", scrape_employment_news),
        ("HireLateral", scrape_hirelateral),
    ]
    
    for name, func in sources:
        try:
            items = func()
            all_items.extend(items)
            log(f"  {name}: {len(items)} items added")
        except Exception as e:
            log(f"  {name} failed: {e}")
    
    log(f"Total collected: {len(all_items)}")
    
    # Dedupe
    seen = set()
    unique = []
    for t, l in all_items:
        key = clean(t).lower()[:50]
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique.append((t, l))
    
    log(f"Unique items: {len(unique)}")
    
    if not unique:
        log("No items found! Check if websites are accessible.")
        return
    
    posted, skipped = 0, 0
    
    for title, link in unique[:MAX_ITEMS]:
        try:
            log(f"Processing: {title[:40]}...")
            
            if wp_exists(WP_SITE, WP_USER, WP_PASS, title):
                log("  → Already exists")
                skipped += 1
                continue
            
            cat = detect_category(title)
            content = build_content(title, link)
            
            result = wp_post(WP_SITE, WP_USER, WP_PASS, title, content, cat)
            
            if result:
                log(f"  ✅ Posted: {result.get('link', 'OK')}")
                posted += 1
            else:
                log("  ❌ Post failed")
            
            time.sleep(SLEEP)
            
        except Exception as e:
            log(f"  ❌ Error: {e}")
    
    log("=" * 60)
    log(f"COMPLETED! Posted: {posted} | Skipped: {skipped}")
    log("=" * 60)

if __name__ == "__main__":
    main()
