# 📖 docs-crawler
A simple tool that downloads documentation from a provided JSON config and saves it to a chosen output directory. It supports single pages, sitemap expansion, deep crawling with Crawl4AI, and YouTube transcripts.

## Purpose
This tool lets you batch-download docs into a single folder for use in AI IDEs (Cursor, Windsurf, etc.). Instead of attaching many URLs, you can generate a compact docs folder that’s easy to attach as extra context.

## Setup
```shell
uv sync
```

## Running
Use the CLI entrypoint via uv:
```shell
uv run docs-crawler run <json-config-file-path> <output-dir> [--dry-run] [--verbose]
```
Examples:
```shell
uv run docs-crawler run ./tests/docs.json ./documentation
uv run docs-crawler run ./tests/docs.json ./documentation --dry-run
uv run docs-crawler run ./tests/docs.json ./documentation --verbose
```

### Config file
There are examples in `tests/docs.json`.

Schema (JSON with camelCase keys):
```json
{
  "persistenceStrategy": "folder_per_domain", 
  "defaults": {
    "threads": 20,
    "rateLimiter": {
      "base_delay": [2.0, 4.0],
      "max_delay": 30.0,
      "max_retries": 5,
      "rate_limit_codes": [429, 503]
    },
    "outputFormat": "markdown"
  },
  "items": [
    {
      "url": "https://example.com/sitemap.xml",
      "isSitemap": true,
      "shouldScrap": false,
      "selectors": ["article", "main", ".content"],
      "includeExternal": false,
      "includeSubdomains": true,
      "maxDepth": 2,
      "maxPages": 100,
      "pathsToSkipRegex": "",
      "outputFormat": "markdown"
    },
    {
      "url": "https://example.com/page",
      "isSitemap": false,
      "shouldScrap": false,
      "selectors": ["#main-content"]
    },
    {
      "url": "https://docs.soliditylang.org/en/latest",
      "isSitemap": false,
      "shouldScrap": true,
      "maxDepth": 2,
      "maxPages": 50,
      "includeExternal": false,
      "includeSubdomains": true,
      "pathsToSkipRegex": "ang.org\\/(?!en)[a-z]{2}(-[a-z]{1,2})?\\/|forum.soliditylang.org",
      "selectors": ["#main-content", "article"]
    }
  ],
  "youtube": [
    "https://www.youtube.com/watch?v=1jkQn_dpROI"
  ]
}
```
Notes:
- `isSitemap: true` with `shouldScrap: false` expands the sitemap into individual page URLs (flat fetch).
- `shouldScrap: true` enables deep crawling starting from `url` using Crawl4AI.
- `selectors` are CSS selectors applied during extraction to focus content.
- `persistenceStrategy` supports:
  - `folder_per_domain`: one file per URL under a domain folder
  - `file_per_domain`: a single aggregated markdown file per domain

#### Note on sitemaps
Many documentation sites expose `/sitemap.xml` (e.g., `https://example.com/sitemap.xml`). Prefer sitemaps over deep scraping where possible to reduce load and speed up processing.

### YouTube transcripts
Add video links under `youtube`. The tool fetches transcripts and persists them alongside crawled docs, formatted as markdown.

## Development
- Run tests:
```shell
uv run pytest
```
- Example local CLI help:
```shell
uv run docs-crawler --help
```

## License
MIT