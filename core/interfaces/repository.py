"""
Repository interfaces for data access.
"""
from abc import ABC, abstractmethod
from typing import Optional

from core.domain.story import UserStory


class IStoryRepository(ABC):
    """Interface for story data access."""
    
    @abstractmethod
    def get_story(self, story_id: int) -> Optional[UserStory]:
        """Retrieve a user story by ID.
        
        Args:
            story_id: The story ID
            
        Returns:
            UserStory if found, None otherwise
        """
        pass
