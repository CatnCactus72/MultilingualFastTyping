# core/conflicts/framework.py
from dataclasses import dataclass
from typing import List, Literal, Optional

IssueLevel = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    level: IssueLevel
    message: str
    context: Optional[str] = None