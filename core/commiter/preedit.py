# core/committer/preedit.py
from typing import Callable
from core.composers.base import Action, Passthrough, Preedit, Replace


class PreeditCommitter:
    """Chế độ preedit ẩn (micro_preedit) cho trình duyệt Chromium/Firefox (Mục 7)."""

    mode = "micro_preedit"

    def __init__(
        self,
        update_preedit: Callable[[str], None],
        hide_preedit: Callable[[], None],
        commit_text: Callable[[str], None],
    ) -> None:
        self._update_preedit = update_preedit
        self._hide_preedit = hide_preedit
        self._commit_text = commit_text
        self._buffer: str = ""

    def apply(self, action: Action, shown_text: str = "") -> bool:
        if isinstance(action, Preedit):
            self._buffer = action.text
            self._update_preedit(self._buffer)
            return True
        if isinstance(action, Replace):
            if shown_text:
                self._buffer = shown_text
            elif action.delete_n > 0:
                self._buffer = self._buffer[:-action.delete_n] + action.text
            else:
                self._buffer += action.text
            self._update_preedit(self._buffer)
            return True
        return False

    def flush(self) -> None:
        if self._buffer:
            text = self._buffer
            self._buffer = ""
            self._hide_preedit()
            self._commit_text(text)