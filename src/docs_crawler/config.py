"""
Configuration module for docs_crawler v2.

Uses Pydantic models for validation and parsing of configuration files.
Includes helpers for sitemap expansion and URL normalization.
"""

import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from pydantic import BaseModel, Field, ConfigDict
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


class RateLimiterConfig(BaseModel):
    """Configuration for rate limiting."""
    base_delay: Tuple[float, float] = (2.0, 4.0)
    max_delay: float = 30.0
    max_retries: int = 5
    rate_limit_codes: List[int] = Field(default_factory=lambda: [429, 503])


class Defaults(BaseModel):
    """Default configuration values applied to all items."""
    threads: int = 20
    rate_limiter: RateLimiterConfig = Field(default_factory=RateLimiterConfig, alias="rateLimiter")
    output_format: str = Field("markdown", alias="outputFormat")  # "markdown" | "json" | "both"

    model_config = ConfigDict(populate_by_name=True)



class Item(BaseModel):
    """Configuration for a single crawl item."""
    url: str
    is_sitemap: bool = Field(False, alias="isSitemap")
    should_scrap: bool = Field(False, alias="shouldScrap")
    selectors: List[str] = Field(default_factory=list)
    include_external: bool = Field(False, alias="includeExternal")
    include_subdomains: bool = Field(True, alias="includeSubdomains")
    max_depth: int = Field(2, alias="maxDepth")
    max_pages: int = Field(100, alias="maxPages")
    paths_to_skip_regex: str = Field("", alias="pathsToSkipRegex")
    output_format: Optional[str] = Field(None, alias="outputFormat")  # Override default

    model_config = ConfigDict(populate_by_name=True)

class Config(BaseModel):
    """Main configuration class."""
    persistence_strategy: str = Field("folder_per_domain", alias="persistenceStrategy")
    defaults: Defaults = Defaults()
    items: List[Item] = Field(default_factory=list)
    youtube: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


def normalize_url(url: str, strip_utm: bool = True) -> str:
    """
    Normalize URL by removing fragments, trailing slashes, and optionally UTM parameters.
    
    Args:
        url: URL to normalize
        strip_utm: Whether to remove UTM tracking parameters
        
    Returns:
        Normalized URL
    """
    # Remove fragment
    url = url.split('#', 1)[0]
    
    # Remove trailing slash
    url = re.sub(r'/$', '', url)
    
    if strip_utm:
        # Remove UTM parameters
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Remove UTM parameters
        utm_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']
        for param in utm_params:
            query_params.pop(param, None)
        
        # Rebuild query string
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        parsed = parsed._replace(query=new_query)
        url = urllib.parse.urlunparse(parsed)
    
    return url


def get_urls_from_sitemap(sitemap_url: str) -> List[str]:
    """
    Extract URLs from a sitemap XML file.
    
    Args:
        sitemap_url: URL of the sitemap
        
    Returns:
        List of URLs found in the sitemap
    """
    try:
        logger.info(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, timeout=30)
        response.raise_for_status()
        
        # Parse the XML
        root = ElementTree.fromstring(response.content)
        
        # Extract all URLs from the sitemap
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [loc.text for loc in root.findall('.//ns:loc', namespace) if loc.text]
        
        logger.info(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
        return urls
        
    except Exception as e:
        logger.error(f"Error fetching sitemap {sitemap_url}: {e}")
        return []


def expand_sitemaps(items: List[Item]) -> List[Item]:
    """
    Expand sitemap items into individual URL items.
    
    Args:
        items: List of items to process
        
    Returns:
        List of items with sitemaps expanded to individual URLs
    """
    expanded_items = []
    
    for item in items:
        if item.is_sitemap and not item.should_scrap:
            # Expand sitemap into individual URLs
            urls = get_urls_from_sitemap(item.url)
            
            for url in urls:
                # Create new item for each URL with same settings as original
                new_item = Item(
                    url=normalize_url(url),
                    is_sitemap=False,
                    should_scrap=False,
                    selectors=item.selectors.copy(),
                    include_external=item.include_external,
                    include_subdomains=item.include_subdomains,
                    max_depth=item.max_depth,
                    max_pages=item.max_pages,
                    paths_to_skip_regex=item.paths_to_skip_regex,
                    output_format=item.output_format,
                )
                expanded_items.append(new_item)
        else:
            # Keep original item
            expanded_items.append(item)
    
    return expanded_items


def deduplicate_urls(items: List[Item]) -> List[Item]:
    """
    Remove duplicate URLs from items list.
    
    Args:
        items: List of items to deduplicate
        
    Returns:
        List of items with duplicates removed
    """
    seen_urls = set()
    unique_items = []
    
    for item in items:
        normalized_url = normalize_url(item.url)
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            unique_items.append(item)
        else:
            logger.debug(f"Skipping duplicate URL: {item.url}")
    
    return unique_items


def load_config(config_path: Union[str, Path]) -> Config:
    """
    Load and process configuration from JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Processed configuration object
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    logger.info(f"Loading configuration from: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Parse using Pydantic models (expects new format)
    config = Config.model_validate(data)

    # Process configuration
    logger.info("Expanding sitemaps and normalizing URLs")
    config.items = expand_sitemaps(config.items)
    config.items = deduplicate_urls(config.items)
    
    # Normalize YouTube URLs
    config.youtube = [normalize_url(url) for url in config.youtube]
    
    logger.info(f"Loaded {len(config.items)} items and {len(config.youtube)} YouTube URLs")
    
    return config
