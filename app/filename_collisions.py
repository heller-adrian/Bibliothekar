from __future__ import annotations

"""Conservative recognition of filesystem-generated duplicate-name suffixes.

These helpers never identify content on their own. They only normalize common
names that Finder/Windows/SMB create when two files with the same name are kept.
Callers that change canonical state must still verify identity by SHA-256/size.
"""

import re


_COPY_WORD_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)(?:\\s*-\\s*|\\s+|_)(?:copy|kopie)(?:[\\s_-]*\\d+)?$",
    re.IGNORECASE,
)
_COPY_PAREN_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)\\s*\\((?:copy\\s*|kopie\\s*)?\\d+\\)$",
    re.IGNORECASE,
)
_PLAIN_NUMBER_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)(?:\\s+|_)(?P<number>\\d+)$"
)
_EXPORT_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)_Export(?:_\\d{3})?$",
    re.IGNORECASE,
)


def copy_collision_base_stem(
    stem: str,
    *,
    allow_plain_number: bool = False,
) -> str | None:
    """Return the pre-collision stem for common OS duplicate suffixes.

    Examples include Bild Kopie, Bild copy 2 and Bild (1). A bare numeric
    suffix is only accepted when the caller explicitly enables it; that mode is
    intended for SHA-verified archive reconciliation, not heuristic family
    inference.
    """
    value = str(stem or "").strip()
    if not value:
        return None
    for pattern in (_COPY_WORD_SUFFIX_RE, _COPY_PAREN_SUFFIX_RE):
        match = pattern.match(value)
        if match is not None:
            base = str(match.group("base") or "").strip()
            return base or None
    if allow_plain_number:
        match = _PLAIN_NUMBER_SUFFIX_RE.match(value)
        if match is not None:
            base = str(match.group("base") or "").strip()
            return base or None
    return None


def export_collision_base_stem(stem: str) -> str | None:
    """Return the base of Bibliothekars _Export collision suffix."""
    match = _EXPORT_SUFFIX_RE.match(str(stem or "").strip())
    if match is None:
        return None
    base = str(match.group("base") or "").strip()
    return base or None


def collision_alias_stems(
    stem: str,
    *,
    allow_plain_number: bool = False,
    include_export_base: bool = False,
) -> set[str]:
    """Return conservative case-folded aliases for one observed/expected stem."""
    pending = [str(stem or "").strip()]
    result: set[str] = set()
    while pending:
        value = pending.pop()
        key = value.casefold()
        if not value or key in result:
            continue
        result.add(key)

        copy_base = copy_collision_base_stem(
            value,
            allow_plain_number=allow_plain_number,
        )
        if copy_base and copy_base.casefold() not in result:
            pending.append(copy_base)

        if include_export_base:
            export_base = export_collision_base_stem(value)
            if export_base and export_base.casefold() not in result:
                pending.append(export_base)
    return result
