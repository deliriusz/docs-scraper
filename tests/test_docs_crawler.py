import os
import asyncio
from re import Pattern
from typing import Optional

import pytest
from crawl4ai import FilterChain

from docs_crawler import Defaults, Item
from src.docs_crawler import VISITED_URLS, C4ABase
from src.docs_crawler.cli import run_crawler

@pytest.fixture
def test_config_file():
    """Provide test configuration file path."""
    return os.path.join(os.path.dirname(__file__), "docs.json")

@pytest.fixture
def test_output_dir(tmp_path):
    """Provide temporary output directory for tests."""
    return str(tmp_path / "output")

@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup for each test."""
    # Clear VISITED_URLS before each test
    VISITED_URLS.clear()
    yield
    # Cleanup after each test
    VISITED_URLS.clear()

def test_filtering_strategy():
    defaults: Defaults = Defaults(threads=1, outputFormat="markdown")
    base: C4ABase = C4ABase(defaults)
    item: Item = Item(url="http://forum.systim.pl/test", is_sitemap=False, should_scrap=False, selectors=[],
                      include_external=True, include_subdomains=True, max_depth=2, max_pages=50,
                      paths_to_skip_regex="")

    filter_chain: FilterChain = base.build_filter_chain(item)
    assert (filter_chain is not None)
    for filter in filter_chain.filters:
        pattern: Pattern = filter._path_patterns[0]
        assert pattern.match("https://test.forum.systim.pl/x")
        assert not pattern.match("https://inne.systim.pl/x")


def test_crawl_docs_dry_run(test_config_file, test_output_dir):
    """Test that docs_crawler can process the test config file in dry run mode."""
    # Run the crawler function in dry run mode
    asyncio.run(run_crawler(test_config_file, test_output_dir, dry_run=True))

    # In dry run mode, we don't expect output files, just that the process completes
    # Check if the output directory was created
    assert os.path.exists(test_output_dir), "Output directory was not created"

    print(f"Dry run test completed successfully.")
    print(f"Output directory: {test_output_dir}")
    print(f"Visited URLs: {len(VISITED_URLS)}")
