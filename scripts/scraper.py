name: RojgarBhaskar Auto-Poster

on:
  # Manual trigger
  workflow_dispatch:
  
  # Auto run every 30 minutes
  schedule:
    - cron: "*/30 * * * *"

jobs:
  scrape-and-post:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Make script executable
        run: chmod +x scripts/run.sh
      
      - name: Run Scraper
        env:
          WP_SITE_URL: ${{ secrets.WP_SITE_URL }}
          WP_USERNAME: ${{ secrets.WP_USERNAME }}
          WP_APP_PASSWORD: ${{ secrets.WP_APP_PASSWORD }}
          MAX_ITEMS: "5"
          SLEEP_BETWEEN_POSTS: "3"
        run: ./scripts/run.sh
