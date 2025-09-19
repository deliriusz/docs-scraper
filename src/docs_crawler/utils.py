"""
Utility functions for docs_crawler v2.

Provides URL cleanup, deduplication, domain utilities, and hashing functions.
"""

import hashlib
import logging
import re
from typing import Set, List, Dict, Any
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# Global set to track visited URLs across all operations
VISITED_URLS: Set[str] = set()


def cleanup_url(url: str, strip_utm: bool = True) -> str:
    """
    Clean up URL by removing fragments, trailing slashes, and optionally UTM parameters.
    
    Args:
        url: URL to clean up
        strip_utm: Whether to remove UTM tracking parameters
        
    Returns:
        Cleaned URL
    """
    if not url:
        return url
    
    # Remove fragment
    url = url.split('#', 1)[0]
    
    # Remove trailing slash
    url = re.sub(r'/$', '', url)
    
    if strip_utm:
        # Remove UTM parameters
        parsed = urlparse(url)
        query_params = {}
        for key, value in parsed.query.split('&') if parsed.query else []:
            if '=' in key:
                k, v = key.split('=', 1)
                if not k.startswith('utm_'):
                    query_params[k] = v
        
        # Rebuild query string
        new_query = '&'.join(f"{k}={v}" for k, v in query_params.items())
        parsed = parsed._replace(query=new_query)
        url = urljoin(parsed.geturl(), '')
    
    return url


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent comparison and storage.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL
    """
    return cleanup_url(url, strip_utm=True)


def is_url_visited(url: str) -> bool:
    """
    Check if URL has been visited.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL has been visited
    """
    normalized_url = normalize_url(url)
    return normalized_url in VISITED_URLS


def mark_url_visited(url: str) -> None:
    """
    Mark URL as visited.
    
    Args:
        url: URL to mark as visited
    """
    normalized_url = normalize_url(url)
    VISITED_URLS.add(normalized_url)


def clear_visited_urls() -> None:
    """Clear all visited URLs."""
    VISITED_URLS.clear()


def get_visited_urls() -> Set[str]:
    """
    Get set of all visited URLs.
    
    Returns:
        Set of visited URLs
    """
    return VISITED_URLS.copy()


def deduplicate_urls(urls: List[str]) -> List[str]:
    """
    Remove duplicate URLs from list while preserving order.
    
    Args:
        urls: List of URLs to deduplicate
        
    Returns:
        List of unique URLs
    """
    seen = set()
    unique_urls = []
    
    for url in urls:
        normalized = normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(url)
    
    return unique_urls


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name or empty string if invalid
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception as e:
        logger.warning(f"Failed to extract domain from URL {url}: {e}")
        return ""


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if URLs are from the same domain
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    return domain1 and domain2 and domain1 == domain2


def is_subdomain(url1: str, url2: str) -> bool:
    """
    Check if url1 is a subdomain of url2.
    
    Args:
        url1: Potential subdomain URL
        url2: Base domain URL
        
    Returns:
        True if url1 is a subdomain of url2
    """
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    
    if not domain1 or not domain2:
        return False
    
    return domain1.endswith('.' + domain2) or domain1 == domain2


def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """
    Sanitize filename by removing/replacing invalid characters.
    
    Args:
        filename: Filename to sanitize
        max_length: Maximum length of filename
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', filename)
    
    # Replace multiple underscores with single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Truncate if too long
    if len(sanitized) > max_length:
        # Keep extension if present
        if '.' in sanitized:
            name, ext = sanitized.rsplit('.', 1)
            if len(ext) < 10:  # Reasonable extension length
                max_name_length = max_length - len(ext) - 1
                sanitized = name[:max_name_length] + '.' + ext
            else:
                sanitized = sanitized[:max_length]
        else:
            sanitized = sanitized[:max_length]
    
    return sanitized or "unnamed"


def create_file_hash(content: str, algorithm: str = "md5") -> str:
    """
    Create hash of content for unique identification.
    
    Args:
        content: Content to hash
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash string
    """
    if algorithm == "md5":
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(content.encode('utf-8')).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def create_url_hash(url: str, algorithm: str = "md5") -> str:
    """
    Create hash of URL for unique identification.
    
    Args:
        url: URL to hash
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash string
    """
    return create_file_hash(url, algorithm)


def build_output_path(base_dir: str, url: str, extension: str = ".md") -> str:
    """
    Build output file path for a URL.
    
    Args:
        base_dir: Base output directory
        url: URL to build path for
        extension: File extension
        
    Returns:
        Full output file path
    """
    domain = extract_domain(url)
    if not domain:
        domain = "unknown"
    
    # Create filename from URL
    url_path = urlparse(url).path
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
    
    # Build full path
    return f"{base_dir}/{domain}/{filename}"


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries, with later dictionaries taking precedence.
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def format_bytes(bytes_count: int) -> str:
    """
    Format byte count as human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"
