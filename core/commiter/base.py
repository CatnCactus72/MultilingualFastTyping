# core/committer/base.py
from typing import Protocol
from core.composers.base import Action


class CommitterBackend(Protocol):
    mode: str

    def apply(self, action: Action, shown_text: str) -> None:
        ...

    def flush(self) -> None:
        ...