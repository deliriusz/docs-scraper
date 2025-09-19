"""
docs_crawler v2 - Advanced web crawler for documentation sites using Crawl4AI

This package provides a modern, async-based web crawler specifically designed
for documentation sites with support for:
- Deep crawling with configurable depth and filters
- Sitemap expansion
- Content selection via CSS selectors
- Structured data extraction (JSON/CSS)
- YouTube transcript extraction
- Multiple persistence strategies
"""

__version__ = "2.0.0"
__author__ = "Deliriusz"

from .config import load_config, Config, Item, Defaults
from .base import C4ABase
from .batch_runner import BatchRunner
from .deepcrawl_runner import DeepCrawlRunner
from .extraction import JSONCSSExtractor
from .persistence import PersistenceStrategy, FolderPerDomainStrategy, FilePerDomainStrategy
from .youtube import YouTubeTranscriptExtractor
from .cli import main

__all__ = [
    "load_config",
    "Config",
    "Item", 
    "Defaults",
    "C4ABase",
    "BatchRunner",
    "DeepCrawlRunner",
    "JSONCSSExtractor",
    "PersistenceStrategy",
    "FolderPerDomainStrategy", 
    "FilePerDomainStrategy",
    "YouTubeTranscriptExtractor",
    "main",
]
