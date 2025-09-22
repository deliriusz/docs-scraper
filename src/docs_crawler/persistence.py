"""
Persistence module for docs_crawler v2.

Handles different persistence strategies for saving crawled content.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urlparse

from .utils import extract_domain, sanitize_filename, create_url_hash

logger = logging.getLogger(__name__)


@dataclass
class SavedFileInfo:
    """Information about a saved file."""
    url: str
    path: str
    size: int


@dataclass
class SavedDomainFileInfo:
    """Information about a saved domain file (for FilePerDomainStrategy)."""
    domain: str
    path: str
    pages: int
    size: int
    urls: List[str]


class PersistenceStrategy(ABC):
    """Abstract base class for persistence strategies."""
    
    @abstractmethod
    async def save(self, url: str, content: str) -> str:
        """
        Save content for a URL.
        
        Args:
            url: URL of the content
            content: Content to save
            
        Returns:
            Path where content was saved
        """
        pass
    
    @abstractmethod
    async def finalize(self) -> None:
        """Finalize persistence operations (e.g., merge files)."""
        pass


class FolderPerDomainStrategy(PersistenceStrategy):
    """Persistence strategy that creates one file per URL in domain folders."""
    
    def __init__(self, output_dir: str):
        """
        Initialize FolderPerDomainStrategy.
        
        Args:
            output_dir: Base output directory
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._saved_files: List[SavedFileInfo] = []  # Track saved files for manifest
    
    def _build_file_path(self, url: str, extension: str = ".md") -> Path:
        """
        Build file path for URL in domain folder structure.
        
        Args:
            url: URL to build path for
            extension: File extension
            
        Returns:
            Full path to save file
        """
        domain = extract_domain(url)
        if not domain:
            domain = "unknown"
        
        # Create domain directory
        domain_dir = self.output_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        
        # Build filename from URL path
        parsed_url = urlparse(url)
        url_path = parsed_url.path
        
        if not url_path or url_path == '/':
            filename = "index"
        else:
            # Remove leading slash and replace path separators
            filename = url_path.lstrip('/').replace('/', '_')
        
        # Sanitize filename
        filename = sanitize_filename(filename)
        
        # Add extension
        if not filename.endswith(extension):
            filename += extension
        
        # Handle filename length limit
        max_file_name_len = 120
        if len(filename) > max_file_name_len:
            # Truncate and add hash
            name_part = filename[:max_file_name_len - 33]  # 32 for hash + 1 for underscore
            hash_part = create_url_hash(url)[:8]
            filename = f"{name_part}_{hash_part}{extension}"
        
        return domain_dir / filename
    
    async def save(self, url: str, content: str) -> str:
        """
        Save content to domain folder.
        
        Args:
            url: URL of the content
            content: Content to save
            
        Returns:
            Path where content was saved
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for URL: {url}")
            return ""
        
        file_path = self._build_file_path(url, ".md")
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self._saved_files.append(SavedFileInfo(
                url=url,
                path=str(file_path),
                size=len(content)
            ))
            
            logger.debug(f"Saved content to: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save content for {url}: {e}")
            return ""
    
    async def finalize(self) -> None:
        """No finalization needed for folder per domain."""
        logger.info(f"FolderPerDomainStrategy completed. Saved {len(self._saved_files)} files.")
    
    def get_saved_files(self) -> List[SavedFileInfo]:
        """Get list of saved files for manifest generation."""
        return self._saved_files.copy()


class FilePerDomainStrategy(PersistenceStrategy):
    """Persistence strategy that aggregates content per domain into single files."""
    
    def __init__(self, output_dir: str, buffer_size: int = 100, flush_size_mb: int = 10):
        """
        Initialize FilePerDomainStrategy.
        
        Args:
            output_dir: Base output directory
            buffer_size: Number of items to buffer before flushing
            flush_size_mb: Size in MB to flush buffer
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.buffer_size = buffer_size
        self.flush_size_mb = flush_size_mb * 1024 * 1024  # Convert to bytes
        self.buffers = defaultdict(list)  # domain -> list of content items
        self.buffer_sizes = defaultdict(int)  # domain -> current buffer size in bytes
        self._saved_files: List[SavedDomainFileInfo] = []  # Track final files for manifest
    
    def _should_flush(self, domain: str) -> bool:
        """Check if buffer should be flushed for domain."""
        return (
            len(self.buffers[domain]) >= self.buffer_size or
            self.buffer_sizes[domain] >= self.flush_size_mb
        )
    
    async def _flush_domain(self, domain: str) -> str:
        """
        Flush buffer for a specific domain to file.
        
        Args:
            domain: Domain to flush
            
        Returns:
            Path to created file
        """
        if not self.buffers[domain]:
            return ""
        
        # Create domain file
        domain_file = self.output_dir / f"{domain}.md"
        
        # Write all buffered content for this domain
        try:
            with open(domain_file, 'w', encoding='utf-8') as f:
                for i, item in enumerate(self.buffers[domain]):
                    if i > 0:
                        f.write("\n\n---\n\n")  # Separator between pages
                    
                    f.write(f"# {item['url']}\n\n")
                    f.write(item['content'])
            
            # Track saved file
            total_size = sum(len(item['content']) for item in self.buffers[domain])
            self._saved_files.append(SavedDomainFileInfo(
                domain=domain,
                path=str(domain_file),
                pages=len(self.buffers[domain]),
                size=total_size,
                urls=[item['url'] for item in self.buffers[domain]]
            ))
            
            logger.info(f"Flushed {len(self.buffers[domain])} pages for domain {domain} to {domain_file}")
            
            # Clear buffer
            self.buffers[domain] = []
            self.buffer_sizes[domain] = 0
            
            return str(domain_file)
            
        except Exception as e:
            logger.error(f"Failed to flush domain {domain}: {e}")
            return ""
    
    async def save(self, url: str, content: str) -> str:
        """
        Buffer content for domain aggregation.
        
        Args:
            url: URL of the content
            content: Content to save
            
        Returns:
            Path where content will be saved (after finalization)
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for URL: {url}")
            return ""
        
        domain = extract_domain(url)
        if not domain:
            domain = "unknown"
        
        # Add to buffer
        item = {
            "url": url,
            "content": content
        }
        
        self.buffers[domain].append(item)
        self.buffer_sizes[domain] += len(content)
        
        logger.debug(f"Buffered content for {domain}: {url}")
        
        # Check if we should flush
        if self._should_flush(domain):
            await self._flush_domain(domain)
        
        # Return expected final path
        return str(self.output_dir / f"{domain}.md")
    
    async def finalize(self) -> None:
        """Flush all remaining buffers to domain files."""
        logger.info("Finalizing FilePerDomainStrategy - flushing all buffers")
        
        for domain in list(self.buffers.keys()):
            if self.buffers[domain]:  # Only flush non-empty buffers
                await self._flush_domain(domain)
        
        logger.info(f"FilePerDomainStrategy completed. Created {len(self._saved_files)} domain files.")
    
    def get_saved_files(self) -> List[SavedDomainFileInfo]:
        """Get list of saved files for manifest generation."""
        return self._saved_files.copy()


def create_persistence_strategy(
    strategy: str, 
    output_dir: str, 
    **kwargs
) -> PersistenceStrategy:
    """
    Factory function to create persistence strategy.
    
    Args:
        strategy: Strategy name ("folder_per_domain" or "file_per_domain")
        output_dir: Output directory
        **kwargs: Additional strategy-specific parameters
        
    Returns:
        Configured persistence strategy
        
    Raises:
        ValueError: If strategy is not supported
    """
    if strategy == "folder_per_domain":
        return FolderPerDomainStrategy(output_dir)
    elif strategy == "file_per_domain":
        buffer_size = kwargs.get("buffer_size", 100)
        flush_size_mb = kwargs.get("flush_size_mb", 10)
        return FilePerDomainStrategy(output_dir, buffer_size, flush_size_mb)
    else:
        raise ValueError(f"Unsupported persistence strategy: {strategy}")
