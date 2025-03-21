import os
import sys
import asyncio
import hashlib
import re
import json
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import requests
from xml.etree import ElementTree
from typing import List, Dict, Any
from dataclasses import dataclass, field
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Global hashmap to track visited URLs
VISITED_URLS = {}
crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

@dataclass
class ScrapItem:
    url: str
    depth: int = 1
    allow_external_links: bool = False

@dataclass
class ScrapConfig:
    scrap: List[ScrapItem] = field(default_factory=list)
    
    def add_item(self, url, depth=1, allow_external_links=False):
        self.scrap.append(ScrapItem(url, depth, allow_external_links))
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "scrap": [
                {
                    "url": item.url,
                    "depth": item.depth,
                    "allow_external_links": item.allow_external_links
                } for item in self.scrap
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScrapConfig':
        config = cls()
        for item in data.get("scrap", []):
            config.scrap.append(ScrapItem(
                url=item["url"],
                depth=item.get("depth", 1),
                allow_external_links=item.get("allow_external_links", False)
            ))
        return config

def cleanup_url(url: str) -> str:
    """Remove fragment identifier (#) from URL."""
    # TODO: this won't work for YT, where video is passed as a query param
    # url = url.split('?', 1)[0]
    url = url.split('#', 1)[0]
    url = re.sub(r'/$', '', url) # remove final `/` if exists
    return url

async def process_and_store_document(url: str, markdown: str, out_dir: str):
    """ Create output file name from url and save it. """
    # whole path max length in Windows/Linux/Mac seems to be 256, 120 is a good buffer,
    # giving informative names. MD5 hash is 16 bytes (~32 characters).
    max_file_name_len = 120

    if markdown is None or len(markdown) == 0:
        return

    possible_doc_name_from_url = re.sub(r'https?://(www\.)?', '', url) # remove http:// or https://
    possible_doc_name_from_url = re.sub(r'[^a-zA-Z0-9-]', '_', possible_doc_name_from_url) # replace non-alphanumeric characters with underscores
    possible_doc_name_from_url = re.sub(r'_+', '_', possible_doc_name_from_url) # replace multiple underscores with a single underscore

    if len(possible_doc_name_from_url) > max_file_name_len:
        doc_name = possible_doc_name_from_url[:max_file_name_len] + "_" + hashlib.md5(url.encode()).hexdigest()
    else:
        doc_name = possible_doc_name_from_url

    output_path = out_dir + '/' + doc_name + ".md"

    # normalize any //
    output_path = re.sub(r'/+', '/', output_path)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(output_path, 'w') as md_file:
        md_file.write(markdown)

async def get_scrap_config_from_file(config_file: str) -> ScrapConfig:
    """
    Load just the scrap configuration items from a config file.
    Returns a ScrapConfig object populated with the scrap items.
    """
    with open(config_file) as json_data:
        conf = json.load(json_data)
        
        # Create a new ScrapConfig object
        scrap_config = ScrapConfig()
        
        # Process each scrap item from the config
        for scrap_item in conf.get("scrap", []):
            scrap_config.add_item(
                url=scrap_item["url"],
                depth=scrap_item.get("depth", 1),
                allow_external_links=scrap_item.get("allow_external_links", False)
            )
            
        return scrap_config

async def get_unique_urls_from_config(config_file: str) -> List[str]:
    """ Bundle urls from single pages, sitemap files and recursive crawling pages. """
    with open(config_file) as json_data:
        conf = json.load(json_data)

        output_urls = set()

        output_urls.update(conf["single_page"])
        output_urls.update(conf["youtube"])

        for sitemap_url in conf["sitemap"]:
            output_urls.update(get_urls_from_sitemap(sitemap_url))

        # YT don't need crawling, just yt_dlp to get transcript
        return list(output_urls)

def get_yt_transcript(url: str) -> str:
    # Heavily inspired by https://github.com/AlteredAdmin/YouTube-Transcript-Downloader
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    video_id = match.group(1) if match else None

    if video_id is None:
        print(f"No video id found in url {url}")
    else:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(['en'])

            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript.fetch())

            # Remove timecodes and speaker names
            transcript_text = re.sub(r'\[\d+:\d+:\d+\]', '', transcript_text)
            transcript_text = re.sub(r'<\w+>', '', transcript_text)

            print(f"Successfully crawled: {url}")

            return transcript_text
        except Exception as e:
            print(f"Error downloading transcript: {e}")
            return ""

async def crawl_parallel(urls: List[str], output_dir: str, crawler: AsyncWebCrawler, semaphore: asyncio.Semaphore, scrap_item: ScrapItem = None):
    """Crawl multiple URLs in parallel with a concurrency limit."""
    if len(urls) == 0:
        return

    if scrap_item is not None and scrap_item.depth < 1:
        return

    async def process_url(url: str):
        url = cleanup_url(url)

        if VISITED_URLS.get(url, False):
            print(f"Already crawled: {url}")
            return

        # Use the passed semaphore instead of creating a new one
        async with semaphore:
            # Mark this URL as visited
            VISITED_URLS[url] = True

            if "youtube.com" in url or "youtu.be" in url:
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
                    await process_and_store_document(url, result.markdown, output_dir)

                    if scrap_item is not None:
                        new_scrap_item = ScrapItem(url=url, depth=scrap_item.depth - 1, allow_external_links=scrap_item.allow_external_links)

                        links_hrefs = [link['href'] for link in result.links['internal']]

                        if scrap_item.allow_external_links:
                            external_links_hrefs = [link['href'] for link in result.links['external']]
                            links_hrefs.extend(external_links_hrefs)

                        # Gather all links into a set to remove duplicates
                        links_set = set()
                        
                        # Add internal links
                        for link in links_hrefs:
                            # Extract just the href values from internal links and remove URL fragments
                            link = cleanup_url(link)

                            if not VISITED_URLS.get(link, False):
                                links_set.add(link)
                            
                        links_hrefs = list(links_set)
                            
                        if new_scrap_item.depth < 1:
                            new_scrap_item = None

                        # Create tasks but don't await them here - avoid nesting crawl calls
                        asyncio.create_task(crawl_parallel(links_hrefs, output_dir, crawler, semaphore, new_scrap_item))
                else:
                    print(f"Failed: {url} - Error: {result.error_message}")

    # Create tasks for each URL but limit their execution with the semaphore
    tasks = [asyncio.create_task(process_url(url)) for url in urls]
    await asyncio.gather(*tasks)

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
        # performance improvements
        extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
    )

    # Create a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(10)

    # Create the crawler instance
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.start()

    try:
        urls = await get_unique_urls_from_config(config_file)
        scrap_config = await get_scrap_config_from_file(config_file)

        tasks = []
        # Process scrap items
        for scrap_item in scrap_config.scrap:
            print(f"Processing scrap: {scrap_item.url} with depth {scrap_item.depth}")
            tasks.append(crawl_parallel([scrap_item.url], output_dir, crawler, semaphore, scrap_item))

        # Process single URLs
        tasks.append(crawl_parallel(urls, output_dir, crawler, semaphore))

        # tasks.append(asyncio.sleep(15))
        
        # Wait for all crawling to complete
        await asyncio.gather(*tasks)
    finally:
        # Ensure crawler is properly closed
        # await crawler.close()
        print(f"DONE")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage {sys.argv[0]} <json-config-file-path> <output-dir>")
        exit(1)

    config_file = sys.argv[1]
    output_dir = sys.argv[2]
    asyncio.run(main(config_file, output_dir))