#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Scraper - FIXED VERSION
- Proper job title extraction (not "Get Details")
- Correct category assignment
- No footer social links
- Sources: FreeJobAlert, SarkariNaukri, FreshersLive, SarkariResult.com.cm
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
        time.sleep(random.uniform(0.5, 1.5))
        r = requests.get(url, headers=get_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        log(f"  → OK ({len(r.text)} bytes)")
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

def is_aggregator_link(url):
    """Check if URL is from job aggregator site"""
    aggregators = ['freejobalert.com', 'sarkariexam.com', 'rojgarlive.com', 
                   'sarkarinaukri.com', 'fresherslive.com', 'sarkariresult.com.cm']
    for d in aggregators:
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

# ========== SCRAPERS ==========

def scrape_freejobalert():
    """
    FreeJobAlert Scraper - Get actual job titles, not "Get Details"
    """
    items = []
    base = "https://www.freejobalert.com"
    url = f"{base}/latest-notifications/"
    
    log("FreeJobAlert: Fetching...")
    html = fetch(url)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # FreeJobAlert structure: Tables with job listings
    # Each row has: Date | Job Title (with link) | Post Info
    
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            
            # Look for cells with job links
            for cell in cells:
                links = cell.find_all('a', href=True)
                for a in links:
                    href = a.get('href', '')
                    text = clean(a.get_text())
                    
                    # Skip navigation/category links
                    if not text or len(text) < 15:
                        continue
                    if any(skip in text.lower() for skip in ['view all', 'click here', 'read more', 'get details']):
                        continue
                    if any(skip in href for skip in ['/category/', '/tag/', '/page/', '/author/', '/latest-notifications/']):
                        continue
                    
                    # Valid job detail link
                    if 'freejobalert.com' in href:
                        full_url = make_absolute(href, base)
                        items.append((text, full_url))
    
    # Also check for links outside tables
    if len(items) < 5:
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = clean(a.get_text())
            
            if not text or len(text) < 20:
                continue
            if 'recruitment' in text.lower() or 'vacancy' in text.lower() or 'notification' in text.lower():
                if 'freejobalert.com' in href and '/latest-notifications/' not in href:
                    full_url = make_absolute(href, base)
                    items.append((text, full_url))
    
    # Deduplicate
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen and len(t) > 15:
            seen.add(l)
            unique.append((t, l))
    
    log(f"FreeJobAlert: {len(unique)} items")
    return unique[:15]


def scrape_sarkariresult_cm():
    """
    SarkariResult.com.cm Scraper
    """
    items = []
    base = "https://www.sarkariresult.com.cm"
    
    log("SarkariResult.cm: Fetching...")
    html = fetch(base)
    if not html:
        # Try with trailing slash
        html = fetch(base + "/")
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find job links
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 15:
            continue
        
        # Skip navigation
        skip_words = ['home', 'about', 'contact', 'privacy', 'disclaimer', 'view more', 'read more']
        if any(skip in text.lower() for skip in skip_words):
            continue
        
        # Job related content
        job_keywords = ['recruitment', 'vacancy', 'admit', 'result', 'notification', 'apply', 'online form', 'bharti']
        if any(kw in text.lower() for kw in job_keywords):
            full_url = make_absolute(href, base)
            items.append((text, full_url))
    
    # Deduplicate
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"SarkariResult.cm: {len(unique)} items")
    return unique[:15]


def scrape_sarkarinaukri():
    """SarkariNaukri.com Scraper"""
    items = []
    base = "https://www.sarkarinaukri.com"
    
    log("SarkariNaukri: Fetching...")
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 15:
            continue
        
        skip = ['home', 'about', 'contact', 'privacy', 'disclaimer', 'advertise']
        if any(s in text.lower() for s in skip):
            continue
        
        if 'sarkarinaukri.com' in href:
            items.append((text, href))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen and 'sarkarinaukri.com' in l:
            seen.add(l)
            unique.append((t, l))
    
    log(f"SarkariNaukri: {len(unique)} items")
    return unique[:10]


def scrape_fresherslive():
    """FreshersLive Scraper"""
    items = []
    base = "https://www.fresherslive.com"
    url = f"{base}/government-jobs"
    
    log("FreshersLive: Fetching...")
    html = fetch(url)
    if not html:
        html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 15:
            continue
        
        if 'fresherslive.com' in href:
            if '/government-jobs/' in href or '/central-govt-jobs/' in href:
                items.append((text, href))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"FreshersLive: {len(unique)} items")
    return unique[:10]


# ========== CONTENT EXTRACTION ==========

def extract_job_title_from_page(soup, fallback_title):
    """Extract actual job title from detail page"""
    
    # Method 1: Look for H1/H2 with job-related content
    for tag in ['h1', 'h2']:
        for heading in soup.find_all(tag):
            text = clean(heading.get_text())
            if len(text) > 20 and len(text) < 200:
                # Check if it looks like a job title
                if any(kw in text.lower() for kw in ['recruitment', 'vacancy', 'notification', 'admit', 'result', 'apply']):
                    return text
    
    # Method 2: Page title
    if soup.title:
        title = clean(soup.title.string)
        # Remove site name from title
        for remove in ['- FreeJobAlert', '- Sarkari Result', '| FreshersLive', '- SarkariNaukri']:
            title = title.replace(remove, '').strip()
        if len(title) > 20:
            return title
    
    # Method 3: Meta title
    meta_title = soup.find('meta', {'property': 'og:title'})
    if meta_title and meta_title.get('content'):
        return clean(meta_title.get('content'))
    
    return fallback_title


def extract_details(soup):
    """Extract job details from page"""
    details = {}
    
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = clean(cells[0].get_text()).lower()
                value = clean(cells[1].get_text())
                
                if not value or len(value) < 2 or value.lower() in ['na', 'n/a', '-']:
                    continue
                
                if any(k in label for k in ['organization', 'department', 'company', 'board', 'संस्था', 'विभाग']):
                    details['org'] = value
                elif any(k in label for k in ['post name', 'position', 'job title', 'पद']):
                    details['post'] = value
                elif any(k in label for k in ['qualification', 'education', 'eligibility', 'योग्यता']):
                    details['qual'] = value
                elif any(k in label for k in ['vacancy', 'total post', 'no of post', 'रिक्ति']):
                    details['vacancy'] = value
                elif any(k in label for k in ['last date', 'closing date', 'अंतिम']):
                    details['last_date'] = value
                elif any(k in label for k in ['salary', 'pay scale', 'वेतन']):
                    details['salary'] = value
                elif any(k in label for k in ['age', 'age limit', 'आयु']):
                    details['age'] = value
                elif any(k in label for k in ['fee', 'application fee', 'शुल्क']):
                    details['fee'] = value
    
    return details


def extract_official_links(soup):
    """Extract only official/government links - NO aggregator links"""
    links = {"apply": None, "notification": None, "official": None}
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text()).lower()
        
        if not href.startswith('http'):
            continue
        
        # Skip aggregator site links
        if is_aggregator_link(href):
            continue
        
        # Only official govt/org links
        if ('apply' in text or 'registration' in text or 'online' in text) and not links['apply']:
            links['apply'] = href
        elif ('notification' in text or 'pdf' in text or 'download' in text) and not links['notification']:
            links['notification'] = href
        elif ('official' in text or 'website' in text) and not links['official']:
            links['official'] = href
    
    return links


def extract_faq(soup):
    """Extract FAQ section if present"""
    faqs = []
    
    # Look for FAQ heading
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        heading_text = heading.get_text().lower()
        if 'faq' in heading_text or 'frequently' in heading_text or 'question' in heading_text:
            # Get following content
            sibling = heading.find_next_sibling()
            count = 0
            while sibling and count < 10:
                if sibling.name in ['h2', 'h3']:
                    break
                text = clean(sibling.get_text())
                if text and len(text) > 30:
                    faqs.append(text)
                sibling = sibling.find_next_sibling()
                count += 1
    
    return faqs[:5]


# ========== CONTENT BUILDER - NO FOOTER SOCIAL ==========

def build_content(title, link):
    """Build SarkariResult style content - NO FOOTER SOCIAL LINKS"""
    
    html = fetch(link)
    
    if not html:
        return build_simple_content(title)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get ACTUAL job title from page
    actual_title = extract_job_title_from_page(soup, title)
    
    # Extract data
    details = extract_details(soup)
    links = extract_official_links(soup)
    faqs = extract_faq(soup)
    
    # Get excerpt
    excerpt = ""
    for p in soup.find_all('p'):
        t = clean(p.get_text())
        if 50 < len(t) < 400:
            excerpt = t
            break
    
    # Build HTML - NO FOOTER SOCIAL LINKS
    content = f'''
<div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;">

<!-- Header -->
<div style="background:linear-gradient(135deg,#c62828,#8e0000);color:#fff;padding:25px;border-radius:10px 10px 0 0;text-align:center;">
<h1 style="margin:0;font-size:22px;line-height:1.4;">{actual_title}</h1>
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
    
    content += '''
</table>
</div>'''

    # FAQ Section
    if faqs:
        content += '''
<div style="padding:20px;background:#fff;">
<h2 style="color:#c62828;border-bottom:3px solid #c62828;padding-bottom:10px;font-size:18px;">❓ FAQ / अक्सर पूछे जाने वाले प्रश्न</h2>'''
        for i, faq in enumerate(faqs, 1):
            content += f'''
<div style="background:#f5f5f5;padding:15px;margin:10px 0;border-left:4px solid #c62828;border-radius:0 8px 8px 0;">{i}. {faq}</div>'''
        content += '</div>'

    # Close main div - NO FOOTER SOCIAL
    content += '''
</div>
'''
    return content, actual_title


def build_simple_content(title):
    """Simple content when page fetch fails - NO FOOTER SOCIAL"""
    content = f'''
<div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;">
<div style="background:#c62828;color:#fff;padding:25px;border-radius:10px;text-align:center;">
<h1 style="margin:0;">{title}</h1>
<p style="margin:10px 0 0;opacity:0.9;">RojgarBhaskar.com - Sarkari Naukri Portal</p>
</div>
<div style="padding:30px;text-align:center;background:#f9f9f9;">
<p>Latest Government Job Notification</p>
<p>नवीनतम सरकारी नौकरी अधिसूचना। पूरी जानकारी के लिए official website देखें।</p>
</div>
</div>
'''
    return content, title


# ========== MAIN ==========

def main():
    log("=" * 60)
    log("RojgarBhaskar Scraper - Fixed Version")
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
    
    # Sources - Only these 4
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
            log(f"  → {name}: {len(items)} items")
        except Exception as e:
            log(f"  → {name} failed: {e}")
    
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
        log("No items found!")
        return
    
    posted, skipped = 0, 0
    
    for orig_title, link in unique[:MAX_ITEMS]:
        try:
            log(f"Processing: {orig_title[:40]}...")
            
            # Build content and get actual title
            result = build_content(orig_title, link)
            content, actual_title = result
            
            # Use actual title for posting
            final_title = actual_title if len(actual_title) > 15 else orig_title
            
            log(f"  → Title: {final_title[:50]}")
            
            # Check if exists
            if wp_exists(WP_SITE, WP_USER, WP_PASS, final_title):
                log("  → Already exists, skipping")
                skipped += 1
                continue
            
            # Detect category from title
            cat = detect_category(final_title)
            log(f"  → Category ID: {cat}")
            
            # Post to WordPress
            result = wp_post(WP_SITE, WP_USER, WP_PASS, final_title, content, cat)
            
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
