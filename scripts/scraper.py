You are an expert Python developer.  
Write a complete production-ready scrape.py script for my Government Job Auto-Scraper.

The script must perform the following:

1. SCRAPING  
   - Input: SOURCE_URL (a single job post URL)  
   - Fetch full page HTML  
   - Extract:
     • Title  
     • Short intro paragraph  
     • Important Dates  
     • Application Fee  
     • Age Limit  
     • Vacancy Details  
     • Eligibility  
     • Important Links  
     • Any tables present on the page  

2. STRUCTURE  
   - Convert scraped data into a Sarkari-Result style post  
   - Follow EXACT structure:

        POST TITLE  
        Short Notification  
        Important Dates (HTML Table)  
        Application Fee (HTML Table)  
        Age Limit (HTML Table)  
        Vacancy Details (HTML Table)  
        Eligibility (HTML Table)  
        Important Links (HTML Table)

3. CATEGORY DETECTION (Auto)  
   - If title contains:  
       “Recruitment / Vacancy / Online Form” → Category: Latest Jobs  
       “Admit Card” → Category: Admit Card  
       “Result” → Category: Result  
       “Syllabus” → Category: Syllabus  
       “Answer Key” → Category: Answer Key  
       Else default: Latest Jobs

4. FEATURED IMAGE PROMPT  
   - At the end, generate an IMAGE PROMPT like:  
     “Banner for PNB LBO Recruitment 2025, 750 Posts, Apply Link, Government Job, Bold, Blue-Red-White theme, Hindi + English, News Thumbnail Style.”

5. OUTPUT (VERY IMPORTANT)
Return a final JSON object containing:
   {
     "post_title": "",
     "post_category": "",
     "post_html": "",
     "featured_image_prompt": ""
   }

6. CODE REQUIREMENTS  
   - Use BeautifulSoup4  
   - Use requests  
   - Use lxml parser  
   - Auto-clean HTML (remove ads/scripts)  
   - Tables must be converted cleanly  
   - No placeholders  
   - Ready to run file

Write the full scrape.py code now.
