import asyncio
import json
import yt_dlp
import requests
from xml.etree import ElementTree
from typing import List
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# def scrape_recursively
async def process_and_store_document(url: str, markdown: str, output_dir: str):
    #TODO: implement
    print(url)
    print(markdown)


async def get_unique_urls_from_config(config_file: str) -> List[str]:
    """ Bundle urls from single pages, sitemap files and recursive crawling pages. """
    with open(config_file) as json_data:
        conf = json.load(json_data)

        output_urls = set()

        output_urls.update(conf["single_page"])
        output_urls.update(conf["youtube"])

        for sitemap_url in conf["sitemap"]:
            output_urls.update(get_urls_from_sitemap(sitemap_url))

        # TODO: add scraping options, possibly change return type to list of objects
        for scrap_url in conf["scrap"]:
            output_urls.add(scrap_url["url"])

        # YT don't need crawling, just yt_dlp to get transcript
        return list(output_urls)

def get_yt_transcript(url: str) -> str:
    # TODO: change to https://pypi.org/project/youtube-transcript-api/
    ydl_opts = {
        'write-thumbnail': True,
        'skip-download': True,
        'verbose': True
    }

    with yt_dlp.YoutubeDL(params = ydl_opts) as ydl:
        return ydl.download(url)

async def crawl_parallel(urls: List[str], output_dir: str, crawler: AsyncWebCrawler, max_concurrent: int = 5):
    """Crawl multiple URLs in parallel with a concurrency limit."""
    crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    # Create the crawler instance

    try:
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_url(url: str):
            async with semaphore:
                if "youtube.com" in url:
                    result = get_yt_transcript(url)
                    await process_and_store_document(url, result, output_dir)
                else:
                    result = await crawler.arun(
                        url=url,
                        config=crawl_config,
                        session_id="session1"
                    )
                    if result.success:
                        print(f"Successfully crawled: {url}")
                        # await process_and_store_document(url, result.markdown_v2.raw_markdown)
                        await process_and_store_document(url, result.markdown, output_dir)
                    else:
                        print(f"Failed: {url} - Error: {result.error_message}")

        # Process all URLs in parallel with limited concurrency
        await asyncio.gather(*[process_url(url) for url in urls])
    finally:
        await crawler.close()

def get_urls_from_sitemap(url: str) -> List[str]:
    """Get URLs from docs sitemap."""
    try:
        response = requests.get(url)
        response.raise_for_status()

        # Parse the XML
        root = ElementTree.fromstring(response.content)

        # Extract all URLs from the sitemap
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [loc.text for loc in root.findall('.//ns:loc', namespace)]

        return urls
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return []


async def main(config_file: str, output_dir: str):
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )

    # Create the crawler instance
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.start()

    urls = await get_unique_urls_from_config(config_file)

    await crawl_parallel(urls, output_dir, crawler, 10)
    # with open(config_file) as json_data:
    #     d = json.load(json_data)
    #     print(d)
    #     print(d["single_page"])
    #
    #     async with AsyncWebCrawler() as crawler:
    #         result = await crawler.arun("https://docs-one.zerolend.xyz/")
    #         print(result.markdown)
    #         # print(result.fit_markdown)
    #         print("f=====\n\n")
    #         print(result.links["internal"])
    #         print(result.links["external"])
    #         # print(result.markdown[:300])  # Print first 300 chars


if __name__ == "__main__":
    config_file = 'test/docs.json'
    output_dir = 'docs/'
    asyncio.run(main(config_file, output_dir))