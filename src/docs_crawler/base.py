"""
Base crawler module for docs_crawler v2.

Provides shared Crawl4AI setup, configuration building, and filter chain management.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
from crawl4ai.rate_limiter import RateLimiter
from crawl4ai.web_scraping_strategy import LXMLWebScrapingStrategy

from .config import Item, Defaults, RateLimiterConfig

logger = logging.getLogger(__name__)


class C4ABase:
    """
    Base class for Crawl4AI operations.
    
    Manages AsyncWebCrawler lifecycle and provides common configuration building methods.
    """
    
    def __init__(self, defaults: Defaults):
        """
        Initialize C4ABase with default configuration.
        
        Args:
            defaults: Default configuration values
        """
        self.defaults = defaults
        self.crawler: Optional[AsyncWebCrawler] = None
        self.browser_config = self._build_browser_config()
        self.rate_limiter = self._build_rate_limiter()
    
    def _build_browser_config(self) -> BrowserConfig:
        """Build browser configuration with performance optimizations."""
        return BrowserConfig(
            headless=True,
            verbose=False,
            # Performance improvements
            extra_args=[
                "--disable-gpu",
                "--disable-dev-shm-usage", 
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ]
        )
    
    def _build_rate_limiter(self) -> RateLimiter:
        """Build rate limiter from configuration."""
        rate_config = self.defaults.rate_limiter
        return RateLimiter(
            base_delay=rate_config.base_delay,
            max_delay=rate_config.max_delay,
            max_retries=rate_config.max_retries,
            rate_limit_codes=rate_config.rate_limit_codes
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        logger.info("Starting AsyncWebCrawler")
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        await self.crawler.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.crawler:
            logger.info("Closing AsyncWebCrawler")
            await self.crawler.close()
    
    def build_run_config(self, item: Item) -> CrawlerRunConfig:
        """
        Build CrawlerRunConfig for a specific item.
        
        Args:
            item: Item configuration
            
        Returns:
            Configured CrawlerRunConfig
        """
        # Build content selection strategy if selectors are provided
        scraping_strategy = None
        if item.selectors:
            scraping_strategy = LXMLWebScrapingStrategy(
                css_selector=", ".join(item.selectors)
            )
        
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            scraping_strategy=scraping_strategy,
            # Add other configuration as needed
        )
    
    def build_filter_chain(self, item: Item) -> Optional[FilterChain]:
        """
        Build filter chain for deep crawling based on item configuration.
        
        Args:
            item: Item configuration
            
        Returns:
            Configured FilterChain or None
        """
        filters = []
        
        # Add URL pattern filter for paths_to_skip_regex
        if item.paths_to_skip_regex:
            try:
                # Compile regex to validate it
                re.compile(item.paths_to_skip_regex)
                filters.append(
                    URLPatternFilter(
                        pattern=item.paths_to_skip_regex,
                        action="block"
                    )
                )
                logger.debug(f"Added URL pattern filter: {item.paths_to_skip_regex}")
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{item.paths_to_skip_regex}': {e}")
        
        # Add domain filter for include_external
        if not item.include_external:
            domain = self._extract_domain(item.url)
            if domain:
                # Block external domains
                external_pattern = f"^(?!https?://(www\\.)?{re.escape(domain)})"
                filters.append(
                    URLPatternFilter(
                        pattern=external_pattern,
                        action="block"
                    )
                )
                logger.debug(f"Added domain filter for: {domain}")
        
        # Add subdomain filter
        if not item.include_subdomains and item.include_external:
            domain = self._extract_domain(item.url)
            if domain:
                # Only allow exact domain matches
                exact_domain_pattern = f"^https?://(www\\.)?{re.escape(domain)}/"
                filters.append(
                    URLPatternFilter(
                        pattern=exact_domain_pattern,
                        action="allow"
                    )
                )
                logger.debug(f"Added exact domain filter for: {domain}")
        
        return FilterChain(filters) if filters else None
    
    def build_best_first_strategy(self, item: Item) -> BestFirstCrawlingStrategy:
        """
        Build BestFirstCrawlingStrategy for deep crawling.
        
        Args:
            item: Item configuration
            
        Returns:
            Configured BestFirstCrawlingStrategy
        """
        filter_chain = self.build_filter_chain(item)
        
        return BestFirstCrawlingStrategy(
            max_depth=item.max_depth,
            max_pages=item.max_pages,
            include_external=item.include_external,
            filter_chain=filter_chain,
            # No scoring for now - using default behavior
        )
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """
        Extract domain from URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain name or None if invalid URL
        """
        try:
            parsed = urlparse(url)
            domain = parsed.hostname
            if domain and domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception as e:
            logger.warning(f"Failed to extract domain from URL {url}: {e}")
            return None
    
    def get_output_format(self, item: Item) -> str:
        """
        Get output format for item, falling back to defaults.
        
        Args:
            item: Item configuration
            
        Returns:
            Output format string
        """
        return item.output_format or self.defaults.output_format
