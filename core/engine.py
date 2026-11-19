# core/engine.py
from typing import Optional
import core.composers.mapping  # Đảm bảo MappingComposer đã được đăng ký
import languages.vi.vi_vni
import languages.vi.vi_telex
from core.composers.base import (
    Action,
    Candidates,
    Composer,
    InputEvent,
    KeyEvent,
    Passthrough,
    Preedit,
    Replace,
    ResetEvent,
)
from core.loader import LanguagePack
from core.registry import get_composer_class

# Bổ sung thuộc tính tương thích ngược cho Replace (delete_count & consume_key)
if not hasattr(Replace, "delete_count"):
    Replace.delete_count = property(lambda self: self.delete_n)  # type: ignore
if not hasattr(Replace, "consume_key"):
    Replace.consume_key = property(lambda self: True)  # type: ignore
if not hasattr(Passthrough, "consume_key"):
    Passthrough.consume_key = property(lambda self: False)  # type: ignore


class FastTypeEngine:
    """Engine điều phối sự kiện phím tới Composer đăng ký qua Registry (N-04, FR-20)."""

    def __init__(self, pack: Optional[LanguagePack] = None) -> None:
        self.pack: Optional[LanguagePack] = None
        self.composer: Optional[Composer] = None
        self.set_pack(pack)

    def set_pack(self, pack: Optional[LanguagePack]) -> None:
        self.pack = pack
        if pack is None:
            self.composer = None
            return
        composer_name = getattr(pack, "composer", "mapping") or "mapping"
        composer_cls = get_composer_class(composer_name)
        self.composer = composer_cls(pack)

    def reset(self) -> None:
        if self.composer is not None:
            self.composer.reset()

    def backspace(self) -> Action:
        if self.composer is None:
            return Passthrough()
        return self.composer.backspace()

    def process_event(self, event: InputEvent) -> Action:
        if self.composer is None:
            return Passthrough()

        if isinstance(event, ResetEvent):
            self.composer.reset()
            return Passthrough()

        if isinstance(event, KeyEvent):
            if event.char == "\x08" or event.keyval == 65288:  # BackSpace
                return self.composer.backspace()
            return self.composer.feed(event)

        return Passthrough()