#!/usr/bin/env bash
# Serve the frontend standalone on port 3000
set -e
cd "$(dirname "$0")"
echo "Kayan Console UI  ->  http://localhost:3000"
echo "API (backend)     ->  http://localhost:8000"
python3 -m http.server 3000
