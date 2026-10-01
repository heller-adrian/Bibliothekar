from __future__ import annotations

from contextvars import ContextVar, Token

from app.library_context import LibraryContext


_CURRENT_LIBRARY: ContextVar[LibraryContext | None] = ContextVar(
    "bibliothekar_current_library",
    default=None,
)


def set_current_library(context: LibraryContext) -> Token:
    return _CURRENT_LIBRARY.set(context)


def reset_current_library(token: Token) -> None:
    _CURRENT_LIBRARY.reset(token)


def get_current_library() -> LibraryContext | None:
    return _CURRENT_LIBRARY.get()
