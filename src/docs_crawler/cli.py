"""
CLI module for docs_crawler v2.

Provides command-line interface and orchestration logic.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import load_config
from .base import C4ABase
from .batch_runner import BatchRunner
from .deepcrawl_runner import DeepCrawlRunner
from .youtube import YouTubeTranscriptExtractor
from .persistence import create_persistence_strategy

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


async def run_crawler(
    config_path: str,
    output_dir: str,
    dry_run: bool = False,
    verbose: bool = False
) -> None:
    """
    Main crawler orchestration function.
    
    Args:
        config_path: Path to configuration file
        output_dir: Output directory for crawled content
        threads: Number of concurrent threads
        dry_run: If True, only print URLs without crawling
        verbose: Enable verbose logging
    """
    setup_logging(verbose)
    
    try:
        # Load configuration
        config = load_config(config_path)
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize persistence strategy
        persistence = create_persistence_strategy(
            config.persistence_strategy, 
            output_dir
        )
        
        # Initialize YouTube extractor with persistence
        youtube_extractor = YouTubeTranscriptExtractor(persistence)
        
        # Process YouTube URLs
        if config.youtube:
            logger.info(f"Processing {len(config.youtube)} YouTube URLs")
            for url in config.youtube:
                if dry_run:
                    logger.info(f"Would process YouTube: {url}")
                else:
                    path = await youtube_extractor.save_transcript(url)
                    if path:
                        logger.info(f"Saved YouTube transcript: {url} -> {path}")
                    else:
                        logger.warning(f"Failed to save YouTube transcript: {url}")
        
        # Split items into flat and deep crawling
        flat_items = [item for item in config.items if not item.should_scrap]
        deep_items = [item for item in config.items if item.should_scrap]
        
        logger.info(f"Found {len(flat_items)} flat items and {len(deep_items)} deep crawl items")
        
        # Run crawler with C4ABase context
        async with C4ABase(config.defaults) as base:
            # Process flat items
            if flat_items:
                logger.info("Processing flat items")
                batch_runner = BatchRunner(base, config.defaults, persistence)
                if not dry_run:
                    await batch_runner.run(flat_items)
                    stats = batch_runner.get_stats()
                    logger.info(f"Batch processing stats: {stats.success} success, {stats.failed} failed, {stats.skipped} skipped")
                else:
                    for item in flat_items:
                        logger.info(f"Would process flat: {item.url}")
            
            # Process deep crawl items
            for item in deep_items:
                logger.info(f"Processing deep crawl: {item.url}")
                deep_runner = DeepCrawlRunner(base, config.defaults, persistence)
                if not dry_run:
                    await deep_runner.run(item)
                    stats = deep_runner.get_stats()
                    logger.info(f"Deep crawl stats: {stats.success} success, {stats.failed} failed, {stats.skipped} skipped, max_depth: {stats.max_depth_reached}")
                else:
                    logger.info(f"Would deep crawl: {item.url}")
        
        # Finalize persistence
        await persistence.finalize()
        
        logger.info("Crawling completed successfully")
        
    except Exception as e:
        logger.error(f"Crawling failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Advanced web crawler for documentation sites using Crawl4AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  docs-crawler run config.json output/
  docs-crawler run config.json output/ --threads 10 --dry-run
  docs-crawler run config.json output/ --verbose
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the crawler')
    run_parser.add_argument('config_file', help='Path to JSON configuration file')
    run_parser.add_argument('output_dir', help='Directory to store crawled files')
    run_parser.add_argument('--dry-run', action='store_true',
                          help='Print URLs only, don\'t save files')
    run_parser.add_argument('--verbose', '-v', action='store_true',
                          help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        asyncio.run(run_crawler(
            config_path=args.config_file,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            verbose=args.verbose
        ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
