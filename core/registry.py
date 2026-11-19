# core/registry.py
from typing import Dict, Type
from core.composers.base import Composer

_COMPOSER_REGISTRY: Dict[str, Type[Composer]] = {}


def register_composer(name: str, cls: Type[Composer]) -> None:
    _COMPOSER_REGISTRY[name] = cls


def get_composer_class(name: str) -> Type[Composer]:
    if name not in _COMPOSER_REGISTRY:
        raise KeyError(f"Composer chưa được đăng ký: '{name}'")
    return _COMPOSER_REGISTRY[name]


def list_composers() -> list[str]:
    return list(_COMPOSER_REGISTRY.keys())