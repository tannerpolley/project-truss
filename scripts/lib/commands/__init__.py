"""Focused command ownership maps loaded by the public dispatcher."""
from __future__ import annotations

from collections.abc import Callable

from . import distribution, project


def load_handlers() -> dict[str, Callable]:
    handlers: dict[str, Callable] = {}
    for module in (project, distribution):
        overlap = set(handlers) & set(module.HANDLERS)
        if overlap:
            raise ValueError("duplicate focused command handlers: " + ", ".join(sorted(overlap)))
        handlers.update(module.HANDLERS)
    return handlers
