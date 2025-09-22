import os
import asyncio
import tempfile
import pytest
from pathlib import Path

from src.docs_crawler.persistence import create_persistence_strategy


class TestPersistence:
    """Test suite for persistence layer functionality."""
    
    @pytest.mark.asyncio
    async def test_folder_per_domain(self, tmp_path):
        """Test FolderPerDomainStrategy."""
        strategy = create_persistence_strategy("folder_per_domain", str(tmp_path))
        
        # Test saving content
        test_urls = [
            "https://example.com/page1",
            "https://example.com/page2", 
            "https://test.org/page1",
            "https://test.org/page2"
        ]
        
        for i, url in enumerate(test_urls):
            content = f"# Test Content {i+1}\n\nThis is test content for {url}"
            path = await strategy.save(url, content)
            assert path is not None
            print(f"Saved: {url} -> {path}")
        
        await strategy.finalize()
        
        # Check results
        saved_files = strategy.get_saved_files()
        assert len(saved_files) == 4
        print(f"Saved {len(saved_files)} files")
        
        for file_info in saved_files:
            print(f"  {file_info.url} -> {file_info.path} ({file_info.size} bytes)")
        
        # List created files
        for root, dirs, files in os.walk(tmp_path):
            for file in files:
                print(f"  {Path(root) / file}")

    @pytest.mark.asyncio
    async def test_file_per_domain(self, tmp_path):
        """Test FilePerDomainStrategy."""
        strategy = create_persistence_strategy("file_per_domain", str(tmp_path), buffer_size=2)
        
        # Test saving content
        test_urls = [
            "https://example.com/page1",
            "https://example.com/page2", 
            "https://example.com/page3",  # Should trigger flush
            "https://test.org/page1",
            "https://test.org/page2"
        ]
        
        for i, url in enumerate(test_urls):
            content = f"# Test Content {i+1}\n\nThis is test content for {url}"
            path = await strategy.save(url, content)
            assert path is not None
            print(f"Buffered: {url} -> {path}")
        
        await strategy.finalize()
        
        # Check results
        saved_files = strategy.get_saved_files()
        # With buffer_size=2, we expect 3 files: 2 for example.com (flushed at 2 pages) + 1 for test.org
        assert len(saved_files) == 3
        print(f"Created {len(saved_files)} domain files")
        
        for file_info in saved_files:
            print(f"  {file_info.domain}: {file_info.pages} pages, {file_info.size} bytes")
            print(f"    URLs: {', '.join(file_info.urls)}")
