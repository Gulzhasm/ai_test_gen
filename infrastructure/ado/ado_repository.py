"""
Azure DevOps repository implementation.
"""
from typing import Optional
import re

from core.domain.story import UserStory
from core.interfaces.repository import IStoryRepository
from core.config import ADOConfig
from src.ado_client import ADOClient


class ADOStoryRepository(IStoryRepository):
    """Azure DevOps implementation of story repository."""
    
    def __init__(self, config: ADOConfig):
        """Initialize repository with ADO configuration.
        
        Args:
            config: Azure DevOps configuration
        """
        if not config.pat:
            raise ValueError("ADO_PAT environment variable is required")
        self.config = config
        self._client = None
    
    @property
    def client(self) -> ADOClient:
        """Lazy-load ADO client."""
        if self._client is None:
            # Temporarily set config values for ADOClient compatibility
            import config as old_config
            old_config.ADO_PAT = self.config.pat
            old_config.BASE_URL = self.config.base_url
            self._client = ADOClient()
        return self._client
    
    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID.
        
        Args:
            story_id: The story ID
            
        Returns:
            UserStory if found, None otherwise
        """
        try:
            story_data = self.client.extract_story_data(story_id)
            acceptance_criteria = self.client.parse_acceptance_criteria(
                story_data['acceptance_criteria_text']
            )
            
            return UserStory(
                story_id=story_data['story_id'],
                title=story_data['title'],
                description=story_data['description_text'],
                acceptance_criteria_text=story_data['acceptance_criteria_text'],
                acceptance_criteria=acceptance_criteria
            )
        except Exception as e:
            print(f"Error retrieving story {story_id}: {e}")
            return None
