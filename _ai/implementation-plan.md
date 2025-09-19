## docs_crawler v2 – Implementation Plan

References:
- Deep Crawling (Crawl4AI v0.7.x): `https://docs.crawl4ai.com/core/deep-crawling/`
- Content Selection: `https://docs.crawl4ai.com/core/content-selection/`
- Structured Extraction (JSON/CSS): `https://docs.crawl4ai.com/core/content-selection/#41-pattern-based-with-jsoncssextractionstrategy`
- Multi-URL Crawling and Rate Limiting: `https://docs.crawl4ai.com/advanced/multi-url-crawling/`

### Goals
- Replace custom recursion with Crawl4AI deep crawling using BestFirstCrawlingStrategy.
- Support per-item content selection (selectors array) and optional structured extraction via JSON/CSS schema.
- Unify configuration into a single items list with flags `shouldScrap` and `isSitemap`.
- Use `arun_many()` with rate limiting for flat URL batches (single pages and sitemap-expanded URLs).
- Add pluggable persistence: `folder_per_domain` and `file_per_domain` (aggregation at end).
- Keep YouTube transcript extraction as a separate component.

### Project Structure
- pyproject.toml (package metadata and dependencies)
- docs_crawler/
  - __init__.py
  - config.py (load/validate/expand config; sitemap expansion)
  - base.py (shared Crawl4AI setup: BrowserConfig, CrawlerRunConfig, RateLimiter; selection/extraction wiring)
  - batch_runner.py (arun_many for flat URL lists with rate limiting)
  - deepcrawl_runner.py (BestFirstCrawlingStrategy + filters + scorers; streaming)
  - extraction.py (JSON/CSS extraction handling; result shaping)
  - persistence.py (writers for folder_per_domain and file_per_domain aggregation)
  - youtube.py (YouTubeTranscriptApi wrapper)
  - cli.py (entry points and orchestration)
  - utils.py (URL cleanup, dedup, domain utils, hashing)

### Config Schema (docs.json)
Top-level keys:
- persistenceStrategy: "folder_per_domain" | "file_per_domain"
- defaults: optional defaults applied to items
  - threads, rateLimiter, outputFormat ("markdown"|"json"|"both")
- items: array of item objects
- youtube: array of YouTube URLs

Item object:
- url: string (page URL or sitemap URL)
- isSitemap: boolean (if true, expand into URLs; item-level selectors/schema apply to expanded pages)
- shouldScrap: boolean (if true, run deep crawling starting from url)
- selectors: array of CSS selectors (applied via scraping strategy)
- schema: optional object for structured extraction
  - type: "jsoncss"
  - definition: JSON with CSS selectors map, or schema_file path
- include_external: boolean (for deep crawl)
- include_subdomains: boolean (optional; default true)
- max_depth: int (deep crawl)
- max_pages: int (deep crawl cap)
- paths_to_skip_regex: string regex to exclude URLs
- outputFormat: optional override ("markdown"|"json"|"both")

Rate Limiter (defaults.rateLimiter):
```python
rate_limiter = RateLimiter(
    base_delay=(2.0, 4.0),
    max_delay=30.0,
    max_retries=5,
    rate_limit_codes=[429, 503]
)
```

### Core Components
1) base.C4ABase
- Manages AsyncWebCrawler lifecycle via async context manager.
- Builds BrowserConfig (headless, performance flags) and common CrawlerRunConfig.
- Applies content selection to scraping strategy (e.g., LXMLWebScrapingStrategy) per item.
- Exposes helpers:
  - build_run_config(item)
  - build_filter_chain(item) – maps paths_to_skip_regex to a blocking filter; optional allow-list later
  - build_best_first(item) – BestFirstCrawlingStrategy with include_external, max_depth, max_pages, filter_chain (no scoring)

2) config.py
- Dataclasses for Defaults, Item, RootConfig.
- Loading/validation with schema checks; merge defaults into items.
- Sitemap expansion:
  - For each item with isSitemap true and shouldScrap false: fetch and expand to flat URL list; keep item properties (selectors/schema/outputFormat) to apply to each expanded URL.
- URL normalization: strip fragments, optionally strip tracking params; dedup globally.

3) batch_runner.py
- Input: flat list of (url, item_cfg) pairs.
- Use crawler.arun_many(urls, config=..., concurrency=threads, rate_limiter=RateLimiter).
- For each result:
  - Persist markdown (respecting selectors via scraping strategy) unless outputFormat excludes it.
  - If schema present, run extraction to produce JSON alongside.
- Error handling with retries delegated to RateLimiter; collect per-URL status.

4) deepcrawl_runner.py
- For each item with shouldScrap true:
  - Configure BestFirstCrawlingStrategy per docs: `https://docs.crawl4ai.com/core/deep-crawling/`.
  - Enable stream=True; iterate async results as they arrive.
  - Apply item selectors via scraping strategy; persist each page.
  - If schema present, run structured extraction per page.
  - Respect include_external, include_subdomains, max_depth, max_pages, and paths_to_skip_regex via filter chain.
  - Track metadata: depth, score, url; accumulate stats.

5) extraction.py
- JSONCSS extraction dispatcher when item.schema.type == "jsoncss".
- Accepts page HTML/DOM context from Crawl4AI result and applies schema definition to produce JSON.
- Output file naming coordinated with persistence module.

6) persistence.py
- folder_per_domain:
  - Current behavior: write one file per URL under domain dir; filenames deduped and normalized.
- file_per_domain:
  - Keep in-memory append buffers per domain (with flush thresholds to avoid OOM).
  - Write interim fragments and merge at end into a single ordered file per domain.
  - For JSON extraction, aggregate as an array per domain or NDJSON; configurable in future.

7) youtube.py
- Use YouTubeTranscriptApi to fetch transcripts; persist using persistence strategies (domain `youtube.com`).
- Not affected by selectors/schema.

8) cli.py
- Command: `docs-crawler run <config.json> <out_dir> [--threads N] [--stream] [--dry-run]`
- Steps:
  - Load config; expand sitemaps; split items into: deep items (shouldScrap) and flat items (others).
  - With C4ABase context, run BatchRunner for flat set (arun_many with rate limiting) and DeepCrawler for deep items.
  - After runs, finalize persistence (merge per-domain files when needed) and write a run manifest (stats, outputs).

### Processing Flow
1) Load docs.json; validate; merge defaults into items.
2) Expand sitemap items where applicable into flat URLs; attach item-derived settings to each URL.
3) Build flat fetch set (single pages + sitemap-expanded, not deep) and deep set (shouldScrap).
4) Start AsyncWebCrawler once (shared across runs) via base.C4ABase.
5) Run BatchRunner.arun_many on flat set with provided RateLimiter and threads.
6) Run DeepCrawler on each deep item using BestFirstCrawlingStrategy with stream=True.
7) For every page result:
   - Apply selection (scraping strategy configured with item.selectors).
   - Persist markdown/JSON depending on outputFormat and persistenceStrategy.
8) Finalize: flush/merge per-domain aggregates; write manifest with counts, failures, and top URLs by score.

### URL Filtering and Dedup
- Normalize URLs: remove fragments, normalize trailing slashes, optionally strip UTM parameters.
- Global dedup set keyed by normalized URL.
- Deep crawl filter chain blocks paths matching paths_to_skip_regex.
- For include_external=false, remain within the same registrable domain (public suffix); allow subdomains if include_subdomains=true.

### Error Handling & Retries
- Use Crawl4AI RateLimiter as specified for arun_many.
- For deep crawl streaming, handle transient failures and log result.status; skip on repeated errors.
- Summarize failures in manifest with HTTP codes and last error message.

### Output & Naming
- Markdown: identical naming as current v2 (host subfolder; sanitized filename; length-capped with md5 suffix when needed).
- JSON (extraction): same base path/filename with `.json` extension; for file_per_domain, aggregate arrays/NDJSON and finalize at end.

### Logging & Metrics
- Verbose flag to print concise per-item progress: Depth, Score, URL for deep crawl; status per URL for batch.
- Final per-item stats: pages visited, success/fail counts, average score (deep), depth distribution (deep), output paths.
- Write `run_manifest.json` in output root with the above summary.

### Testing Plan
- Unit tests:
  - Config load/merge; sitemap expansion; selector merge; schema routing.
  - URL normalization and dedup behavior.
  - Persistence strategies: file naming and domain aggregation correctness.
- Integration tests:
  - Batch run on small set of known pages; verify outputs and schemas.
  - Deep crawl on a controlled site with limited depth and max_pages; verify streaming persistence and filters.
  - YouTube transcript happy-path and error-path.

### Milestones
1) Scaffolding: pyproject + package layout + cli stub.
2) Config loader + sitemap expansion + URL normalization/dedup.
3) Base crawler setup with selection + arun_many with RateLimiter.
4) Persistence strategies implementation.
5) Deep crawler with BestFirst, filters, scorers, streaming.
6) Structured extraction (JSON/CSS) wiring.
7) CLI orchestration + manifest + logging polish.
8) Tests and examples; README update.

### Dependencies (pyproject.toml)
```toml
[tool.poetry.dependencies]
python = "^3.9"
crawl4ai = "0.7.4"
requests = "2.32.3"
youtube-transcript-api = "0.6.3"
```

### Example Configuration
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
      "url": "https://docs-one.zerolend.xyz/sitemap.xml",
      "isSitemap": true,
      "shouldScrap": false,
      "selectors": ["article", "main", ".content"],
      "schema": {
        "type": "jsoncss",
        "definition": {
          "title": "h1::text",
          "sections": "h2::text"
        }
      }
    },
    {
      "url": "https://www.dailywarden.com/",
      "isSitemap": false,
      "shouldScrap": false,
      "selectors": ["#main-content"]
    },
    {
      "url": "https://docs.soliditylang.org/en/latest",
      "isSitemap": false,
      "shouldScrap": true,
      "max_depth": 2,
      "max_pages": 50,
      "include_external": false,
      "include_subdomains": true,
      "paths_to_skip_regex": "ang.org\\/(?!en)[a-z]{2}(-[a-z]{1,2})?\\/|forum.soliditylang.org",
      "selectors": ["#main-content", "article"],
      "outputFormat": "both"
    }
  ],
  "youtube": [
    "https://www.youtube.com/watch?v=1jkQn_dpROI"
  ]
}
```

### Backward Compatibility
- The config loader will detect old format (separate `single_page`, `sitemap`, `scrap` keys) and convert to new unified `items` array.
- Migration logic in `config.py`:
  - `single_page` entries → items with `isSitemap=false, shouldScrap=false`
  - `sitemap` entries → items with `isSitemap=true, shouldScrap=false`
  - `scrap` entries → items with `isSitemap=false, shouldScrap=true`
- This ensures existing configs continue to work without modification.

### Implementation Steps

#### Step 1: Project Setup (Day 1)
1. Create `pyproject.toml` with dependencies from requirements.txt
2. Set up package structure:
   ```bash
   mkdir -p docs_crawler
   touch docs_crawler/__init__.py
   touch docs_crawler/{config,base,batch_runner,deepcrawl_runner,extraction,persistence,youtube,cli,utils}.py
   ```
3. Initialize git branch for v2 development
4. Set up basic logging configuration

#### Step 2: Configuration Module (Day 1-2)
1. Create dataclasses in `config.py`:
   ```python
   @dataclass
   class RateLimiterConfig:
       base_delay: Tuple[float, float] = (2.0, 4.0)
       max_delay: float = 30.0
       max_retries: int = 5
       rate_limit_codes: List[int] = field(default_factory=lambda: [429, 503])
   
   @dataclass
   class Item:
       url: str
       isSitemap: bool = False
       shouldScrap: bool = False
       selectors: List[str] = field(default_factory=list)
       # ... other fields
   ```
2. Implement config loading with backward compatibility
3. Add sitemap expansion logic using existing code from v2
4. Implement URL normalization and global dedup set

#### Step 3: Base Crawler (Day 2-3)
1. Create `C4ABase` class with async context manager:
   ```python
   class C4ABase:
       async def __aenter__(self):
           self.crawler = AsyncWebCrawler(config=self.browser_config)
           await self.crawler.start()
           return self
       
       async def __aexit__(self, exc_type, exc, tb):
           await self.crawler.close()
   ```
2. Implement `build_run_config()` with content selection
3. Create filter chain builder for `paths_to_skip_regex`
4. Set up RateLimiter configuration

#### Step 4: Persistence Layer (Day 3-4)
1. Create abstract `PersistenceStrategy` base class
2. Implement `FolderPerDomainStrategy` (port from v2)
3. Implement `FilePerDomainStrategy` with buffering:
   ```python
   class FilePerDomainStrategy:
       def __init__(self, buffer_size=100, flush_size_mb=10):
           self.buffers = defaultdict(list)
           self.buffer_sizes = defaultdict(int)
   ```
4. Add file naming and path utilities to `utils.py`

#### Step 5: Batch Runner (Day 4-5)
1. Implement `BatchRunner` class inheriting from `C4ABase`
2. Create `run()` method using `arun_many()`:
   ```python
   async def run(self, items: List[Tuple[str, Item]]) -> List[CrawlResult]:
       urls = [url for url, _ in items]
       configs = [self.build_run_config(item) for _, item in items]
       results = await self.crawler.arun_many(
           urls=urls,
           configs=configs,
           rate_limiter=self.rate_limiter
       )
   ```
3. Add result processing and persistence calls
4. Implement error handling and retry logic

#### Step 6: Deep Crawl Runner (Day 5-6)
1. Create `DeepCrawlRunner` class
2. Implement BestFirstCrawlingStrategy configuration:
   ```python
   from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
   from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
   
   strategy = BestFirstCrawlingStrategy(
       max_depth=item.max_depth,
       max_pages=item.max_pages,
       include_external=item.include_external,
       filter_chain=self.build_filter_chain(item)
   )
   ```
3. Set up streaming result processing
4. Add concurrency control for deep crawls

#### Step 7: Extraction Module (Day 6-7)
1. Implement JSON/CSS extraction wrapper
2. Create schema loader (inline vs file)
3. Add result shaping and validation
4. Coordinate with persistence for JSON output

#### Step 8: YouTube Module (Day 7)
1. Port YouTube transcript logic from v2
2. Adapt to use new persistence strategies
3. Add error handling for missing transcripts

#### Step 9: CLI and Orchestration (Day 7-8)
1. Create main CLI using argparse
2. Implement orchestration logic:
   ```python
   async def run_crawler(config_path, output_dir, threads=20, dry_run=False):
       config = load_config(config_path)
       async with C4ABase(config.defaults) as base:
           # Split items
           flat_items = [i for i in config.items if not i.shouldScrap]
           deep_items = [i for i in config.items if i.shouldScrap]
           
           # Run batch
           if flat_items:
               batch_runner = BatchRunner(base.crawler, config.defaults)
               await batch_runner.run(flat_items)
           
           # Run deep crawls
           for item in deep_items:
               deep_runner = DeepCrawlRunner(base.crawler, config.defaults)
               await deep_runner.run(item)
   ```
3. Add manifest generation
4. Implement dry-run mode

#### Step 10: Testing (Day 8-9)
1. Unit tests for config loading and migration
2. Unit tests for URL normalization and dedup
3. Integration test with mock server
4. Test persistence strategies
5. End-to-end test with sample config

#### Step 11: Documentation and Polish (Day 9-10)
1. Update README with new features
2. Create migration guide from v1/v2
3. Add inline code documentation
4. Create example configs
5. Performance testing and optimization

### Notes
- Deep crawling feature set and streaming behavior per Crawl4AI docs: `https://docs.crawl4ai.com/core/deep-crawling/`.
- Content selection strategy integration per: `https://docs.crawl4ai.com/core/content-selection/`.
- JSON/CSS structured extraction per: `https://docs.crawl4ai.com/core/content-selection/#41-pattern-based-with-jsoncssextractionstrategy`.
- Multi-URL concurrency and RateLimiter per: `https://docs.crawl4ai.com/advanced/multi-url-crawling/`.
- No scoring/keywords - using default BestFirstCrawlingStrategy behavior
- Concurrency parameter only relevant for deep crawl scenarios, not batch fetching



