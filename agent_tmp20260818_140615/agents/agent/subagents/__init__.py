"""
Subagents package for Ms. Agenica S Multi-Agent System.
"""

from .inbox_helper import InboxHelperSubagent, INBOX_HELPER_INSTRUCTIONS
from .scheduling_assistant import SchedulingAssistantSubagent, SCHEDULING_INSTRUCTIONS
from .content_creator import ContentCreatorSubagent, CONTENT_CREATOR_INSTRUCTIONS

__all__ = [
    "InboxHelperSubagent",
    "INBOX_HELPER_INSTRUCTIONS",
    "SchedulingAssistantSubagent",
    "SCHEDULING_INSTRUCTIONS",
    "ContentCreatorSubagent",
    "CONTENT_CREATOR_INSTRUCTIONS",
]
