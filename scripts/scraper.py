#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Government Job Auto-Scraper (Single URL Worker + Auto-Post)
Usage: python scrape.py <SOURCE_URL>
Output: JSON object with Post Status
"""

import sys
import json
import re
import os
import requests
from bs4 import BeautifulSoup
import argparse

# ---- Config ----
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ---- User's Category IDs ----
CATEGORIES = {
    "latest_jobs": 18,
    "results": 19,
    "admit_card": 20,
    "answer_key": 21,
    "syllabus": 22,
    "admission": 23
}

# ---- Category Detection Logic ----
def get_category_id(title):
    t = title.lower()
    if any(x in t for x in ["admit card", "hall ticket", "call letter"]):
        return CATEGORIES["admit_card"], "Admit Card"
    elif any(x in t for x in ["result", "merit list", "cut off", "score card"]):
        return CATEGORIES["results"], "Result"
    elif any(x in t for x in ["syllabus", "exam pattern"]):
        return CATEGORIES["syllabus"], "Syllabus"
    elif any(x in t for x in ["answer key", "answer sheet"]):
        return CATEGORIES["answer_key"], "Answer Key"
    elif any(x in t for x in ["admission", "counselling"]):
        return CATEGORIES["admission"], "Admission"
    else:
        return CATEGORIES["latest_jobs"], "Latest Jobs"

# ---- WordPress Functions ----
def wp_post(title, content, cat_id):
    site = os.environ.get("WP_SITE_URL")
    user = os.environ.get("WP_USERNAME")
    pwd = os.environ.get("WP_APP_PASSWORD")

    if not all([site, user, pwd]):
        return {"error": "Missing WP Credentials"}

    try:
        url = f"{site.rstrip('/')}/wp-json/wp/v2/posts"
        
        # Check if exists first
        check = requests.get(url, params={"search": title[:30], "per_page": 1}, auth=(user, pwd), timeout=15)
        if check.status_code == 200 and len(check.json()) > 0:
            # Check for exact match or close match
            for p in check.json():
                if clean_text(p['title']['rendered']).lower() == clean_text(title).lower():
                    return {"status": "skipped", "reason": "Already exists", "link": p['link']}

        # Post new
        data = {
            "title": title,
            "content": content,
            "status": "publish",
            "categories": [cat_id]
        }
        r = requests.post(url, json=data, auth=(user, pwd), timeout=30)
        if r.status_code in (200, 201):
            return {"status": "success", "id": r.json().get('id'), "link": r.json().get('link')}
        else:
            return {"status": "failed", "code": r.status_code, "msg": r.text}
            
    except Exception as e:
        return {"status": "error", "msg": str(e)}

# ---- Cleaning ----
def clean_text(text):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_html(soup):
    for tag in soup(['script', 'style', 'iframe', 'noscript', 'header', 'footer', 'nav', 'aside']):
        tag.decompose()
    return soup

# ---- Extraction Heuristics ----
def extract_table_data(soup, keywords):
    data = []
    for kw in keywords:
        elements = soup.find_all(string=re.compile(kw, re.I))
        for el in elements:
            parent = el.find_parent(['tr', 'li', 'div'])
            if parent:
                if parent.name == 'tr':
                    cells = parent.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = clean_text(cells[0].get_text())
                        val = clean_text(cells[1].get_text())
                        data.append((key, val))
                elif parent.name == 'li':
                    text = clean_text(parent.get_text())
                    if ':' in text:
                        parts = text.split(':', 1)
                        data.append((parts[0].strip(), parts[1].strip()))
                    else:
                        data.append((text, ""))
    
    unique_data = []
    seen = set()
    for k, v in data:
        if k not in seen and len(k) < 50:
            seen.add(k)
            unique_data.append((k, v))
    return unique_data

def extract_links(soup, base_url):
    links = []
    keywords = ['apply', 'notification', 'official', 'download', 'click here', 'login', 'registration', 'admit card', 'result']
    seen_urls = set()
    
    for a in soup.find_all('a', href=True):
        text = clean_text(a.get_text()).lower()
        href = a['href']
        
        if not href.startswith('http'): continue # Skip relative for now or handle if needed

        if any(k in text for k in keywords):
            if any(x in href for x in ['facebook', 'twitter', 'whatsapp', 'telegram']): continue
            
            if href not in seen_urls:
                label = clean_text(a.get_text())
                if len(label) < 3: label = "Click Here"
                links.append((label, href))
                seen_urls.add(href)
    return links

# ---- HTML Generator ----
def generate_sarkari_html(title, intro, dates, fees, age, vacancy, eligibility, links):
    RED = "#ab1e1e"
    GREEN = "#008000"
    BLUE = "#000080"
    
    html = f"""
<div style="font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; border: 2px solid {RED};">

    <!-- Header -->
    <div style="text-align: center; background-color: {RED}; color: white; padding: 15px;">
        <h1 style="margin: 0; font-size: 22px; font-weight: bold;">{title}</h1>
        <p style="margin: 8px 0 0; font-size: 14px;">{intro}</p>
    </div>

    <!-- Dates & Fees -->
    <table style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="width: 50%; vertical-align: top; border-right: 2px solid {RED}; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center;">Important Dates</div>
                <div style="padding: 10px;">
                    <ul style="list-style: none; padding: 0;">
                        {''.join([f'<li style="margin-bottom: 5px;"><strong>{k}:</strong> {v}</li>' for k, v in dates]) or '<li>Check Notification</li>'}
                    </ul>
                </div>
            </td>
            <td style="width: 50%; vertical-align: top; padding: 0;">
                <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center;">Application Fee</div>
                <div style="padding: 10px;">
                    <ul style="list-style: none; padding: 0;">
                        {''.join([f'<li style="margin-bottom: 5px;"><strong>{k}:</strong> {v}</li>' for k, v in fees]) or '<li>Check Notification</li>'}
                    </ul>
                </div>
            </td>
        </tr>
    </table>

    <!-- Age Limit -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {GREEN}; color: white; font-weight: bold; padding: 8px; text-align: center;">Age Limit</div>
        <div style="padding: 10px;">
            <ul style="list-style: none; padding: 0;">
                {''.join([f'<li style="margin-bottom: 5px;"><strong>{k}:</strong> {v}</li>' for k, v in age]) or '<li>As per Rules</li>'}
            </ul>
        </div>
    </div>

    <!-- Vacancy & Eligibility -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {BLUE}; color: white; font-weight: bold; padding: 8px; text-align: center;">Vacancy & Eligibility Details</div>
        <div style="padding: 10px;">
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Post Name</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Post</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Eligibility</th>
                </tr>
                {''.join([f'<tr><td style="border: 1px solid #ddd; padding: 8px;">{k}</td><td style="border: 1px solid #ddd; padding: 8px;">{v}</td><td style="border: 1px solid #ddd; padding: 8px;">Check Notification</td></tr>' for k, v in vacancy]) or '<tr><td colspan="3" style="padding:8px;text-align:center;">Details in Notification</td></tr>'}
            </table>
        </div>
    </div>

    <!-- Important Links -->
    <div style="border-top: 2px solid {RED};">
        <div style="background-color: {RED}; color: white; font-weight: bold; padding: 8px; text-align: center;">Important Links</div>
        <div style="padding: 10px;">
            <table style="width: 100%; border-collapse: collapse;">
                {''.join([f'<tr><td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{l[0]}</td><td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;"><a href="{l[1]}" target="_blank" style="background-color: {RED}; color: white; padding: 5px 15px; text-decoration: none; border-radius: 3px;">Click Here</a></td></tr>' for l in links])}
            </table>
        </div>
    </div>

</div>
"""
    return html

# ---- Main Scraper ----
def scrape(url):
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        soup = clean_html(soup)
        
        h1 = soup.find('h1')
        title = clean_text(h1.get_text()) if h1 else clean_text(soup.title.string)
        
        intro = ""
        for p in soup.find_all('p'):
            text = clean_text(p.get_text())
            if len(text) > 50:
                intro = text
                break
        
        dates = extract_table_data(soup, ['date', 'start', 'end', 'last', 'exam'])
        fees = extract_table_data(soup, ['fee', 'application', 'general', 'obc', 'sc/st'])
        age = extract_table_data(soup, ['age', 'limit', 'born'])
        
        vacancy = []
        for table in soup.find_all('table'):
            headers = [clean_text(th.get_text()).lower() for th in table.find_all(['th', 'td'])]
            if any('post' in h for h in headers) and any('total' in h for h in headers):
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        vacancy.append((clean_text(cols[0].get_text()), clean_text(cols[-1].get_text())))
                break
        
        links = extract_links(soup, url)
        
        # Determine Category ID
        cat_id, cat_name = get_category_id(title)
        
        post_html = generate_sarkari_html(title, intro, dates, fees, age, vacancy, [], links)
        prompt = f"Banner for {title}, Government Job, Bold Typography, Blue and Red Theme, Professional News Style, 4k Resolution"
        
        # Auto Post
        post_result = wp_post(title, post_html, cat_id)
        
        return {
            "post_title": title,
            "post_category": cat_name,
            "category_id": cat_id,
            "post_html": post_html,
            "featured_image_prompt": prompt,
            "wp_status": post_result
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a government job URL")
    parser.add_argument("url", help="The URL to scrape")
    args = parser.parse_args()
    
    result = scrape(args.url)
    print(json.dumps(result, indent=4))
