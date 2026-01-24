"""
Factory for creating test case generators based on story characteristics.
"""
from typing import List

from core.domain.story import UserStory
from core.interfaces.test_generator import ITestGenerator


class TestCaseGeneratorFactory:
    """Factory for selecting appropriate test generators."""
    
    def __init__(self, generators: List[ITestGenerator]):
        """Initialize factory with available generators.
        
        Args:
            generators: List of available test generators
        """
        self.generators = generators
    
    def get_generator(self, story: UserStory) -> ITestGenerator:
        """Get appropriate generator for the story.
        
        Args:
            story: The user story
            
        Returns:
            Appropriate test generator
            
        Raises:
            ValueError: If no generator can handle the story
        """
        for generator in self.generators:
            if generator.can_handle(story):
                return generator
        
        # Return first generator as default if none match
        if self.generators:
            return self.generators[0]
        
        raise ValueError("No test generators available")
