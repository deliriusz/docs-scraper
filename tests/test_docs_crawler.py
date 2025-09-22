import os
import asyncio
import pytest
from pathlib import Path

from src.docs_crawler import cleanup_url, VISITED_URLS
from src.docs_crawler.cli import run_crawler


class TestDocsCrawler:
    """Test suite for the main docs_crawler functionality."""
    
    @pytest.fixture
    def test_config_file(self):
        """Provide test configuration file path."""
        return os.path.join(os.path.dirname(__file__), "docs.json")
    
    @pytest.fixture
    def test_output_dir(self, tmp_path):
        """Provide temporary output directory for tests."""
        return str(tmp_path / "output")
    
    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Setup and cleanup for each test."""
        # Clear VISITED_URLS before each test
        VISITED_URLS.clear()
        yield
        # Cleanup after each test
        VISITED_URLS.clear()
    
    def test_crawl_docs_dry_run(self, test_config_file, test_output_dir):
        """Test that docs_crawler can process the test config file in dry run mode."""
        # Run the crawler function in dry run mode
        asyncio.run(run_crawler(test_config_file, test_output_dir, dry_run=True))

        # In dry run mode, we don't expect output files, just that the process completes
        # Check if the output directory was created
        assert os.path.exists(test_output_dir), "Output directory was not created"
        
        print(f"Dry run test completed successfully.")
        print(f"Output directory: {test_output_dir}")
        print(f"Visited URLs: {len(VISITED_URLS)}")
