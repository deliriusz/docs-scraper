"""
Configuration module for docs_crawler v2.

Handles loading, validation, and processing of configuration files
with support for backward compatibility and sitemap expansion.
"""

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import requests
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiting."""
    base_delay: Tuple[float, float] = (2.0, 4.0)
    max_delay: float = 30.0
    max_retries: int = 5
    rate_limit_codes: List[int] = field(default_factory=lambda: [429, 503])


@dataclass
class Defaults:
    """Default configuration values applied to all items."""
    threads: int = 20
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    output_format: str = "markdown"  # "markdown" | "json" | "both"


@dataclass
class Schema:
    """Schema configuration for structured extraction."""
    type: str = "jsoncss"
    definition: Union[Dict[str, Any], str] = field(default_factory=dict)  # JSON dict or file path


@dataclass
class Item:
    """Configuration for a single crawl item."""
    url: str
    is_sitemap: bool = False
    should_scrap: bool = False
    selectors: List[str] = field(default_factory=list)
    schema: Optional[Schema] = None
    include_external: bool = False
    include_subdomains: bool = True
    max_depth: int = 2
    max_pages: int = 100
    paths_to_skip_regex: str = ""
    output_format: Optional[str] = None  # Override default


@dataclass
class Config:
    """Main configuration class."""
    persistence_strategy: str = "folder_per_domain"  # "folder_per_domain" | "file_per_domain"
    defaults: Defaults = field(default_factory=Defaults)
    items: List[Item] = field(default_factory=list)
    youtube: List[str] = field(default_factory=list)


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
                    schema=item.schema,
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


def migrate_legacy_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate legacy configuration format to new unified format.
    
    Args:
        data: Configuration dictionary
        
    Returns:
        Migrated configuration dictionary
    """
    if "items" in data:
        # Already in new format
        return data
    
    logger.info("Migrating legacy configuration format")
    
    # Create new format
    new_config = {
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
        "items": [],
        "youtube": data.get("youtube", [])
    }
    
    # Migrate single_page entries
    for url in data.get("single_page", []):
        new_config["items"].append({
            "url": url,
            "isSitemap": False,
            "shouldScrap": False,
            "selectors": []
        })
    
    # Migrate sitemap entries
    for url in data.get("sitemap", []):
        new_config["items"].append({
            "url": url,
            "isSitemap": True,
            "shouldScrap": False,
            "selectors": []
        })
    
    # Migrate scrap entries
    for scrap_item in data.get("scrap", []):
        new_config["items"].append({
            "url": scrap_item["url"],
            "isSitemap": False,
            "shouldScrap": True,
            "selectors": [],
            "include_external": scrap_item.get("allow_external_links", False),
            "max_depth": scrap_item.get("depth", 2),
            "paths_to_skip_regex": scrap_item.get("paths_to_skip_regex", "")
        })
    
    return new_config


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
    
    # Migrate legacy format if needed
    data = migrate_legacy_config(data)
    
    # Parse configuration
    defaults_data = data.get("defaults", {})
    defaults = Defaults(
        threads=defaults_data.get("threads", 20),
        rate_limiter=RateLimiterConfig(
            base_delay=tuple(defaults_data.get("rateLimiter", {}).get("base_delay", [2.0, 4.0])),
            max_delay=defaults_data.get("rateLimiter", {}).get("max_delay", 30.0),
            max_retries=defaults_data.get("rateLimiter", {}).get("max_retries", 5),
            rate_limit_codes=defaults_data.get("rateLimiter", {}).get("rate_limit_codes", [429, 503])
        ),
        output_format=defaults_data.get("outputFormat", "markdown")
    )
    
    # Parse items
    items = []
    for item_data in data.get("items", []):
        schema_data = item_data.get("schema")
        schema = None
        if schema_data:
            schema = Schema(
                type=schema_data.get("type", "jsoncss"),
                definition=schema_data.get("definition", {})
            )
        
        item = Item(
            url=item_data["url"],
            is_sitemap=item_data.get("isSitemap", False),
            should_scrap=item_data.get("shouldScrap", False),
            selectors=item_data.get("selectors", []),
            schema=schema,
            include_external=item_data.get("include_external", False),
            include_subdomains=item_data.get("include_subdomains", True),
            max_depth=item_data.get("max_depth", 2),
            max_pages=item_data.get("max_pages", 100),
            paths_to_skip_regex=item_data.get("paths_to_skip_regex", ""),
            output_format=item_data.get("outputFormat")
        )
        items.append(item)
    
    # Create config object
    config = Config(
        persistence_strategy=data.get("persistenceStrategy", "folder_per_domain"),
        defaults=defaults,
        items=items,
        youtube=data.get("youtube", [])
    )
    
    # Process configuration
    logger.info("Expanding sitemaps and normalizing URLs")
    config.items = expand_sitemaps(config.items)
    config.items = deduplicate_urls(config.items)
    
    # Normalize YouTube URLs
    config.youtube = [normalize_url(url) for url in config.youtube]
    
    logger.info(f"Loaded {len(config.items)} items and {len(config.youtube)} YouTube URLs")
    
    return config
