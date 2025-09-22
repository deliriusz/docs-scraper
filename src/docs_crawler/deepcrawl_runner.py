"""
Deep crawl runner module for docs_crawler v2.

Handles deep crawling using BestFirstCrawlingStrategy with streaming results.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from crawl4ai import CrawlResult
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy

from .base import C4ABase
from .config import Item, Defaults
from .persistence import PersistenceStrategy

logger = logging.getLogger(__name__)


@dataclass
class DeepCrawlStats:
    """Statistics for deep crawling."""
    total_pages: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    max_depth_reached: int = 0
    avg_score: float = 0.0
    depth_distribution: Dict[str, int] = None
    
    def __post_init__(self):
        if self.depth_distribution is None:
            self.depth_distribution = {}


class DeepCrawlRunner:
    """Handles deep crawling with BestFirstCrawlingStrategy."""
    
    def __init__(self, base: C4ABase, defaults: Defaults, persistence: PersistenceStrategy):
        """
        Initialize DeepCrawlRunner.
        
        Args:
            base: C4ABase instance for crawler operations
            defaults: Default configuration
            persistence: Persistence strategy for saving content
        """
        self.base = base
        self.defaults = defaults
        self.persistence = persistence
        self.results = []
        self.stats = DeepCrawlStats()
    
    async def run(self, item: Item) -> List[CrawlResult]:
        """
        Run deep crawling on a single item.
        
        Args:
            item: Item configuration for deep crawling
            
        Returns:
            List of crawl results
        """
        logger.info(f"Starting deep crawl: {item.url} (max_depth={item.max_depth}, max_pages={item.max_pages})")
        
        # Build BestFirstCrawlingStrategy
        strategy = self.base.build_best_first_strategy(item)
        
        # Build run config for the starting URL
        run_config = self.base.build_run_config(item)
        
        try:
            # Run deep crawling
            results = await self.base.crawler.arun(
                url=item.url,
                config=run_config,
                strategy=strategy
            )
            
            # Process results
            for result in results:
                await self._process_streaming_result(result, item)
            
            # Calculate final statistics
            self._calculate_final_stats()
            
            logger.info(f"Deep crawl completed: {self.stats.success} success, {self.stats.failed} failed, {self.stats.skipped} skipped")
            logger.info(f"Max depth reached: {self.stats.max_depth_reached}, Average score: {self.stats.avg_score:.2f}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"Deep crawl failed for {item.url}: {e}")
            raise
    
    async def _process_streaming_result(self, result: CrawlResult, item: Item) -> None:
        """
        Process a single streaming result from deep crawl.
        
        Args:
            result: Crawl result from stream
            item: Item configuration
        """
        self.stats.total_pages += 1
        
        if not result.success:
            logger.error(f"Failed to crawl {result.url}: {result.error_message}")
            self.stats.failed += 1
            return
        
        # Check if we should skip empty content
        if not result.markdown or not result.markdown.strip():
            logger.warning(f"Empty content for {result.url}, skipping")
            self.stats.skipped += 1
            return
        
        try:
            # Save markdown content
            await self._save_markdown(result)
            
            # Track statistics
            self._update_stats(result)
            
            self.stats.success += 1
            self.results.append(result)
            
            logger.debug(f"Processed: {result.url} (depth: {getattr(result, 'depth', 'unknown')}, score: {getattr(result, 'score', 'unknown')})")
            
        except Exception as e:
            logger.error(f"Failed to process result for {result.url}: {e}")
            self.stats.failed += 1
    
    async def _save_markdown(self, result: CrawlResult) -> None:
        """
        Save markdown content using persistence strategy.
        
        Args:
            result: Crawl result
        """
        path = await self.persistence.save(result.url, result.markdown)
        if path:
            logger.debug(f"Saved markdown: {result.url} -> {path}")
    
    def _update_stats(self, result: CrawlResult) -> None:
        """
        Update statistics with result data.
        
        Args:
            result: Crawl result
        """
        # Track depth
        depth = getattr(result, 'depth', 0)
        if depth > self.stats.max_depth_reached:
            self.stats.max_depth_reached = depth
        
        # Track depth distribution
        depth_key = f"depth_{depth}"
        self.stats.depth_distribution[depth_key] = self.stats.depth_distribution.get(depth_key, 0) + 1
        
        # Track score for average calculation
        score = getattr(result, 'score', 0.0)
        if hasattr(self, '_score_sum'):
            self._score_sum += score
            self._score_count += 1
        else:
            self._score_sum = score
            self._score_count = 1
    
    def _calculate_final_stats(self) -> None:
        """Calculate final statistics."""
        if hasattr(self, '_score_count') and self._score_count > 0:
            self.stats.avg_score = self._score_sum / self._score_count
        else:
            self.stats.avg_score = 0.0
    
    def get_stats(self) -> DeepCrawlStats:
        """Get processing statistics."""
        return self.stats
    
    def get_results(self) -> List[CrawlResult]:
        """Get processed results."""
        return self.results.copy()
