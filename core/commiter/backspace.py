# core/committer/backspace.py
from typing import Callable
from core.composers.base import Action, Passthrough, Replace


class BackspaceCommitter:
    """Chế độ mặc định: gửi n phím BackSpace rồi commit chuỗi mới."""

    mode = "backspace"

    def __init__(
        self,
        send_backspace: Callable[[int], None],
        commit_text: Callable[[str], None],
    ) -> None:
        self._send_backspace = send_backspace
        self._commit_text = commit_text

    def apply(self, action: Action, shown_text: str = "") -> bool:
        if isinstance(action, Passthrough):
            return False
        if isinstance(action, Replace):
            if action.delete_n > 0:
                self._send_backspace(action.delete_n)
            if action.text:
                self._commit_text(action.text)
            return True
        return False

    def flush(self) -> None:
        pass