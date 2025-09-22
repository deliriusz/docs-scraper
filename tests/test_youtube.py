import asyncio
import pytest
from pathlib import Path

from src.docs_crawler.youtube import YouTubeTranscriptExtractor
from src.docs_crawler.persistence import create_persistence_strategy


class TestYouTube:
    """Test suite for YouTube transcript extraction functionality."""
    
    @pytest.mark.asyncio
    async def test_youtube_persistence(self, tmp_path):
        """Test YouTube transcript extraction with persistence."""
        # Create persistence strategy
        persistence = create_persistence_strategy("folder_per_domain", str(tmp_path))
        
        # Create YouTube extractor with persistence
        youtube_extractor = YouTubeTranscriptExtractor(persistence)
        
        # Test URLs (using a known video with transcript)
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll (has transcript)
            "https://youtu.be/dQw4w9WgXcQ",  # Short URL format
            "https://www.youtube.com/watch?v=invalid123",  # Invalid video ID
        ]
        
        for url in test_urls:
            print(f"\nTesting URL: {url}")
            
            # Test transcript extraction
            transcript = youtube_extractor.get_transcript(url)
            if transcript:
                print(f"✓ Transcript extracted ({len(transcript)} chars)")
            else:
                print("✗ Failed to extract transcript")
            
            # Test saving with persistence
            path = await youtube_extractor.save_transcript(url)
            if path:
                print(f"✓ Transcript saved to: {path}")
                
                # Verify file exists and has content
                if Path(path).exists():
                    content = Path(path).read_text(encoding='utf-8')
                    print(f"✓ File verified ({len(content)} chars)")
                else:
                    print("✗ File not found after saving")
            else:
                print("✗ Failed to save transcript")
        
        # Test persistence strategy saved files
        print(f"\nPersistence strategy saved files:")
        saved_files = persistence.get_saved_files()
        for file_info in saved_files:
            print(f"  - {file_info.url} -> {file_info.path} ({file_info.size} bytes)")
