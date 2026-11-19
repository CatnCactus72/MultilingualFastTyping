# core/composers/base.py
from dataclasses import dataclass, field
from typing import List, Protocol, Union, runtime_checkable


@dataclass(frozen=True)
class KeyEvent:
    char: str
    keyval: int = 0
    is_upper: bool = False
    is_printable: bool = True


@dataclass(frozen=True)
class ResetEvent:
    reason: str = "unknown"


InputEvent = Union[KeyEvent, ResetEvent]


@dataclass(frozen=True)
class Passthrough:
    pass


@dataclass(frozen=True)
class Replace:
    delete_n: int
    text: str


@dataclass(frozen=True)
class Preedit:
    text: str
    cursor: int = 0


@dataclass(frozen=True)
class Candidates:
    items: List[str] = field(default_factory=list)


Action = Union[Passthrough, Replace, Preedit, Candidates]


@runtime_checkable
class Composer(Protocol):
    requires_preedit: bool

    def feed(self, ev: KeyEvent) -> Action:
        ...

    def backspace(self) -> Action:
        ...

    def reset(self) -> None:
        ...

    def render(self) -> str:
        ...

    def settings_schema(self) -> dict:
        ...

    def validate_pack(self, pack: dict) -> list:
        ...