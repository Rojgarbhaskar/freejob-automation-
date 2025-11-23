#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Advanced Scraper - STRUCTURED DATA
- Extracts tables in structured format
- Proper FAQ section
- Important Links table
- Complete SarkariResult-style layout
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
]
TIMEOUT = 20

# ---- Category IDs ----
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
    19: ["result", "merit list", "cut off", "scorecard"],
    21: ["answer key", "answer sheet"],
    22: ["syllabus", "exam pattern"],
    23: ["admission", "counselling"],
    18: ["recruitment", "vacancy", "bharti", "jobs", "notification"]
}

# ---- Utility ----
def log(msg):
    print(f"[LOG] {msg}")

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8"
    }

def fetch(url):
    try:
        log(f"Fetching: {url[:60]}...")
        time.sleep(random.uniform(0.5, 1.5))
        r = requests.get(url, headers=get_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        log(f"  Error: {e}")
        return ""

def clean(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def make_absolute(url, base):
    if not url or url.startswith(('http://', 'https://')):
        return url
    return urljoin(base, url)

def is_aggregator(url):
    agg = ['freejobalert', 'sarkariexam', 'rojgarlive', 'sarkarinaukri', 'fresherslive', 'sarkariresult.com.cm']
    return any(d in url.lower() for d in agg)

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
        return r.json() if r.status_code in (200, 201) else None
    except Exception as e:
        log(f"WP Error: {e}")
        return None

# ========== SCRAPERS ==========

def scrape_freejobalert():
    items = []
    base = "https://www.freejobalert.com"
    url = f"{base}/latest-notifications/"
    
    html = fetch(url)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for table in soup.find_all('table'):
        for a in table.find_all('a', href=True):
            href = a.get('href', '')
            text = clean(a.get_text())
            if text and len(text) > 15 and 'freejobalert.com' in href:
                if '/latest-notifications/' not in href and '/category/' not in href:
                    items.append((text, make_absolute(href, base)))
    
    seen = set()
    unique = [item for item in items if item[1] not in seen and not seen.add(item[1])]
    log(f"FreeJobAlert: {len(unique)} items")
    return unique[:15]

def scrape_sarkariresult_cm():
    items = []
    base = "https://www.sarkariresult.com.cm"
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        if text and len(text) > 15:
            keywords = ['recruitment', 'vacancy', 'admit', 'result']
            if any(k in text.lower() for k in keywords):
                items.append((text, make_absolute(href, base)))
    
    seen = set()
    unique = [item for item in items if item[1] not in seen and not seen.add(item[1])]
    log(f"SarkariResult.cm: {len(unique)} items")
    return unique[:15]

def scrape_sarkarinaukri():
    items = []
    base = "https://www.sarkarinaukri.com"
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        if text and len(text) > 15 and 'sarkarinaukri.com' in href:
            items.append((text, href))
    
    seen = set()
    unique = [item for item in items if item[1] not in seen and not seen.add(item[1])]
    log(f"SarkariNaukri: {len(unique)} items")
    return unique[:10]

def scrape_fresherslive():
    items = []
    base = "https://www.fresherslive.com"
    html = fetch(f"{base}/government-jobs")
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        text = clean(a.get_text())
        href = a.get('href', '')
        if text and len(text) > 15 and 'fresherslive.com' in href:
            if '/government-jobs/' in href:
                items.append((text, href))
    
    seen = set()
    unique = [item for item in items if item[1] not in seen and not seen.add(item[1])]
    log(f"FreshersLive: {len(unique)} items")
    return unique[:10]

# ========== ADVANCED EXTRACTION ==========

def extract_title(soup, fallback):
    """Extract actual job title"""
    # Try H1/H2 with job keywords
    for tag in ['h1', 'h2']:
        for h in soup.find_all(tag):
            text = clean(h.get_text())
            if 20 < len(text) < 200:
                keywords = ['recruitment', 'vacancy', 'admit', 'result', 'notification']
                if any(k in text.lower() for k in keywords):
                    return text
    
    # Try page title
    if soup.title:
        title = clean(soup.title.string)
        for remove in ['- FreeJobAlert', '- Sarkari', '| FreshersLive']:
            title = title.replace(remove, '').strip()
        if len(title) > 20:
            return title
    
    return fallback


def extract_structured_data(soup):
    """Extract all structured data from page"""
    data = {
        'overview': '',
        'important_dates': [],
        'vacancy_details': [],
        'age_limit': [],
        'application_fee': [],
        'eligibility': [],
        'links': [],
        'faq': []
    }
    
    # Get overview/excerpt
    for p in soup.find_all('p'):
        text = clean(p.get_text())
        if 80 < len(text) < 500:
            data['overview'] = text
            break
    
    # Extract tables
    for table in soup.find_all('table'):
        rows = []
        for tr in table.find_all('tr'):
            cells = [clean(td.get_text()) for td in tr.find_all(['td', 'th'])]
            if len(cells) >= 2 and cells[0] and cells[1]:
                rows.append(cells)
        
        if not rows:
            continue
        
        # Categorize table based on content
        table_text = str(table).lower()
        first_row_text = ' '.join([str(c).lower() for c in rows[0]]).lower()
        
        if any(k in table_text or k in first_row_text for k in ['important date', 'date', 'timeline', 'schedule']):
            data['important_dates'].extend(rows)
        elif any(k in table_text or k in first_row_text for k in ['vacancy', 'post', 'department', 'organization']):
            data['vacancy_details'].extend(rows)
        elif any(k in table_text or k in first_row_text for k in ['age limit', 'age', 'maximum age', 'minimum age']):
            data['age_limit'].extend(rows)
        elif any(k in table_text or k in first_row_text for k in ['fee', 'application fee', 'payment']):
            data['application_fee'].extend(rows)
        elif any(k in table_text or k in first_row_text for k in ['eligibility', 'qualification', 'education']):
            data['eligibility'].extend(rows)
        else:
            # General vacancy details
            data['vacancy_details'].extend(rows)
    
    # Extract official links (NO aggregator sites)
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not href.startswith('http') or is_aggregator(href):
            continue
        
        # Categorize links
        text_lower = text.lower()
        link_type = None
        
        if any(k in text_lower for k in ['apply', 'online form', 'registration']):
            link_type = 'Apply Online'
        elif any(k in text_lower for k in ['notification', 'pdf', 'download']):
            link_type = 'Download Notification'
        elif any(k in text_lower for k in ['admit card', 'hall ticket']):
            link_type = 'Download Admit Card'
        elif any(k in text_lower for k in ['result', 'scorecard']):
            link_type = 'Check Result'
        elif any(k in text_lower for k in ['official', 'website']):
            link_type = 'Official Website'
        
        if link_type and not any(l[0] == link_type for l in data['links']):
            data['links'].append((link_type, href, text))
    
    # Extract FAQ
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        h_text = heading.get_text().lower()
        if 'faq' in h_text or 'question' in h_text or 'प्रश्न' in h_text:
            sibling = heading.find_next_sibling()
            count = 0
            while sibling and count < 10:
                if sibling.name in ['h2', 'h3']:
                    break
                text = clean(sibling.get_text())
                if text and len(text) > 30:
                    data['faq'].append(text)
                sibling = sibling.find_next_sibling()
                count += 1
    
    return data


# ========== CONTENT BUILDER - STRUCTURED FORMAT ==========

def build_structured_content(title, link):
    """Build highly structured content like SarkariResult"""
    
    html = fetch(link)
    if not html:
        return build_simple_content(title), title
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get actual title
    actual_title = extract_title(soup, title)
    
    # Extract all structured data
    data = extract_structured_data(soup)
    
    # Build HTML with proper structure
    content = f'''
<style>
.sr-container{{max-width:900px;margin:0 auto;font-family:Arial,sans-serif;}}
.sr-header{{background:linear-gradient(135deg,#c62828,#8e0000);color:#fff;padding:25px;text-align:center;border-radius:8px 8px 0 0;}}
.sr-header h1{{margin:0;font-size:22px;line-height:1.4;}}
.sr-header p{{margin:10px 0 0;opacity:0.9;font-size:13px;}}
.sr-section{{padding:20px;background:#fff;margin-bottom:0;}}
.sr-section-alt{{padding:20px;background:#f9f9f9;margin-bottom:0;}}
.sr-title{{color:#c62828;font-size:18px;font-weight:bold;border-bottom:3px solid #c62828;padding-bottom:10px;margin:0 0 15px;}}
.sr-table{{width:100%;border-collapse:collapse;margin-top:10px;}}
.sr-table th{{background:#c62828;color:#fff;padding:12px;text-align:left;font-weight:bold;}}
.sr-table td{{padding:10px 12px;border:1px solid #e0e0e0;}}
.sr-table tr:nth-child(even){{background:#fafafa;}}
.sr-table tr:hover{{background:#fff3f3;}}
.sr-btn{{display:inline-block;padding:8px 20px;background:#4caf50;color:#fff;text-decoration:none;border-radius:5px;font-weight:bold;}}
.sr-btn-blue{{background:#2196f3;}}
.sr-btn-orange{{background:#ff9800;}}
.sr-btn-purple{{background:#9c27b0;}}
.sr-btn-red{{background:#f44336;}}
.sr-faq{{background:#f5f5f5;padding:15px;margin:10px 0;border-left:4px solid #c62828;border-radius:0 8px 8px 0;}}
.sr-overview{{background:#f5f5f5;padding:20px;border-left:4px solid #c62828;margin-bottom:0;}}
</style>

<div class="sr-container">

<!-- Header -->
<div class="sr-header">
<h1>{actual_title}</h1>
<p>📢 RojgarBhaskar.com - Sarkari Naukri Portal</p>
</div>

<!-- Overview -->
<div class="sr-overview">
<h2 class="sr-title">📋 Overview / संक्षिप्त विवरण</h2>
<p style="margin:0;line-height:1.6;">{data['overview'] if data['overview'] else "नवीनतम सरकारी नौकरी अधिसूचना। नीचे दी गई सभी जानकारी ध्यान से पढ़ें और अंतिम तिथि से पहले आवेदन करें।"}</p>
</div>
'''

    # Important Dates Section
    if data['important_dates']:
        content += '''
<div class="sr-section">
<h2 class="sr-title">📅 Important Dates / महत्वपूर्ण तिथियाँ</h2>
<table class="sr-table">
<tr><th>Event / घटना</th><th>Date / तिथि</th></tr>'''
        for row in data['important_dates'][:8]:
            if len(row) >= 2:
                content += f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>'
        content += '</table></div>'
    
    # Vacancy Details Section
    if data['vacancy_details']:
        content += '''
<div class="sr-section-alt">
<h2 class="sr-title">📊 Vacancy Details / रिक्ति विवरण</h2>
<table class="sr-table">
<tr><th>Details / विवरण</th><th>Information / जानकारी</th></tr>'''
        for row in data['vacancy_details'][:12]:
            if len(row) >= 2:
                content += f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>'
        content += '</table></div>'
    
    # Age Limit Section
    if data['age_limit']:
        content += '''
<div class="sr-section">
<h2 class="sr-title">🎂 Age Limit / आयु सीमा</h2>
<table class="sr-table">
<tr><th>Category / श्रेणी</th><th>Age Limit / आयु सीमा</th></tr>'''
        for row in data['age_limit'][:6]:
            if len(row) >= 2:
                content += f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>'
        content += '</table></div>'
    
    # Application Fee Section
    if data['application_fee']:
        content += '''
<div class="sr-section-alt">
<h2 class="sr-title">💰 Application Fee / आवेदन शुल्क</h2>
<table class="sr-table">
<tr><th>Category / श्रेणी</th><th>Fee / शुल्क</th></tr>'''
        for row in data['application_fee'][:6]:
            if len(row) >= 2:
                content += f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>'
        content += '</table></div>'
    
    # Eligibility Section
    if data['eligibility']:
        content += '''
<div class="sr-section">
<h2 class="sr-title">🎓 Eligibility / योग्यता</h2>
<table class="sr-table">
<tr><th>Post / पद</th><th>Qualification / योग्यता</th></tr>'''
        for row in data['eligibility'][:8]:
            if len(row) >= 2:
                content += f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>'
        content += '</table></div>'
    
    # Important Links Section
    if data['links']:
        content += '''
<div class="sr-section-alt">
<h2 class="sr-title">🔗 Some Useful Important Links / कुछ उपयोगी महत्वपूर्ण लिंक</h2>
<table class="sr-table">
<tr><th style="text-align:center;">Action / कार्य</th><th style="text-align:center;">Link / लिंक</th></tr>'''
        
        btn_classes = {
            'Apply Online': 'sr-btn',
            'Download Notification': 'sr-btn-blue',
            'Download Admit Card': 'sr-btn-orange',
            'Check Result': 'sr-btn-purple',
            'Official Website': 'sr-btn-red'
        }
        
        for link_type, href, text in data['links'][:8]:
            btn_class = btn_classes.get(link_type, 'sr-btn-blue')
            content += f'''
<tr>
<td style="text-align:center;padding:15px;"><strong>{link_type}</strong></td>
<td style="text-align:center;padding:15px;"><a href="{href}" target="_blank" class="{btn_class}">Click Here</a></td>
</tr>'''
        content += '</table></div>'
    
    # FAQ Section
    if data['faq']:
        content += '''
<div class="sr-section">
<h2 class="sr-title">❓ FAQ / अक्सर पूछे जाने वाले प्रश्न</h2>'''
        for i, faq in enumerate(data['faq'][:10], 1):
            content += f'<div class="sr-faq"><strong>Q{i}:</strong> {faq}</div>'
        content += '</div>'
    
    content += '</div>'
    
    return content, actual_title


def build_simple_content(title):
    return f'''
<div style="font-family:Arial;max-width:900px;margin:0 auto;">
<div style="background:#c62828;color:#fff;padding:25px;text-align:center;border-radius:8px;">
<h1 style="margin:0;">{title}</h1>
<p style="margin:10px 0 0;">RojgarBhaskar.com</p>
</div>
<div style="padding:30px;text-align:center;background:#f9f9f9;">
<p>Latest Government Job Notification</p>
</div>
</div>
''', title


# ========== MAIN ==========

def main():
    log("=" * 60)
    log("RojgarBhaskar Advanced Scraper - Structured Data")
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
    
    sources = [
        ("FreeJobAlert", scrape_freejobalert),
        ("SarkariResult.cm", scrape_sarkariresult_cm),
        ("SarkariNaukri", scrape_sarkarinaukri),
        ("FreshersLive", scrape_fresherslive),
    ]
    
    for name, func in sources:
        try:
            items = func()
            all_items.extend(items)
            log(f"  {name}: {len(items)} items")
        except Exception as e:
            log(f"  {name} error: {e}")
    
    log(f"Total: {len(all_items)}")
    
    # Dedupe
    seen = set()
    unique = []
    for t, l in all_items:
        key = clean(t).lower()[:50]
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique.append((t, l))
    
    log(f"Unique: {len(unique)}")
    
    if not unique:
        log("No items!")
        return
    
    posted, skipped = 0, 0
    
    for orig_title, link in unique[:MAX_ITEMS]:
        try:
            log(f"Processing: {orig_title[:40]}...")
            
            # Build structured content
            content, actual_title = build_structured_content(orig_title, link)
            
            final_title = actual_title if len(actual_title) > 15 else orig_title
            log(f"  Title: {final_title[:45]}")
            
            if wp_exists(WP_SITE, WP_USER, WP_PASS, final_title):
                log("  → Exists, skip")
                skipped += 1
                continue
            
            cat = detect_category(final_title)
            log(f"  Category: {cat}")
            
            result = wp_post(WP_SITE, WP_USER, WP_PASS, final_title, content, cat)
            
            if result:
                log(f"  ✅ Posted: {result.get('link', 'OK')}")
                posted += 1
            else:
                log("  ❌ Failed")
            
            time.sleep(SLEEP)
            
        except Exception as e:
            log(f"  ❌ Error: {e}")
    
    log("=" * 60)
    log(f"DONE! Posted: {posted} | Skipped: {skipped}")
    log("=" * 60)

if __name__ == "__main__":
    main()
