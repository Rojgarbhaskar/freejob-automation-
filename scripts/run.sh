#!/bin/bash
set -euo pipefail

echo "Starting multi-site scraper -> WP autopost..."

# Required envs (set as GitHub repository secrets or Actions secrets)
: "${WP_SITE_URL:?Need WP_SITE_URL env (e.g. https://rojgarbhaskar.com)}"
: "${WP_USERNAME:?Need WP_USERNAME env}"
: "${WP_APP_PASSWORD:?Need WP_APP_PASSWORD env}"

MAX_ITEMS=${MAX_ITEMS:-10}
SLEEP_BETWEEN_POSTS=${SLEEP_BETWEEN_POSTS:-3}

echo "WP_SITE_URL: ***"
echo "MAX_ITEMS: ${MAX_ITEMS}"
echo "SLEEP_BETWEEN_POSTS: ${SLEEP_BETWEEN_POSTS}"

# Ensure python + pip are available
if ! python3 -c "import bs4,requests" >/dev/null 2>&1; then
  echo "Installing python dependencies..."
  python3 -m pip install --user --upgrade pip >/dev/null
  python3 -m pip install --user requests beautifulsoup4 lxml >/dev/null
fi

# Run scraper
python3 scripts/scraper.py

echo "Script Completed."
