#!/usr/bin/env bash
# Full build: parse data -> Hugo build -> Pagefind index.
#   DICT_SRC=https://raw.githubusercontent.com/<org>/<repo>/master/README.md \
#   EXAMPLES_SRC=https://raw.githubusercontent.com/<org>/<repo>/master/examples.md \
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Testing parser"
python3 scripts/test_build_data.py
# Temporary patch layer (scripts/patches.py); for missing POS markers
[ -f scripts/test_patches.py ] && python3 scripts/test_patches.py

echo "==> Parsing source markdown -> data/terms.json"
python3 scripts/build_data.py

echo "==> Building site with Hugo"
# --cleanDestinationDir removes stale output (e.g. renamed term slugs) so reruns
# don't leave orphaned pages for Pagefind to index.
hugo --gc --minify --cleanDestinationDir

echo "==> Indexing with Pagefind"
npx pagefind --site public

echo "==> Done. Serve ./public over HTTP (Pagefind needs HTTP, not file://)."
