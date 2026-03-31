#!/usr/bin/env bash
# After `docker compose up` (or `-d`), verify the backend health endpoint from the host.
set -euo pipefail
url="${1:-http://localhost:8000/api/health}"
echo "GET $url"
curl -fsS "$url" | head -c 500
echo
