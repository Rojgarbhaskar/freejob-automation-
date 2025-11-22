#!/bin/bash
set -euo pipefail

echo "========================================"
echo "RojgarBhaskar Auto-Poster Starting..."
echo "========================================"

# Check required environment variables
: "${WP_SITE_URL:?ERROR: WP_SITE_URL not set}"
: "${WP_USERNAME:?ERROR: WP_USERNAME not set}"
: "${WP_APP_PASSWORD:?ERROR: WP_APP_PASSWORD not set}"

# Optional variables with defaults
MAX_ITEMS=${MAX_ITEMS:-10}
SLEEP_BETWEEN_POSTS=${SLEEP_BETWEEN_POSTS:-3}

echo "Config:"
echo "  - WP Site: [HIDDEN]"
echo "  - Max Items: ${MAX_ITEMS}"
echo "  - Sleep Between Posts: ${SLEEP_BETWEEN_POSTS}s"

# Install Python dependencies
echo ""
echo "Installing dependencies..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install requests beautifulsoup4 --quiet

echo "Dependencies installed."
echo ""

# Run the scraper
echo "Running scraper..."
python3 scripts/scraper.py

echo ""
echo "========================================"
echo "Script Completed!"
echo "========================================"
