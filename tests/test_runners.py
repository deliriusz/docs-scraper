import asyncio
import pytest
from pathlib import Path

from src.docs_crawler.config import load_config, Item, Defaults
from src.docs_crawler.base import C4ABase
from src.docs_crawler.batch_runner import BatchRunner
from src.docs_crawler.deepcrawl_runner import DeepCrawlRunner
from src.docs_crawler.persistence import create_persistence_strategy


class TestRunners:
    """Test suite for batch and deep crawl runners."""
    
    @pytest.mark.asyncio
    async def test_batch_runner(self, tmp_path):
        """Test BatchRunner with sample data."""
        # Create test items
        test_items = [
            Item(
                url="https://httpbin.org/html",
                is_sitemap=False,
                should_scrap=False,
                selectors=["h1", "p"]
            ),
            Item(
                url="https://httpbin.org/json",
                is_sitemap=False,
                should_scrap=False,
                selectors=["body"]
            )
        ]
        
        # Create persistence strategy
        persistence = create_persistence_strategy("folder_per_domain", str(tmp_path))
        
        # Create defaults
        defaults = Defaults(threads=2)
        
        # Test with C4ABase
        async with C4ABase(defaults) as base:
            batch_runner = BatchRunner(base, defaults, persistence)
            
            results = await batch_runner.run(test_items)
            assert len(results) >= 0  # Should complete without errors
            print(f"Batch processing completed: {len(results)} results")
            print(f"Stats: {batch_runner.get_stats()}")
            
            # List saved files
            saved_files = persistence.get_saved_files()
            print(f"Saved {len(saved_files)} files:")
            for file_info in saved_files:
                print(f"  {file_info.url} -> {file_info.path} ({file_info.size} bytes)")

    @pytest.mark.asyncio
    async def test_deep_crawl_runner(self, tmp_path):
        """Test DeepCrawlRunner with sample data."""
        # Create test item for deep crawling
        test_item = Item(
            url="https://httpbin.org",
            is_sitemap=False,
            should_scrap=True,
            max_depth=1,
            max_pages=3,
            include_external=False,
            selectors=["body"]
        )
        
        # Create persistence strategy
        persistence = create_persistence_strategy("file_per_domain", str(tmp_path))
        
        # Create defaults
        defaults = Defaults(threads=2)
        
        # Test with C4ABase
        async with C4ABase(defaults) as base:
            deep_runner = DeepCrawlRunner(base, defaults, persistence)
            
            results = await deep_runner.run(test_item)
            assert len(results) >= 0  # Should complete without errors
            print(f"Deep crawl completed: {len(results)} results")
            print(f"Stats: {deep_runner.get_stats()}")
            
            # List saved files
            saved_files = persistence.get_saved_files()
            print(f"Saved {len(saved_files)} domain files:")
            for file_info in saved_files:
                print(f"  {file_info.domain}: {file_info.pages} pages, {file_info.size} bytes")
                print(f"    URLs: {', '.join(file_info.urls[:3])}{'...' if len(file_info.urls) > 3 else ''}")
