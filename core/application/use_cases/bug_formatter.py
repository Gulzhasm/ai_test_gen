"""HTML formatter for BugReport following ENV Drawing Bug Template (Karen's Rules).

Matches the exact ADO HTML structure used in real bugs (e.g., Bug #279389).

Template sections (in order):
    ISSUE:
    ADDITIONAL INFORMATION:
    SUPPORTING DOCUMENTATION PROVIDED:
    RECREATE STEPS:
    Sections below for development use
    TRIAGE/CAUSE INFORMATION:
    FIX SUMMARY:

Formatting rules:
    - ISSUE starts on SAME line as heading (no CRLF), text in italics
    - RECREATE STEPS uses strict numbered/lettered/roman indentation
    - << NOT EXPECTED appears only at failure point (yellow highlight, bold)
    - Expected behavior nested under NOT EXPECTED line (roman numerals)
    - Attachments referenced in expected behavior items (bolded filenames)
    - No extra blank lines anywhere
    - Menu arrows use → character
"""
from core.domain.bug_report import BugReport, RecreateStep, BugObservation


class BugHtmlFormatter:
    """Formats BugReport into ADO-compatible HTML for Microsoft.VSTS.TCM.ReproSteps field."""

    def format(self, bug: BugReport) -> str:
        """Convert BugReport to full ADO HTML string."""
        parts = [
            self._format_issue(bug),
            self._format_additional_info(bug),
            self._format_attachments(bug),
            self._format_recreate_steps(bug),
            self._format_dev_sections(),
        ]
        return ''.join(parts)

    def _format_issue(self, bug: BugReport) -> str:
        """ISSUE: <one sentence, same line as heading, in italics>"""
        return f'<div><b>ISSUE:</b>&nbsp;<i>{self._escape(bug.issue)}</i></div>'

    def _format_additional_info(self, bug: BugReport) -> str:
        """ADDITIONAL INFORMATION: content in italics, or empty."""
        html = '<div><b>ADDITIONAL INFORMATION:</b>&nbsp;'
        if bug.additional_info:
            info_text = '; '.join(bug.additional_info)
            html += f'<i>{self._escape(info_text)}</i>'
        html += '</div>'
        return html

    def _format_attachments(self, bug: BugReport) -> str:
        """SUPPORTING DOCUMENTATION PROVIDED: bulleted list with bold filenames."""
        html = '<div><b>SUPPORTING DOCUMENTATION PROVIDED:</b>&nbsp;</div>'
        if bug.attachments:
            html += '<div><ul style="padding:0px 0px 0px 40px;">'
            for filename in bug.attachments:
                html += f'<li><b>{self._escape(filename)}</b></li>'
            html += '</ul></div>'
        return html

    def _format_recreate_steps(self, bug: BugReport) -> str:
        """RECREATE STEPS: numbered steps with nested observations.

        Structure:
        1. Step text
        2. Step text
        3. Step text
           a. Observation << NOT EXPECTED
              i. Expected behavior
              ii. Please see screenshot <filename>
        """
        html = '<div><b>RECREATE STEPS:</b>&nbsp;</div>'
        html += '<div><ol style="padding-left:40px;">'

        for step in bug.steps:
            html += f'<li>{self._escape(step.action)}</li>'

            if step.observations:
                # Close the main <ol> temporarily and open a nested one
                # ADO uses nested <ol> inside the parent <ol> for sub-items
                html += f'<ol style="padding-left:40px;list-style:lower-alpha;">'
                for obs in step.observations:
                    obs_html = self._format_observation(obs)
                    html += f'<li>{obs_html}</li>'

                    if obs.expected_behaviors:
                        html += '<ol style="padding-left:40px;list-style:lower-roman;">'
                        for expected in obs.expected_behaviors:
                            html += f'<li>{self._escape(expected)}</li>'
                        # Add attachment reference as a separate item if present
                        if obs.attachment:
                            html += (
                                f'<li>Please see the screenshot&nbsp;'
                                f'<b>{self._escape(obs.attachment)}</b></li>'
                            )
                        html += '</ol>'
                    elif obs.attachment:
                        # No expected behaviors but has attachment
                        html += '<ol style="padding-left:40px;list-style:lower-roman;">'
                        html += (
                            f'<li>Please see the screenshot&nbsp;'
                            f'<b>{self._escape(obs.attachment)}</b></li>'
                        )
                        html += '</ol>'

                html += '</ol>'

        html += '</ol></div>'
        return html

    def _format_observation(self, obs: BugObservation) -> str:
        """Format observation line with yellow-highlighted << NOT EXPECTED marker."""
        text = self._escape(obs.text)

        if obs.is_not_expected:
            text += (
                '&nbsp;<span style="background-color:rgb(255, 255, 0);">'
                '<b>&lt;&lt; NOT EXPECTED</b></span>'
            )

        return text

    def _format_dev_sections(self) -> str:
        """Development sections: triage + fix summary (empty by default)."""
        html = '<div><b><i><u>Sections below for development use</u></i></b></div>'
        html += '<div><b>TRIAGE/CAUSE INFORMATION:</b>&nbsp;</div>'
        html += '<div><br/></div>'
        html += '<div><b>FIX SUMMARY:</b>&nbsp;</div>'
        html += '<div><br/></div>'
        return html

    @staticmethod
    def _escape(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
