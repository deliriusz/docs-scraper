# 📖 docs-scraper
A simple script that downloads documentation from provided json and saves it to desired output directory.

## Purpose
I created this script, because I needed a way to download multiple documentation items to load it into AI IDE (Cursor, Windsurf, etc.). While they already have interesting RAG capabilities, attaching web links as a context is a pain in the ass. So I created a script that loads multiple docs into a single folder, that easily can be attached to enhance AI responses.

## Setup
```shell
pip install -r requirements.txt
```

## Running
```shell
python3 docs_scraper.py <json-config-file-path> <output-dir>
```
E.g.
```shell
python3 docs_scraper.py ./docs.json ./documentation
```

### Config file
There is an exemplary docs list in `test/docs.json`. Generally the structure is as follows:
```json
{
  "single_page": [], // takes array of pages to load
  "sitemap": [], // link of sitemap from which to download all documentation
  "scrap": [ // recursively scraps all webpages up to desired depth
    {
      "url": "https://...",
      "depth": 1, // number of recursive crawl operations to get links
      "allow_external_links": false // whether to follow links that have different host than initial docs
    }
  ],
  "youtube": [] // YT links - loads video transcripts
}
```

#### Note on sitemaps
Many documentation pages have .../sitemap.xml, that lists all the pages in docs - (e.g. https://example.com => https://example.com/sitemap.xml). Try to add `/sitemap.xml` to web address and see if the page supports that. This may be better option than recursively scrapping the page, which may incur unnecesary load on the scrapped page and give the same results.


## TODO
- [x] recursive scraping (`scrap` from config file)