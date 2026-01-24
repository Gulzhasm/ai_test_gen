"""
Feature extraction and analysis domain logic.
"""
import re
from typing import Optional


class FeatureExtractor:
    """Extracts feature name from story title."""
    
    TITLE_PREFIXES = ['As a', 'As an', 'I want', 'I need']
    
    @staticmethod
    def extract_feature_name(story_title: str) -> str:
        """Extract feature name from story title.
        
        Args:
            story_title: The user story title
            
        Returns:
            Extracted feature name
        """
        title = story_title.strip()
        
        for prefix in FeatureExtractor.TITLE_PREFIXES:
            if title.lower().startswith(prefix.lower()):
                parts = title.split(',')
                if len(parts) > 1:
                    title = parts[1].strip() if len(parts) > 1 else title.replace(prefix, '').strip()
                else:
                    title = title.replace(prefix, '').strip()
                break
        
        return title
    
    @staticmethod
    def sanitize_filename(text: str, max_length: int = 50) -> str:
        """Sanitize text for use in filenames.
        
        Args:
            text: Text to sanitize
            max_length: Maximum length for filename
            
        Returns:
            Sanitized filename-safe string
        """
        # Remove or replace characters that are problematic in filenames
        text = re.sub(r'[:/\\<>"|?*]', '_', text)
        # Replace multiple spaces/underscores with single underscore
        text = re.sub(r'[\s_]+', '_', text)
        # Remove leading/trailing underscores
        text = text.strip('_')
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        return text
