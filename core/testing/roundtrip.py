# core/testing/roundtrip.py
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence
from core.composers.base import Composer, KeyEvent, Passthrough, Replace


@dataclass(frozen=True)
class RoundtripFailure:
    expected: str
    actual: str
    keystrokes: str
    style: str


def simulate_sequence(composer: Composer, keystrokes: str) -> str:
    """Mô phỏng chuỗi phím gõ qua composer và trả về văn bản hiển thị cuối cùng."""
    composer.reset()
    screen: List[str] = []

    for ch in keystrokes:
        if ch == "\b":
            act = composer.backspace()
            if isinstance(act, Passthrough):
                if screen:
                    screen.pop()
            elif isinstance(act, Replace):
                if act.delete_n > 0:
                    del screen[-act.delete_n:]
                screen.extend(list(act.text))
            continue

        ev = KeyEvent(
            char=ch,
            is_upper=ch.isupper(),
            is_printable=True,
        )
        act = composer.feed(ev)
        if isinstance(act, Passthrough):
            screen.append(ch)
        elif isinstance(act, Replace):
            if act.delete_n > 0:
                del screen[-act.delete_n:]
            screen.extend(list(act.text))

    return "".join(screen)


def run_roundtrip_harness(
    composer_factory: Callable[[], Composer],
    valid_items: Iterable[str],
    encoder: Callable[[str, str], str],
    styles: Sequence[str] = ("tone_end", "immediate", "tone_before_coda"),
    max_failures: int = 20,
) -> List[RoundtripFailure]:
    """Chạy kiểm thử vòng trên mọi mục hợp lệ nhân với các thứ tự gõ (FR-24)."""
    failures: List[RoundtripFailure] = []
    composer = composer_factory()

    for item in valid_items:
        for style in styles:
            keys = encoder(item, style)
            actual = simulate_sequence(composer, keys)
            if actual != item:
                failures.append(
                    RoundtripFailure(
                        expected=item,
                        actual=actual,
                        keystrokes=keys,
                        style=style,
                    )
                )
                if len(failures) >= max_failures:
                    return failures
    return failures