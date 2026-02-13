"""Parser for structured .txt bug files into BugReport domain objects."""
import re
from pathlib import Path
from typing import Dict, List, Optional

from core.domain.bug_report import BugReport, RecreateStep, BugObservation


class BugFileParser:
    """Parses structured .txt bug files into BugReport domain objects.

    Expected file format:
        TITLE: DRAW: Feature / Brief Description
        SEVERITY: 2 - High
        STORY_ID: 272261
        ITERATION: Sprint 42

        ISSUE: One sentence describing the bug.

        ADDITIONAL_INFO:
        - Extra info line 1
        - WCAG reference

        ATTACHMENTS:
        - screenshot.png
        - video.mp4

        STEPS:
        1. First step
        2. Second step
        3. Third step
           a. Observation text >> NOT EXPECTED (see attached screenshot.png)
              i. Expected behavior here

        SYSTEM_INFO:
        - OS: Windows 11
        - App Version: 3.2.4
    """

    # Section keys that start a new section
    SINGLE_LINE_KEYS = {'TITLE', 'SEVERITY', 'STORY_ID', 'ITERATION', 'ISSUE'}
    MULTI_LINE_KEYS = {'ADDITIONAL_INFO', 'ATTACHMENTS', 'STEPS', 'SYSTEM_INFO'}
    ALL_KEYS = SINGLE_LINE_KEYS | MULTI_LINE_KEYS

    # Regex for section header at start of line
    _SECTION_RE = re.compile(r'^([A-Z_]+):\s*(.*)', re.MULTILINE)

    # Regex for step parsing
    _NUMBERED_STEP_RE = re.compile(r'^(\d+)\.\s+(.+)')
    _LETTERED_OBS_RE = re.compile(r'^\s+([a-z])\.\s+(.+)')
    _ROMAN_EXPECTED_RE = re.compile(r'^\s+([ivxlc]+)\.\s+(.+)', re.IGNORECASE)
    _NOT_EXPECTED_RE = re.compile(r'(?:>>|<<)\s*NOT EXPECTED', re.IGNORECASE)
    _ATTACHMENT_REF_RE = re.compile(r'\(see attached\s+([^)]+)\)', re.IGNORECASE)

    def parse(self, file_path: str) -> BugReport:
        """Parse a .txt bug file into a BugReport.

        Args:
            file_path: Path to the .txt file

        Returns:
            BugReport domain object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required fields are missing
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Bug file not found: {file_path}")

        content = path.read_text(encoding='utf-8')
        return self.parse_content(content)

    def parse_content(self, content: str) -> BugReport:
        """Parse text content into a BugReport."""
        sections = self._extract_sections(content)

        # Validate required fields
        if not sections.get('TITLE', '').strip():
            raise ValueError("TITLE is required")
        if not sections.get('ISSUE', '').strip():
            raise ValueError("ISSUE is required")
        if not sections.get('STEPS', '').strip():
            raise ValueError("STEPS is required")

        # Parse story_id
        story_id = None
        story_id_str = sections.get('STORY_ID', '').strip()
        if story_id_str:
            try:
                story_id = int(story_id_str)
            except ValueError:
                raise ValueError(f"STORY_ID must be a number, got: {story_id_str}")

        return BugReport(
            title=sections.get('TITLE', '').strip(),
            issue=sections.get('ISSUE', '').strip(),
            severity=sections.get('SEVERITY', '2 - High').strip(),
            story_id=story_id,
            iteration=sections.get('ITERATION', '').strip() or None,
            additional_info=self._parse_bullet_list(sections.get('ADDITIONAL_INFO', '')),
            attachments=self._parse_bullet_list(sections.get('ATTACHMENTS', '')),
            steps=self._parse_steps(sections.get('STEPS', '')),
            system_info=self._parse_bullet_list(sections.get('SYSTEM_INFO', '')),
        )

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Split content into section key -> raw text pairs."""
        sections: Dict[str, str] = {}
        lines = content.split('\n')

        current_key: Optional[str] = None
        current_lines: List[str] = []

        for line in lines:
            # Check if this line starts a new section
            match = self._SECTION_RE.match(line)
            if match and match.group(1) in self.ALL_KEYS:
                # Save previous section
                if current_key:
                    sections[current_key] = '\n'.join(current_lines).strip()

                key = match.group(1)
                rest = match.group(2).strip()
                current_key = key

                if key in self.SINGLE_LINE_KEYS:
                    # Single-line keys: value is on the same line
                    sections[key] = rest
                    current_key = None
                    current_lines = []
                else:
                    # Multi-line keys: value starts on next lines
                    current_lines = [rest] if rest else []
            elif current_key:
                current_lines.append(line)

        # Save last section
        if current_key:
            sections[current_key] = '\n'.join(current_lines).strip()

        return sections

    def _parse_bullet_list(self, text: str) -> List[str]:
        """Parse bulleted list (lines starting with -)."""
        items = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- '):
                items.append(stripped[2:].strip())
            elif stripped.startswith('* '):
                items.append(stripped[2:].strip())
        return items

    def _parse_steps(self, steps_text: str) -> List[RecreateStep]:
        """Parse the STEPS section into RecreateStep objects.

        Handles:
        - Numbered steps: 1. 2. 3.
        - Lettered observations: a. b. (indented)
        - >> NOT EXPECTED markers
        - (see attached <filename>) references
        - Roman numeral expected items: i. ii. (deeper indented)
        """
        steps: List[RecreateStep] = []
        current_step: Optional[RecreateStep] = None
        current_obs: Optional[BugObservation] = None

        for line in steps_text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            # Check for numbered step: "1. Step text"
            num_match = self._NUMBERED_STEP_RE.match(stripped)
            if num_match:
                # Save current step
                if current_step:
                    if current_obs:
                        current_step.observations.append(current_obs)
                        current_obs = None
                    steps.append(current_step)

                current_step = RecreateStep(
                    number=int(num_match.group(1)),
                    action=num_match.group(2).strip()
                )
                current_obs = None
                continue

            # When inside an observation, check roman numerals FIRST
            # (because 'i.' matches both lettered and roman patterns)
            if current_obs:
                roman_match = self._ROMAN_EXPECTED_RE.match(line)
                # Use indentation depth: roman numerals are deeper than lettered obs
                leading_spaces = len(line) - len(line.lstrip())
                if roman_match and leading_spaces >= 6:
                    expected_text = roman_match.group(2).strip()
                    if expected_text.lower().startswith('expected:'):
                        expected_text = expected_text[9:].strip()
                    current_obs.expected_behaviors.append(expected_text)
                    continue

            # Check for lettered observation: "   a. Observation text"
            obs_match = self._LETTERED_OBS_RE.match(line)
            if obs_match and current_step:
                # Save previous observation
                if current_obs:
                    current_step.observations.append(current_obs)

                obs_text = obs_match.group(2).strip()

                # Check for << NOT EXPECTED or >> NOT EXPECTED
                is_not_expected = bool(self._NOT_EXPECTED_RE.search(obs_text))

                # Extract attachment reference
                attachment = None
                att_match = self._ATTACHMENT_REF_RE.search(obs_text)
                if att_match:
                    attachment = att_match.group(1).strip()

                # Clean observation text: remove NOT EXPECTED marker and attachment ref
                clean_text = self._NOT_EXPECTED_RE.sub('', obs_text).strip()
                clean_text = self._ATTACHMENT_REF_RE.sub('', clean_text).strip()

                current_obs = BugObservation(
                    text=clean_text,
                    is_not_expected=is_not_expected,
                    attachment=attachment,
                )
                continue

            # Fallback: check roman numeral without current_obs context
            roman_match = self._ROMAN_EXPECTED_RE.match(line)
            if roman_match and current_obs:
                expected_text = roman_match.group(2).strip()
                if expected_text.lower().startswith('expected:'):
                    expected_text = expected_text[9:].strip()
                current_obs.expected_behaviors.append(expected_text)
                continue

        # Save final step/observation
        if current_step:
            if current_obs:
                current_step.observations.append(current_obs)
            steps.append(current_step)

        return steps
