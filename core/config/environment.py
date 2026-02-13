"""
Environment Configuration Module

Loads environment variables for the test generation framework.
Project-specific configuration is managed through YAML files in projects/configs/.
"""
import os
from typing import Optional
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except (ImportError, PermissionError, OSError):
    pass


class EnvironmentConfig:
    """Environment configuration loaded from environment variables."""

    # Azure DevOps Authentication
    ADO_PAT: Optional[str] = os.getenv("ADO_PAT")

    # LLM Configuration
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_ENDPOINT: str = os.getenv("LLM_ENDPOINT", "http://localhost:11434")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    # Gemini Configuration
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")

    # Default Project (for backward compatibility)
    DEFAULT_PROJECT: str = os.getenv("DEFAULT_PROJECT", "env-quickdraw")

    @classmethod
    def validate(cls) -> bool:
        """Validate that required environment variables are set."""
        if not cls.ADO_PAT:
            print("Warning: ADO_PAT environment variable not set")
            return False
        return True

    @classmethod
    def get_llm_api_key(cls, provider_type: Optional[str] = None) -> Optional[str]:
        """Get the API key for the specified or configured LLM provider.

        Args:
            provider_type: Override provider type. If None, uses LLM_PROVIDER env var.
        """
        provider = (provider_type or cls.LLM_PROVIDER).lower()
        if provider == "gemini" or provider == "google":
            return cls.GEMINI_API_KEY
        elif provider == "anthropic" or provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY")
        else:
            return cls.OPENAI_API_KEY

    @classmethod
    def get_llm_config(cls) -> dict:
        """Get LLM configuration as a dictionary."""
        return {
            'enabled': cls.LLM_ENABLED,
            'provider': cls.LLM_PROVIDER,
            'model': cls.LLM_MODEL,
            'endpoint': cls.LLM_ENDPOINT,
            'timeout': cls.LLM_TIMEOUT,
            'max_retries': cls.LLM_MAX_RETRIES,
            'temperature': cls.LLM_TEMPERATURE,
            'api_key': cls.get_llm_api_key()
        }


# Backward compatibility exports
ADO_PAT = EnvironmentConfig.ADO_PAT
LLM_ENABLED = EnvironmentConfig.LLM_ENABLED
LLM_PROVIDER = EnvironmentConfig.LLM_PROVIDER
LLM_MODEL = EnvironmentConfig.LLM_MODEL
LLM_ENDPOINT = EnvironmentConfig.LLM_ENDPOINT
LLM_TIMEOUT = EnvironmentConfig.LLM_TIMEOUT
LLM_MAX_RETRIES = EnvironmentConfig.LLM_MAX_RETRIES
LLM_TEMPERATURE = EnvironmentConfig.LLM_TEMPERATURE
OPENAI_API_KEY = EnvironmentConfig.OPENAI_API_KEY
GEMINI_API_KEY = EnvironmentConfig.GEMINI_API_KEY
DEFAULT_PROJECT = EnvironmentConfig.DEFAULT_PROJECT

# Output directory (relative to project root)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
