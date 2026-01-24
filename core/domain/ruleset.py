"""
Ruleset Model: Centralized evidence-based rule system for test generation.

The Ruleset is the single source of truth that extracts signals from AC bullets
and QA Prep bullets, enabling deterministic test generation.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import re


@dataclass
class EvidenceBullet:
    """Represents a single evidence bullet (AC or QA Prep)."""
    id: str  # e.g., "AC1", "QA-1"
    text: str
    source: str  # "AC" or "QA_PREP"
    signals: Set[str] = field(default_factory=set)  # Signal types extracted


@dataclass
class Signal:
    """Represents a signal extracted from evidence."""
    signal_type: str  # e.g., "availability", "action", "state", "visibility", etc.
    value: Optional[str] = None  # e.g., "Edit menu" for entry_point, "Windows 11" for platform
    evidence_refs: List[str] = field(default_factory=list)  # IDs of bullets that support this signal


@dataclass
class Ruleset:
    """
    Centralized ruleset that extracts and stores signals from AC and QA Prep.
    
    This is the single source of truth for test generation - all generators
    must check Ruleset.has_signal() before adding any test or step.
    """
    story_id: int
    ac_bullets: List[EvidenceBullet] = field(default_factory=list)
    qa_prep_bullets: List[EvidenceBullet] = field(default_factory=list)
    
    # Signal maps: signal_type -> Signal
    signals: Dict[str, Signal] = field(default_factory=dict)
    
    # Explicit signals extracted
    has_availability: bool = False
    has_action: bool = False
    has_state_change: bool = False
    has_visibility: bool = False
    has_constraint: bool = False
    has_undo_redo: bool = False
    has_accessibility: bool = False
    has_persistence: bool = False
    
    # Entry points
    entry_points: Set[str] = field(default_factory=set)  # e.g., "Edit menu", "Toolbar"
    
    # Platforms
    platforms: Set[str] = field(default_factory=set)  # e.g., "Windows 11", "iPad", "Android Tablet"
    
    # Units (for measurements)
    units: Set[str] = field(default_factory=set)  # e.g., "metric", "imperial"
    
    # Constraints
    requires_selection: bool = False
    object_type_constraints: Set[str] = field(default_factory=set)  # e.g., "rectangle", "circle"
    
    # Explicit negatives
    explicit_negatives: Set[str] = field(default_factory=set)  # e.g., "no selection", "empty canvas"
    
    # Explicit feedback
    explicit_feedback: bool = False
    
    # Explicit layout behavior
    explicit_layout_behavior: bool = False
    
    # Explicit hotkeys
    explicit_hotkeys: bool = False
    
    # Explicit accessibility standard
    explicit_accessibility_standard: Optional[str] = None  # e.g., "WCAG 2.1 AA"
    
    def __post_init__(self):
        """Extract signals from bullets after initialization."""
        self._extract_signals()
    
    def add_ac_bullet(self, bullet_id: str, text: str):
        """Add an AC bullet and extract signals."""
        bullet = EvidenceBullet(id=bullet_id, text=text, source="AC")
        self.ac_bullets.append(bullet)
        self._extract_signals_from_bullet(bullet)
        self._extract_signals()  # Re-extract all signals
    
    def add_qa_prep_bullet(self, bullet_id: str, text: str):
        """Add a QA Prep bullet and extract signals."""
        bullet = EvidenceBullet(id=bullet_id, text=text, source="QA_PREP")
        self.qa_prep_bullets.append(bullet)
        self._extract_signals_from_bullet(bullet)
        self._extract_signals()  # Re-extract all signals
    
    def _extract_signals_from_bullet(self, bullet: EvidenceBullet):
        """Extract signals from a single bullet."""
        text_lower = bullet.text.lower()
        
        # Signal type detection
        if any(word in text_lower for word in ['available', 'accessible', 'can be activated', 'is displayed']):
            bullet.signals.add('availability')
            self.has_availability = True
        
        if any(word in text_lower for word in ['add', 'remove', 'enable', 'disable', 'toggle', 'activate', 'deactivate']):
            bullet.signals.add('action')
            self.has_action = True
        
        if any(word in text_lower for word in ['state', 'enabled', 'disabled', 'active', 'inactive']):
            bullet.signals.add('state')
            self.has_state_change = True
        
        if any(word in text_lower for word in ['visible', 'hidden', 'displayed', 'shown', 'appears']):
            bullet.signals.add('visibility')
            self.has_visibility = True
        
        if any(word in text_lower for word in ['constraint', 'limit', 'boundary', 'maximum', 'minimum']):
            bullet.signals.add('constraint')
            self.has_constraint = True
        
        if 'undo' in text_lower or 'redo' in text_lower:
            bullet.signals.add('undo_redo')
            self.has_undo_redo = True
        
        if any(word in text_lower for word in ['accessibility', 'keyboard', 'screen reader', 'voiceover', 'talkback', 'wcag']):
            bullet.signals.add('accessibility')
            self.has_accessibility = True
        
        if any(word in text_lower for word in ['persist', 'save', 'retain', 'remember']):
            bullet.signals.add('persistence')
            self.has_persistence = True
        
        # Entry point extraction
        entry_patterns = [
            r'from (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar|dialog))',
            r'in (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar|dialog))',
            r'via (?:the )?([A-Z][a-z]+ (?:menu|panel|toolbar|dialog))',
        ]
        for pattern in entry_patterns:
            matches = re.findall(pattern, bullet.text, re.IGNORECASE)
            for match in matches:
                self.entry_points.add(match.strip())
        
        # Platform extraction
        if 'windows' in text_lower or 'win11' in text_lower:
            self.platforms.add('Windows 11')
        if 'ipad' in text_lower:
            self.platforms.add('iPad')
        if 'android' in text_lower or 'tablet' in text_lower:
            self.platforms.add('Android Tablet')
        
        # Unit extraction
        if 'metric' in text_lower or 'imperial' in text_lower:
            if 'metric' in text_lower:
                self.units.add('metric')
            if 'imperial' in text_lower:
                self.units.add('imperial')
        
        # Selection requirement
        if 'select' in text_lower or 'selection' in text_lower:
            self.requires_selection = True
        
        # Object type constraints
        object_types = ['rectangle', 'circle', 'triangle', 'arrow', 'line', 'polygon', 'text']
        for obj_type in object_types:
            if obj_type in text_lower:
                self.object_type_constraints.add(obj_type)
        
        # Explicit negatives
        if 'no selection' in text_lower or 'without selection' in text_lower:
            self.explicit_negatives.add('no_selection')
        if 'empty canvas' in text_lower or 'no objects' in text_lower:
            self.explicit_negatives.add('empty_canvas')
        
        # Explicit feedback
        if any(word in text_lower for word in ['feedback', 'notification', 'message', 'alert']):
            self.explicit_feedback = True
        
        # Explicit layout behavior
        if any(word in text_lower for word in ['layout', 'position', 'arrange', 'space', 'occupy']):
            self.explicit_layout_behavior = True
        
        # Explicit hotkeys
        if any(word in text_lower for word in ['hotkey', 'shortcut', 'key combination', 'ctrl+', 'cmd+']):
            self.explicit_hotkeys = True
        
        # Explicit accessibility standard
        wcag_match = re.search(r'wcag\s*(\d+\.\d+)?\s*([A-Z]+)?', text_lower)
        if wcag_match:
            level = wcag_match.group(2) or 'AA'
            self.explicit_accessibility_standard = f"WCAG {wcag_match.group(1) or '2.1'} {level}"
    
    def _extract_signals(self):
        """Extract and consolidate all signals from all bullets."""
        # Consolidate signals from all bullets
        for bullet in self.ac_bullets + self.qa_prep_bullets:
            for signal_type in bullet.signals:
                if signal_type not in self.signals:
                    self.signals[signal_type] = Signal(signal_type=signal_type, evidence_refs=[])
                self.signals[signal_type].evidence_refs.append(bullet.id)
    
    def has_signal(self, signal_type: str, value: Optional[str] = None) -> bool:
        """
        Check if a signal exists in the ruleset.
        
        Args:
            signal_type: Type of signal (e.g., "availability", "action", "accessibility")
            value: Optional value to check (e.g., "Windows 11" for platform)
        
        Returns:
            True if signal exists, False otherwise
        """
        if signal_type == 'platform':
            return value in self.platforms if value else len(self.platforms) > 0
        elif signal_type == 'entry_point':
            return value in self.entry_points if value else len(self.entry_points) > 0
        elif signal_type == 'unit':
            return value in self.units if value else len(self.units) > 0
        elif signal_type == 'object_type':
            return value in self.object_type_constraints if value else len(self.object_type_constraints) > 0
        elif signal_type == 'negative':
            return value in self.explicit_negatives if value else len(self.explicit_negatives) > 0
        else:
            return signal_type in self.signals
    
    def get_evidence_refs(self, signal_type: str) -> List[str]:
        """Get evidence references for a signal type."""
        if signal_type in self.signals:
            return self.signals[signal_type].evidence_refs
        return []
    
    def get_all_ac_ids(self) -> List[str]:
        """Get all AC bullet IDs."""
        return [bullet.id for bullet in self.ac_bullets]
    
    def get_all_qa_prep_ids(self) -> List[str]:
        """Get all QA Prep bullet IDs."""
        return [bullet.id for bullet in self.qa_prep_bullets]
