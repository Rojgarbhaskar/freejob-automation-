import requests
from bs4 import BeautifulSoup

# -------------------------
# WordPress POST function
# -------------------------
def wp_post(site, user, app_pass, title, content):
    url = f"{site}/wp-json/wp/v2/posts"

    data = {
        "title": title,
        "content": content,
        "status": "publish"
    }

    r = requests.post(url, json=data, auth=(user, app_pass))

    if r.status_code in (200, 201):
        print("POSTED:", title)
    else:
        print("WP ERROR:", r.status_code, r.text)


# -------------------------
# SCRAPER 1: SarkariResult CM
# -------------------------
def scrape_sarkariresult_cm():
    try:
        url = "https://sarkariresult.com.cm/"
        soup = BeautifulSoup(requests.get(url).text, "lxml")

        items = soup.select("div.center-result a")[:5]

        data = []
        for a in items:
            title = a.text.strip()
            link = a.get("href")
            if link.startswith("/"):
                link = url + link.lstrip("/")
            data.append((title, link))

        return data
    except Exception as e:
        print("Error CM:", e)
        return []


# -------------------------
# SCRAPER 2: SarkariResult IM
# -------------------------
def scrape_sarkariresult_im():
    try:
        url = "https://sarkariresult.com.im/"
        soup = BeautifulSoup(requests.get(url).text, "lxml")

        items = soup.select("div.center-result a")[:5]

        data = []
        for a in items:
            title = a.text.strip()
            link = a.get("href")
            if link.startswith("/"):
                link = url + link.lstrip("/")
            data.append((title, link))

        return data
    except Exception as e:
        print("Error IM:", e)
        return []


# -------------------------
# SCRAPER 3: FreeJobAlert
# -------------------------
def scrape_freejobalert():
    try:
        url = "https://www.freejobalert.com/latest-notifications/"
        soup = BeautifulSoup(requests.get(url).text, "lxml")

        links = soup.select("h3 a, h2 a")[:5]

        data = []
        for a in links:
            title = a.text.strip()
            link = a.get("href")
            data.append((title, link))

        return data
    except Exception as e:
        print("FJA Error:", e)
        return []


# -------------------------
# MERGE ALL SOURCES
# -------------------------
def collect_all():
    all_items = []
    all_items += scrape_sarkariresult_cm()
    all_items += scrape_sarkariresult_im()
    all_items += scrape_freejobalert()

    # Remove duplicates
    unique = []
    seen = set()
    for t, l in all_items:
        if t not in seen:
            unique.append((t, l))
            seen.add(t)

    return unique[:10]   # Limit 10 max


# -------------------------
# FULL PROCESS
# -------------------------
def run_scraper():
    import os
    WP_SITE = os.environ.get("WP_SITE_URL")
    WP_USER = os.environ.get("WP_USERNAME")
    WP_PASS = os.environ.get("WP_APP_PASSWORD")

    posts = collect_all()

    for title, link in posts:
        content = f"""
<h2>{title}</h2>
<p><b>Official Link:</b> <a href="{link}" target="_blank">{link}</a></p>

<hr>
<b>Follow for Latest Updates:</b><br>
<a href="https://www.whatsapp.com/channel/0029VbB4TL0DuMRYJlLPQN47">WhatsApp</a> |
<a href="https://t.me/+gjQIJRUl1a8wYzM1">Telegram</a> |
<a href="https://www.youtube.com/@Rojgar_bhaskar">YouTube</a>
"""

        wp_post(WP_SITE, WP_USER, WP_PASS, title, content)


if __name__ == "__main__":
    run_scraper()

