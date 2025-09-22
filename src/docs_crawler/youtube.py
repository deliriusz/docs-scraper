"""
YouTube module for docs_crawler v2.

Handles YouTube transcript extraction using YouTubeTranscriptApi.
"""

import logging
import re
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from .persistence import PersistenceStrategy

logger = logging.getLogger(__name__)


class YouTubeTranscriptExtractor:
    """Handles YouTube transcript extraction."""
    
    def __init__(self, persistence: Optional[PersistenceStrategy] = None):
        """
        Initialize YouTubeTranscriptExtractor.
        
        Args:
            persistence: Optional persistence strategy for saving transcripts
        """
        self.persistence = persistence
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID or None if not found
        """
        pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(pattern, url)
        return match.group(1) if match else None
    
    def get_transcript(self, url: str) -> str:
        """
        Get transcript for YouTube video.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Transcript text or empty string if failed
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.warning(f"No video ID found in URL: {url}")
            return ""
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(['en'])
            
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript.fetch())
            
            # Clean up transcript
            transcript_text = re.sub(r'\[\d+:\d+:\d+\]', '', transcript_text)  # Remove timecodes
            transcript_text = re.sub(r'<\w+>', '', transcript_text)  # Remove speaker tags
            
            logger.info(f"Successfully extracted transcript for: {url}")
            return transcript_text
            
        except Exception as e:
            logger.error(f"Error extracting transcript for {url}: {e}")
            return ""
    
    async def save_transcript(self, url: str) -> Optional[str]:
        """
        Extract and save transcript for YouTube video.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Path where transcript was saved, or None if failed
        """
        if not self.persistence:
            logger.warning("No persistence strategy configured for YouTube transcripts")
            return None
        
        transcript_text = self.get_transcript(url)
        if not transcript_text:
            return None
        
        # Create a special URL for YouTube transcripts
        video_id = self.extract_video_id(url)
        if not video_id:
            return None
        
        # Create a YouTube-specific URL for persistence
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Format transcript as markdown
        markdown_content = f"# YouTube Transcript: {video_id}\n\n**URL:** {url}\n\n{transcript_text}"
        
        # Save using persistence strategy
        path = await self.persistence.save(youtube_url, markdown_content)
        if path:
            logger.info(f"Saved YouTube transcript: {url} -> {path}")
        
        return path
