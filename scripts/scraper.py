#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RojgarBhaskar Scraper - SarkariResult Style
- Exact SarkariResult design
- No FreeJobAlert links in output
- FAQ section extraction
- Proper category assignment
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hi-IN,hi;q=0.9,en-US;q=0.8,en;q=0.7",
}
TIMEOUT = 25

# ---- RojgarBhaskar Category IDs ----
CATEGORIES = {
    "latest_jobs": 18,
    "results": 19,
    "admit_card": 20,
    "answer_key": 21,
    "syllabus": 22,
    "admission": 23,
    "tools": 24
}

# Keywords for category detection
CATEGORY_KEYWORDS = {
    20: ["admit card", "admit", "hall ticket", "call letter", "e-admit"],
    19: ["result", "merit list", "cut off", "cutoff", "score card", "scorecard"],
    21: ["answer key", "answerkey", "answer sheet", "objection"],
    22: ["syllabus", "exam pattern", "exam syllabus"],
    23: ["admission", "counselling", "counseling", "seat allotment"],
    18: ["recruitment", "vacancy", "bharti", "jobs", "notification", "apply", "online form"]
}

# Blocked domains - links from these will be removed
BLOCKED_DOMAINS = [
    "freejobalert.com",
    "sarkariexam.com", 
    "rojgarlive.com",
    "sarkarijobfind.com",
    "naukri.com"
]

# ---- Utility Functions ----
def log(msg):
    print(f"[LOG] {msg}")

def fetch(url):
    try:
        log(f"Fetching: {url}")
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        log(f"Fetch error: {e}")
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

def is_blocked_link(url):
    """Check if URL is from blocked domain"""
    url_lower = url.lower()
    for domain in BLOCKED_DOMAINS:
        if domain in url_lower:
            return True
    return False

def detect_category(title):
    """Detect category from title keywords"""
    title_lower = title.lower()
    
    # Check in priority order
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title_lower:
                return cat_id
    
    # Default to Latest Jobs
    return CATEGORIES["latest_jobs"]

# ---- WordPress Functions ----
def wp_post_exists(site, user, pwd, title):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        params = {"search": title[:50], "per_page": 10}
        r = requests.get(url, params=params, auth=(user, pwd), timeout=TIMEOUT)
        if r.status_code == 200:
            for post in r.json():
                existing = post.get("title", {}).get("rendered", "")
                if clean(existing).lower() == clean(title).lower():
                    return True
    except Exception as e:
        log(f"WP search error: {e}")
    return False

def wp_create_post(site, user, pwd, title, content, category_id):
    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        data = {
            "title": title,
            "content": content,
            "status": "publish",
            "categories": [category_id]
        }
        r = requests.post(url, json=data, auth=(user, pwd), timeout=30)
        if r.status_code in (200, 201):
            return r.json()
        else:
            log(f"WP error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"WP exception: {e}")
    return None

# ---- Scrapers ----

def scrape_freejobalert():
    """Scrape FreeJobAlert for job links"""
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
            
            if not text or len(text) < 15:
                continue
            if any(skip in text.lower() for skip in ['view more', 'read more', 'click here']):
                continue
            if 'freejobalert.com' in href and '/latest-notifications/' not in href:
                items.append((text, href))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"FreeJobAlert: {len(unique)} items")
    return unique[:15]

def scrape_sarkariexam():
    """Scrape SarkariExam"""
    items = []
    base = "https://www.sarkariexam.com"
    
    html = fetch(base)
    if not html:
        return items
    
    soup = BeautifulSoup(html, 'html.parser')
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text())
        
        if not text or len(text) < 15:
            continue
        if any(skip in text.lower() for skip in ['view more', 'read more', 'home']):
            continue
        
        full_url = make_absolute(href, base)
        if 'sarkariexam.com' in full_url and '/category/' not in full_url:
            items.append((text, full_url))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"SarkariExam: {len(unique)} items")
    return unique[:10]

def scrape_rojgarlive():
    """Scrape RojgarLive"""
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
        
        if not text or len(text) < 15:
            continue
        
        full_url = make_absolute(href, base)
        if 'rojgarlive.com' in full_url and full_url != url:
            if '/category/' not in full_url:
                items.append((text, full_url))
    
    seen = set()
    unique = []
    for t, l in items:
        if l not in seen:
            seen.add(l)
            unique.append((t, l))
    
    log(f"RojgarLive: {len(unique)} items")
    return unique[:10]

# ---- Content Extraction ----

def extract_tables(soup):
    """Extract and clean tables from page"""
    tables = []
    for table in soup.find_all('table'):
        # Skip navigation/menu tables
        text = table.get_text()
        if len(text) < 50:
            continue
        tables.append(table)
    return tables[:3]  # Max 3 tables

def extract_faq(soup):
    """Extract FAQ section if exists"""
    faq_items = []
    
    # Method 1: Look for FAQ heading and following content
    faq_headings = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'FAQ|frequently asked|सवाल|प्रश्न', re.I))
    
    for heading in faq_headings:
        # Get next siblings until next heading
        sibling = heading.find_next_sibling()
        while sibling and sibling.name not in ['h2', 'h3', 'h4']:
            if sibling.name in ['p', 'div']:
                text = clean(sibling.get_text())
                if text and len(text) > 20:
                    faq_items.append(text)
            sibling = sibling.find_next_sibling()
    
    # Method 2: Look for Q&A pattern
    if not faq_items:
        for strong in soup.find_all(['strong', 'b']):
            text = clean(strong.get_text())
            if text.startswith(('Q.', 'Q:', 'Que', 'प्रश्न', 'सवाल')):
                q = text
                # Find answer
                parent = strong.find_parent(['p', 'div'])
                if parent:
                    a = clean(parent.get_text())
                    if a and a != q:
                        faq_items.append(f"<strong>{q}</strong><br>{a}")
    
    # Method 3: Schema FAQ
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get('@type') == 'FAQPage':
                for item in data.get('mainEntity', []):
                    q = item.get('name', '')
                    a = item.get('acceptedAnswer', {}).get('text', '')
                    if q and a:
                        faq_items.append(f"<strong>Q: {q}</strong><br>A: {a}")
        except:
            pass
    
    return faq_items[:10]

def extract_official_links(soup, source_url):
    """Extract only official/government links, block aggregator sites"""
    links = {
        "apply": None,
        "notification": None,
        "official": None,
        "admit": None,
        "result": None
    }
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = clean(a.get_text()).lower()
        
        # Skip if empty or blocked
        if not href or not href.startswith('http'):
            continue
        if is_blocked_link(href):
            continue
        
        # Detect link type
        if ('apply' in text or 'online' in text or 'registration' in text) and not links["apply"]:
            links["apply"] = (clean(a.get_text()), href)
        elif ('notification' in text or 'pdf' in text or 'download' in text) and not links["notification"]:
            links["notification"] = (clean(a.get_text()), href)
        elif ('official' in text or 'website' in text) and not links["official"]:
            links["official"] = (clean(a.get_text()), href)
        elif ('admit' in text or 'hall ticket' in text) and not links["admit"]:
            links["admit"] = (clean(a.get_text()), href)
        elif ('result' in text or 'score' in text) and not links["result"]:
            links["result"] = (clean(a.get_text()), href)
    
    return links

def extract_job_details(soup):
    """Extract job details from tables"""
    details = {}
    
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = clean(cells[0].get_text()).lower()
                value = clean(cells[1].get_text())
                
                if not value or value.lower() in ['na', 'n/a', '-', '']:
                    continue
                
                if any(k in label for k in ['organization', 'department', 'board', 'संस्था', 'विभाग']):
                    details['org'] = value
                elif any(k in label for k in ['post', 'name', 'पद']):
                    details['post'] = value
                elif any(k in label for k in ['qualification', 'eligibility', 'योग्यता']):
                    details['qual'] = value
                elif any(k in label for k in ['vacancy', 'total', 'रिक्ति', 'पद संख्या']):
                    details['vacancy'] = value
                elif any(k in label for k in ['age', 'आयु']):
                    details['age'] = value
                elif any(k in label for k in ['last date', 'अंतिम तिथि', 'closing']):
                    details['last_date'] = value
                elif any(k in label for k in ['fee', 'शुल्क', 'application fee']):
                    details['fee'] = value
                elif any(k in label for k in ['salary', 'pay', 'वेतन']):
                    details['salary'] = value
    
    return details

# ---- SarkariResult Style Content Builder ----

def build_sarkari_style_content(title, source_link):
    """Build exact SarkariResult style content"""
    
    html = fetch(source_link)
    
    if not html:
        return build_fallback_content(title, source_link)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract data
    page_title = clean(soup.title.string) if soup.title else title
    final_title = page_title if len(page_title) > 10 else title
    
    details = extract_job_details(soup)
    links = extract_official_links(soup, source_link)
    faq_items = extract_faq(soup)
    
    # Get excerpt
    excerpt = ""
    for p in soup.find_all('p'):
        text = clean(p.get_text())
        if 50 < len(text) < 400:
            excerpt = text
            break

    # ========== BUILD SARKARIRESULT STYLE HTML ==========
    
    content = '''
<style>
.sr-box{background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 15px rgba(0,0,0,0.1);margin-bottom:20px}
.sr-header{background:linear-gradient(135deg,#d32f2f,#b71c1c);color:#fff;padding:20px;text-align:center}
.sr-header h1{margin:0;font-size:22px;line-height:1.4}
.sr-section{padding:20px}
.sr-section-title{color:#d32f2f;font-size:18px;font-weight:bold;border-bottom:3px solid #d32f2f;padding-bottom:10px;margin-bottom:15px}
.sr-table{width:100%;border-collapse:collapse}
.sr-table th{background:#d32f2f;color:#fff;padding:12px;text-align:left;font-weight:bold}
.sr-table td{padding:10px 12px;border-bottom:1px solid #eee}
.sr-table tr:nth-child(even){background:#fafafa}
.sr-table tr:hover{background:#fff3f3}
.sr-btn{display:inline-block;padding:10px 25px;border-radius:5px;text-decoration:none;font-weight:bold;margin:5px;transition:all 0.3s}
.sr-btn-green{background:#4caf50;color:#fff}
.sr-btn-green:hover{background:#388e3c}
.sr-btn-blue{background:#2196f3;color:#fff}
.sr-btn-blue:hover{background:#1976d2}
.sr-btn-orange{background:#ff9800;color:#fff}
.sr-btn-orange:hover{background:#f57c00}
.sr-btn-purple{background:#9c27b0;color:#fff}
.sr-btn-purple:hover{background:#7b1fa2}
.sr-links-table th{background:#d32f2f;color:#fff;padding:12px;text-align:center}
.sr-links-table td{padding:12px;text-align:center;border:1px solid #eee}
.sr-follow{background:linear-gradient(135deg,#fff5f5,#fff);border:2px solid #d32f2f;border-radius:8px;padding:20px;text-align:center;margin-top:20px}
.sr-faq{background:#f9f9f9;padding:15px;border-left:4px solid #d32f2f;margin-bottom:10px;border-radius:0 8px 8px 0}
</style>

<div class="sr-box">

<!-- Header -->
<div class="sr-header">
<h1>'''
    
    content += f'''{final_title}</h1>
<p style="margin:10px 0 0 0;opacity:0.9;">RojgarBhaskar.com - Latest Govt Jobs Portal</p>
</div>

<!-- Overview -->
<div class="sr-section">
<div class="sr-section-title">📋 Overview / संक्षिप्त विवरण</div>
<p>{excerpt if excerpt else "Latest Government Job Notification. नीचे दी गई जानकारी देखें और अंतिम तिथि से पहले आवेदन करें।"}</p>
</div>

<!-- Vacancy Details -->
<div class="sr-section">
<div class="sr-section-title">📊 Vacancy Details / रिक्ति विवरण</div>
<table class="sr-table">
<tr>
<th style="width:40%">विवरण / Details</th>
<th>जानकारी / Information</th>
</tr>'''
    
    # Add details rows
    detail_rows = [
        ("🏢 Organization / संस्था", details.get('org', 'Official Notification देखें')),
        ("📝 Post Name / पद का नाम", details.get('post', 'Various Posts')),
        ("🎓 Qualification / योग्यता", details.get('qual', 'As per Notification')),
        ("👥 Total Vacancy / कुल पद", details.get('vacancy', 'Check Notification')),
        ("📅 Age Limit / आयु सीमा", details.get('age', 'As per Rules')),
        ("💰 Application Fee / आवेदन शुल्क", details.get('fee', 'Check Notification')),
        ("💵 Salary / वेतन", details.get('salary', 'As per Govt Norms')),
        ("⏰ Last Date / अंतिम तिथि", details.get('last_date', 'Check Official Website'))
    ]
    
    for label, value in detail_rows:
        content += f'''
<tr>
<td><strong>{label}</strong></td>
<td>{value}</td>
</tr>'''
    
    content += '''
</table>
</div>

<!-- Important Links -->
<div class="sr-section">
<div class="sr-section-title">🔗 Important Links / महत्वपूर्ण लिंक</div>
<table class="sr-table sr-links-table">
<tr>
<th style="width:50%">Description / विवरण</th>
<th>Link / लिंक</th>
</tr>'''
    
    # Add links - only official ones, no aggregator links
    if links["apply"]:
        content += f'''
<tr>
<td><strong>📝 Apply Online / ऑनलाइन आवेदन</strong></td>
<td><a href="{links["apply"][1]}" target="_blank" rel="noopener" class="sr-btn sr-btn-green">Apply Now</a></td>
</tr>'''
    
    if links["notification"]:
        content += f'''
<tr>
<td><strong>📄 Download Notification / अधिसूचना</strong></td>
<td><a href="{links["notification"][1]}" target="_blank" rel="noopener" class="sr-btn sr-btn-blue">Download PDF</a></td>
</tr>'''
    
    if links["admit"]:
        content += f'''
<tr>
<td><strong>🎫 Admit Card / प्रवेश पत्र</strong></td>
<td><a href="{links["admit"][1]}" target="_blank" rel="noopener" class="sr-btn sr-btn-orange">Download</a></td>
</tr>'''
    
    if links["result"]:
        content += f'''
<tr>
<td><strong>📊 Result / परिणाम</strong></td>
<td><a href="{links["result"][1]}" target="_blank" rel="noopener" class="sr-btn sr-btn-purple">Check Result</a></td>
</tr>'''
    
    if links["official"]:
        content += f'''
<tr>
<td><strong>🌐 Official Website / आधिकारिक वेबसाइट</strong></td>
<td><a href="{links["official"][1]}" target="_blank" rel="noopener" class="sr-btn sr-btn-blue">Visit Website</a></td>
</tr>'''
    
    content += '''
</table>
</div>'''
    
    # FAQ Section
    if faq_items:
        content += '''

<!-- FAQ Section -->
<div class="sr-section">
<div class="sr-section-title">❓ FAQ / अक्सर पूछे जाने वाले प्रश्न</div>'''
        
        for faq in faq_items:
            content += f'''
<div class="sr-faq">{faq}</div>'''
        
        content += '''
</div>'''
    
    # Follow Section
    content += '''

<!-- Follow Section -->
<div class="sr-follow">
<h3 style="color:#d32f2f;margin-top:0;">🔔 RojgarBhaskar को Follow करें - Latest Jobs के लिए!</h3>
<p style="margin:15px 0;">
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank" class="sr-btn" style="background:#25d366;color:#fff;">📱 WhatsApp Channel</a>
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank" class="sr-btn" style="background:#0088cc;color:#fff;">📢 Telegram Group</a>
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank" class="sr-btn" style="background:#ff0000;color:#fff;">🎥 YouTube Channel</a>
</p>
<p style="color:#666;font-size:14px;margin-bottom:0;">Daily Updates के लिए हमारे साथ जुड़े रहें!</p>
</div>

</div>
<!-- End RojgarBhaskar Post -->
'''
    
    return content

def build_fallback_content(title, link):
    """Fallback when page fetch fails"""
    return f'''
<div style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 15px rgba(0,0,0,0.1);">
<div style="background:linear-gradient(135deg,#d32f2f,#b71c1c);color:#fff;padding:20px;text-align:center;">
<h2 style="margin:0;">{title}</h2>
</div>
<div style="padding:20px;">
<p>Latest Government Job Notification. Complete details के लिए नीचे दिए गए link पर click करें।</p>
<p style="text-align:center;margin:20px 0;">
<a href="{link}" target="_blank" style="background:#4caf50;color:#fff;padding:12px 30px;border-radius:5px;text-decoration:none;font-weight:bold;">📋 View Complete Details</a>
</p>
<hr style="margin:20px 0;border:none;border-top:1px solid #eee;">
<div style="background:#fff5f5;padding:15px;border-radius:8px;text-align:center;border:2px solid #d32f2f;">
<p style="margin:0;"><strong>🔔 RojgarBhaskar को Follow करें:</strong></p>
<p style="margin:10px 0 0 0;">
<a href="https://whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47" target="_blank">📱 WhatsApp</a> | 
<a href="https://t.me/+gjQIJRUl1a8wYzM1" target="_blank">📢 Telegram</a> | 
<a href="https://www.youtube.com/@Rojgar_bhaskar" target="_blank">🎥 YouTube</a>
</p>
</div>
</div>
</div>
'''

# ---- Main ----

def main():
    log("=" * 60)
    log("RojgarBhaskar Scraper - SarkariResult Style")
    log("=" * 60)
    
    WP_SITE = os.environ.get("WP_SITE_URL", "").strip()
    WP_USER = os.environ.get("WP_USERNAME", "").strip()
    WP_PASS = os.environ.get("WP_APP_PASSWORD", "").strip()
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
    SLEEP = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))
    
    if not all([WP_SITE, WP_USER, WP_PASS]):
        log("ERROR: Missing WP credentials!")
        sys.exit(1)
    
    log(f"Site: {WP_SITE} | Max: {MAX_ITEMS}")
    
    # Collect items
    all_items = []
    
    try:
        all_items.extend(scrape_freejobalert())
    except Exception as e:
        log(f"FreeJobAlert error: {e}")
    
    try:
        all_items.extend(scrape_sarkariexam())
    except Exception as e:
        log(f"SarkariExam error: {e}")
    
    try:
        all_items.extend(scrape_rojgarlive())
    except Exception as e:
        log(f"RojgarLive error: {e}")
    
    log(f"Total: {len(all_items)} items")
    
    # Deduplicate
    seen = set()
    unique = []
    for t, l in all_items:
        key = clean(t).lower()[:50]
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique.append((t, l))
    
    log(f"Unique: {len(unique)} items")
    
    # Process
    posted, skipped = 0, 0
    
    for title, link in unique[:MAX_ITEMS]:
        try:
            log(f"Processing: {title[:45]}...")
            
            if wp_post_exists(WP_SITE, WP_USER, WP_PASS, title):
                log("  → Exists, skip")
                skipped += 1
                continue
            
            # Detect category
            cat_id = detect_category(title)
            log(f"  → Category: {cat_id}")
            
            # Build content
            content = build_sarkari_style_content(title, link)
            
            # Post
            result = wp_create_post(WP_SITE, WP_USER, WP_PASS, title, content, cat_id)
            
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
