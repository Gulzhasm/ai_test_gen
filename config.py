"""
Configuration module for ADO Test Case Generator.
All configuration values are centralized here.
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
    # python-dotenv not installed or .env file not accessible, skip loading .env file
    pass

# Azure DevOps Configuration
ADO_ORG: str = os.getenv("ADO_ORG", "cdpinc")
ADO_PROJECT: str = os.getenv("ADO_PROJECT", "Env")
ADO_PAT: Optional[str] = os.getenv("ADO_PAT")
ADO_AREA_PATH: str = os.getenv("ADO_AREA_PATH", "Env\\ENV Kanda")
BASE_URL: str = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}"

# Test Case Configuration
ASSIGNED_TO: str = os.getenv("ASSIGNED_TO", "gulzhas.mailybayeva@kandasoft.com")
DEFAULT_STATE: str = os.getenv("DEFAULT_STATE", "Design")

# Test Design Rules
FORBIDDEN_WORDS: list = ['or / OR', 'if available', 'if supported', 'ambiguous']
FORBIDDEN_AREA_TERMS: list = ['Functionality', 'Accessibility', 'Behavior', 'Validation', 'General', 'System']

ALLOWED_AREAS: list = [
    'File Menu', 'Edit Menu', 'Tools Menu', 'Properties Panel', 'Dimensions Panel',
    'Canvas', 'Dialog Window', 'Modal Window', 'Top Action Toolbar'
]

# Objective Formatting Rules - Generic patterns for important test terms
OBJECTIVE_KEY_TERM_PATTERNS: list = [
    # UI Surfaces (menus, panels, locations)
    r'\b(?:File|Edit|Tools|View|Help|Insert|Format|Window) Menu\b',
    r'\bProperties Panel\b',
    r'\bDimensions Panel\b',
    r'\bTop Action Toolbar\b',
    r'\bToolbar\b',
    r'\bCanvas\b',
    r'\bDialog(?:\s+Window)?\b',
    r'\bModal(?:\s+Window)?\b',

    # Controls and UI elements
    r'\b(?:color picker|dropdown|button|checkbox|radio button|slider|toggle|input field)\b',
    r'\b(?:Line Color|Line Thickness|Line Type)\b',
    r'\b(?:Solid|Dashed|Dotted)\b',

    # Actions and operations
    r'\b(?:Undo|Redo|Cut|Copy|Paste|Delete|Duplicate)\b',
    r'\b(?:Rotate|Mirror|Flip|Transform|Scale|Move|Resize)\b',
    r'\b(?:horizontal|vertical)(?:\s+flip)?\b',
    r'\b(?:mirror operations|flip operations|transformation operations)\b',

    # Platforms and devices
    r'\b(?:Windows 11|Windows 10|macOS|iPad|Android Tablet|iPhone|Android Phone)\b',
    r'\b(?:Tablets|Desktop|Mobile)\b',

    # Accessibility tools and standards
    r'\bAccessibility Insights(?:\s+for\s+Windows)?\b',
    r'\bVoiceOver\b',
    r'\bAccessibility Scanner\b',
    r'\bNarrator\b',
    r'\bTalkBack\b',
    r'\bJAWS\b',
    r'\bNVDA\b',
    r'\bWCAG\s+\d+\.\d+\s+(?:A|AA|AAA)\b',
    r'\bARIA\s+(?:roles|labels)\b',
    r'\bSection 508\b',

    # Accessibility features
    r'\b(?:keyboard navigation|screen reader|focus indicators|accessible name|accessible role)\b',
    r'\b(?:contrast ratio|color contrast|focus visible|focus order)\b',
    r'\b(?:semantic markup|alt text|aria-label)\b',

    # Measurement and precision
    r'\b(?:diameter|perimeter|radius|width|height|area|length)\b',
    r'\b(?:measurement label|measurement line)\b',

    # State and behavior
    r'\b(?:immediately|in-place|real-time|live)\b',
    r'\b(?:disabled|enabled|visible|hidden|selected|deselected)\b',
    r'\b(?:independent|separately|without affecting)\b',

    # Object types
    r'\b(?:line-based object|ellipse|rectangle|polygon|circle|shape|object|image)\b',
    r'\b(?:selected object|drawn object)\b',

    # Properties
    r'\b(?:stroke|fill|color|thickness|pattern|style)\b',
    r'\b(?:proportions|aspect ratio|dimensions)\b',
]

# Output Configuration
OUTPUT_DIR: str = "output"

# LLM Configuration
LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # 'openai' or 'ollama'
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")  # gpt-4o-mini, gpt-4o, or ollama model
LLM_ENDPOINT: str = os.getenv("LLM_ENDPOINT", "http://localhost:11434")  # For Ollama only
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# OpenAI Configuration
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
