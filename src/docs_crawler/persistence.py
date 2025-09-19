"""
Persistence module for docs_crawler v2.

Handles different persistence strategies for saving crawled content.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PersistenceStrategy(ABC):
    """Abstract base class for persistence strategies."""
    
    @abstractmethod
    async def save(self, url: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save content for a URL.
        
        Args:
            url: URL of the content
            content: Content to save
            metadata: Optional metadata
            
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
        self.output_dir = output_dir
    
    async def save(self, url: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save content to domain folder."""
        # TODO: Implement folder per domain persistence
        logger.debug(f"Saving to folder per domain: {url}")
        return ""
    
    async def finalize(self) -> None:
        """No finalization needed for folder per domain."""
        pass


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
        self.output_dir = output_dir
        self.buffer_size = buffer_size
        self.flush_size_mb = flush_size_mb
        self.buffers = {}
    
    async def save(self, url: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Buffer content for domain aggregation."""
        # TODO: Implement file per domain persistence with buffering
        logger.debug(f"Buffering for file per domain: {url}")
        return ""
    
    async def finalize(self) -> None:
        """Merge buffered content into domain files."""
        # TODO: Implement finalization and merging
        logger.debug("Finalizing file per domain persistence")
