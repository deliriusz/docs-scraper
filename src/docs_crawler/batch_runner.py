"""
Batch runner module for docs_crawler v2.

Handles parallel processing of flat URL lists using arun_many with rate limiting.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from crawl4ai import CrawlResult

from .base import C4ABase
from .config import Item, Defaults
from .persistence import PersistenceStrategy

logger = logging.getLogger(__name__)


@dataclass
class BatchStats:
    """Statistics for batch processing."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0


class BatchRunner:
    """Handles batch processing of flat URL lists."""
    
    def __init__(self, base: C4ABase, defaults: Defaults, persistence: PersistenceStrategy):
        """
        Initialize BatchRunner.
        
        Args:
            base: C4ABase instance for crawler operations
            defaults: Default configuration
            persistence: Persistence strategy for saving content
        """
        self.base = base
        self.defaults = defaults
        self.persistence = persistence
        self.results = []
        self.stats = BatchStats()
    
    async def run(self, items: List[Item]) -> List[CrawlResult]:
        """
        Run batch processing on flat URL list.
        
        Args:
            items: List of items to process
            
        Returns:
            List of crawl results
        """
        if not items:
            logger.info("No items to process")
            return []
        
        logger.info(f"Starting batch processing of {len(items)} items")
        self.stats.total = len(items)
        
        # Extract URLs and build configs
        urls = [item.url for item in items]
        configs = [self.base.build_run_config(item) for item in items]
        
        try:
            # Use arun_many with rate limiting
            results = await self.base.crawler.arun_many(
                urls=urls,
                config=configs,
                concurrency=self.defaults.threads,
                rate_limiter=self.base.rate_limiter
            )
            
            # Process results
            await self._process_results(results)
            
            logger.info(f"Batch processing completed: {self.stats.success} success, {self.stats.failed} failed, {self.stats.skipped} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise
    
    async def _process_results(self, results: List[CrawlResult]) -> None:
        """
        Process crawl results and save content.
        
        Args:
            results: List of crawl results
        """
        
        for result in results:
            url = result.url
            
            if not result.success:
                logger.error(f"Failed to crawl {url}: {result.error_message}")
                self.stats.failed += 1
                continue
            
            # Check if we should skip empty content
            if not result.markdown or not result.markdown.strip():
                logger.warning(f"Empty content for {url}, skipping")
                self.stats.skipped += 1
                continue
            
            try:
                # Save markdown content
                await self._save_markdown(url, result.markdown)
                
                self.stats.success += 1
                logger.debug(f"Successfully processed: {url}")
                
            except Exception as e:
                logger.error(f"Failed to process result for {url}: {e}")
                self.stats.failed += 1
    
    async def _save_markdown(self, url: str, content: str) -> None:
        """
        Save markdown content using persistence strategy.
        
        Args:
            url: URL of the content
            content: Markdown content
        """
        path = await self.persistence.save(url, content)
        if path:
            logger.debug(f"Saved markdown: {url} -> {path}")
    
    def get_stats(self) -> BatchStats:
        """Get processing statistics."""
        return self.stats
    
    def get_results(self) -> List[CrawlResult]:
        """Get processed results."""
        return self.results.copy()
