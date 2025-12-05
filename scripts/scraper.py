#!/usr/bin/env python3
"""
RojgarBhaskar Auto-Poster
Multi-site job scraper with WordPress auto-posting
Scrapes from: FreeJobAlert, SarkariResult IM/CM, Testbook
"""

import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from datetime import datetime
from typing import List, Tuple, Optional

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

WP_SITE_URL = os.environ.get("WP_SITE_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "10"))
SLEEP_BETWEEN_POSTS = int(os.environ.get("SLEEP_BETWEEN_POSTS", "3"))
USER_AGENT = "Mozilla/5.0 (compatible; RojgarBhaskarBot/1.0; +https://rojgarbhaskar.com)"

# Validate Environment Variables
if not all([WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD]):
    logger.error("❌ Missing environment variables!")
    exit(1)

# Website Configurations
SITES_CONFIG = {
    "freejobalert.com": {
        "name": "Free Job Alert",
        "categories": [
            "https://www.freejobalert.com/latest-notifications/",
            "https://www.freejobalert.com/bank-jobs/",
            "https://www.freejobalert.com/railway-jobs/",
            "https://www.freejobalert.com/police-jobs/",
            "https://www.freejobalert.com/ssc-jobs/",
            "https://www.freejobalert.com/defence-jobs/",
        ],
        "type": "freejobalert"
    },
    "sarkariresult.com.im": {
        "name": "Sarkari Result IM",
        "categories": ["https://sarkariresult.com.im/"],
        "type": "sarkariresult"
    },
    "sarkariresult.com.cm": {
        "name": "Sarkari Result CM",
        "categories": ["https://sarkariresult.com.cm/"],
        "type": "sarkariresult"
    },
    "testbook.com": {
        "name": "Testbook",
        "categories": [
            "https://testbook.com/career",
            "https://testbook.com/blog/category/jobs",
        ],
        "type": "testbook"
    }
}

# ============================================================================
# SCRAPER CLASS
# ============================================================================

class JobScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.stats = {
            "total_processed": 0,
            "total_posted": 0,
            "total_skipped": 0,
            "total_errors": 0,
        }
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch webpage content"""
        try:
            logger.info(f"📥 Fetching: {url}")
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"❌ Fetch error: {str(e)}")
            self.stats["total_errors"] += 1
            return None
    
    def extract_links_freejobalert(self, html: str, base_url: str) -> List[str]:
        """Extract job links from Free Job Alert"""
        try:
            soup = BeautifulSoup(html, "lxml")
            links = []
            
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a['href']
                
                if any(x in text for x in ["get details", "read more", "details", "apply"]):
                    full_url = urljoin(base_url, href)
                    if full_url not in links:
                        links.append(full_url)
            
            if not links:
                for a in soup.find_all("a", href=True):
                    href = a['href']
                    if "freejobalert.com" in href and href.count("-") >= 2:
                        full_url = urljoin(base_url, href)
                        if full_url not in links:
                            links.append(full_url)
            
            logger.info(f"🔗 Found {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Extract error: {str(e)}")
            return []
    
    def extract_links_sarkariresult(self, html: str, base_url: str) -> List[str]:
        """Extract job links from Sarkari Result"""
        try:
            soup = BeautifulSoup(html, "lxml")
            links = []
            
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                href = a['href']
                
                keywords = ["apply", "notification", "details", "read more", "job", "vacancy"]
                if any(x in text for x in keywords):
                    full_url = urljoin(base_url, href)
                    if full_url not in links:
                        links.append(full_url)
            
            logger.info(f"🔗 Found {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Extract error: {str(e)}")
            return []
    
    def extract_links_testbook(self, html: str, base_url: str) -> List[str]:
        """Extract job links from Testbook"""
        try:
            soup = BeautifulSoup(html, "lxml")
            links = []
            
            for a in soup.find_all("a", href=True):
                href = a['href']
                
                if any(x in href for x in ["/blog/", "/news/", "/career", "/jobs"]):
                    full_url = urljoin(base_url, href)
                    if full_url not in links:
                        links.append(full_url)
            
            logger.info(f"🔗 Found {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Extract error: {str(e)}")
            return []
    
    def parse_article(self, html: str, site_type: str) -> Tuple[str, str]:
        """Parse article content"""
        try:
            soup = BeautifulSoup(html, "lxml")
            
            # Extract Title
            title = ""
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)[:100]
            
            # Extract Content
            content_selectors = [".entry-content", ".post-content", ".blog-content", "article", ".content"]
            content_element = None
            
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break
            
            if content_element:
                for tag in content_element(["script", "style", "noscript"]):
                    tag.decompose()
                content_html = str(content_element)
            else:
                paragraphs = soup.find_all("p")
                if paragraphs:
                    content_html = "\n".join(
                        f"<p>{p.get_text(strip=True)}</p>" 
                        for p in paragraphs[:50]
                    )
                else:
                    content_html = "<p>Content not available</p>"
            
            return title or "Job Post", content_html
        except Exception as e:
            logger.error(f"Parse error: {str(e)}")
            return "Job Post", "<p>Error parsing content</p>"
    
    def wp_post_exists(self, title: str) -> bool:
        """Check if post already exists in WordPress"""
        try:
            url = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
            params = {
                "search": title,
                "per_page": 5,
                "_fields": "id,title"
            }
            
            response = self.session.get(
                url,
                params=params,
                auth=(WP_USERNAME, WP_APP_PASSWORD),
                timeout=10
            )
            
            if response.status_code == 200:
                posts = response.json()
                for post in posts:
                    post_title = post.get("title", {}).get("rendered", "").strip().lower()
                    if post_title == title.strip().lower():
                        logger.info(f"⏭️  Post exists: {title[:50]}...")
                        self.stats["total_skipped"] += 1
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Check exists error: {str(e)}")
            return False
    
    def wp_create_post(self, title: str, content: str, source: str) -> bool:
        """Create post in WordPress"""
        try:
            if not title or not content:
                logger.warning("❌ Empty title or content")
                return False
            
            url = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
            
            post_data = {
                "title": title[:200],
                "content": f"{content}\n\n<hr/>\n<p><strong>📌 Source:</strong> {source}</p>",
                "status": "publish",
                "categories": [1]
            }
            
            response = self.session.post(
                url,
                json=post_data,
                auth=(WP_USERNAME, WP_APP_PASSWORD),
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                post_link = response_data.get("link", "")
                logger.info(f"✅ Posted: {title[:50]}... ({post_link})")
                self.stats["total_posted"] += 1
                return True
            else:
                logger.error(f"❌ WordPress error {response.status_code}")
                self.stats["total_errors"] += 1
                return False
        except Exception as e:
            logger.error(f"❌ Create post error: {str(e)}")
            self.stats["total_errors"] += 1
            return False
    
    def process_category(self, category_url: str, site_name: str, site_type: str) -> int:
        """Process single category and scrape jobs"""
        logger.info(f"\n🔄 Processing: {category_url}")
        
        html = self.fetch_page(category_url)
        if not html:
            return 0
        
        if site_type == "freejobalert":
            links = self.extract_links_freejobalert(html, category_url)
        elif site_type == "sarkariresult":
            links = self.extract_links_sarkariresult(html, category_url)
        elif site_type == "testbook":
            links = self.extract_links_testbook(html, category_url)
        else:
            links = self.extract_links_freejobalert(html, category_url)
        
        if not links:
            logger.warning(f"⚠️  No links found")
            return 0
        
        posted_count = 0
        for link in links[:MAX_ITEMS]:
            self.stats["total_processed"] += 1
            
            logger.info(f"\n📄 Processing article {self.stats['total_processed']}...")
            
            article_html = self.fetch_page(link)
            if not article_html:
                continue
            
            title, content = self.parse_article(article_html, site_type)
            
            if not title or not content:
                logger.warning("⚠️  Empty title or content, skipping...")
                continue
            
            if self.wp_post_exists(title):
                continue
            
            if self.wp_create_post(title, content, site_name):
                posted_count += 1
            
            time.sleep(SLEEP_BETWEEN_POSTS)
        
        return posted_count
    
    def run(self) -> None:
        """Main execution"""
        logger.info("=" * 70)
        logger.info("🚀 RojgarBhaskar Auto-Poster Started")
        logger.info(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📊 Max items per category: {MAX_ITEMS}")
        logger.info("=" * 70)
        
        total_posted = 0
        
        for site_key, site_config in SITES_CONFIG.items():
            site_name = site_config["name"]
            site_type = site_config["type"]
            categories = site_config["categories"]
            
            logger.info(f"\n{'='*70}")
            logger.info(f"🌐 Processing: {site_name}")
            logger.info(f"{'='*70}")
            
            for category_url in categories:
                try:
                    posted = self.process_category(category_url, site_name, site_type)
                    total_posted += posted
                except Exception as e:
                    logger.error(f"❌ Category error: {str(e)}")
                    self.stats["total_errors"] += 1
        
        logger.info(f"\n{'='*70}")
        logger.info("✅ SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"📊 Total Processed: {self.stats['total_processed']}")
        logger.info(f"✅ Total Posted: {self.stats['total_posted']}")
        logger.info(f"⏭️  Total Skipped: {self.stats['total_skipped']}")
        logger.info(f"❌ Total Errors: {self.stats['total_errors']}")
        logger.info(f"{'='*70}")
        logger.info("🎉 Scraper Finished!")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    scraper = JobScraper()
    scraper.run()
