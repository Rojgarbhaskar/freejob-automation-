#!/bin/bash

echo "===== MULTI-WEBSITE SCRAPER START ====="

# Python install
echo "Installing Python dependencies..."
pip install requests beautifulsoup4 lxml --quiet

echo "Running scraper..."
python3 scripts/scraper.py

echo "===== SCRAPER FINISHED ====="
