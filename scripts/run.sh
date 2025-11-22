#!/bin/bash

echo "Running WordPress test post..."

POST_TITLE="GitHub Automation Test"
POST_CONTENT="This is a test post published automatically from GitHub Actions."

WP_RESPONSE=$(curl -X POST "$WP_SITE_URL/wp-json/wp/v2/posts" \
    -u "$WP_USERNAME:$WP_APP_PASSWORD" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$POST_TITLE\",\"content\":\"$POST_CONTENT\",\"status\":\"publish\"}")

echo "WordPress Response:"
echo "$WP_RESPONSE"
