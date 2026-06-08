# EN2BGTERM — Hugo site

Static rebuild of the EN→BG IT-terminology dictionary. One crawlable page per term, per-page SEO + `DefinedTerm` JSON-LD, accessible bilingual markup, and full-text search  via [Pagefind](https://pagefind.app/).

## Build

```bash
bash scripts/build.sh          # parse data → hugo build → pagefind index → ./public
hugo server                    # local dev (handles baseURL; run build_data.py first)
```

`scripts/build.sh` runs three stages:

1. **`scripts/build_data.py`** (Python stdlib) parses the source markdown into
   `data/terms.json` — splits the dictionary tables into terms, derives unique URL slugs
   (disambiguating collisions like `(to) access` / `(an) access`), and merges matching
   usage examples from `examples.md`.
2. **`hugo --minify --cleanDestinationDir`** — the content adapter
   `content/terms/_content.gotmpl` emits one page per term from `data/terms.json`.
3. **`npx pagefind --site public`** — builds the search index over the rendered term pages
   (`<article data-pagefind-body>`).

Serve `./public` over HTTP (Pagefind needs HTTP, not `file://`).

## Data source (dev vs. prod)

The parser reads its inputs from `$DICT_SRC` / `$EXAMPLES_SRC`

```bash
DICT_SRC=https://raw.githubusercontent.com/<org>/<repo>/master/README.md \
EXAMPLES_SRC=https://raw.githubusercontent.com/<org>/<repo>/master/examples.md \
bash scripts/build.sh
```

`data/terms.json`, `public/`, and `resources/` are generated and git-ignored.

## Config

Set the real `baseURL` and `params.github` in `hugo.toml` before deploying.
