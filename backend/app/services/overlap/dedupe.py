"""Shared substring-containment de-duplication.

Single home for the "drop an item whose text is a sub- or super-string of an
already-kept item" pattern, so detection and presentation layers do not each
re-implement it.
"""

from __future__ import annotations

from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def dedupe_by_containment(
    items: Iterable[T],
    *,
    key: Callable[[T], str],
    sort_key: Callable[[T], object],
    reverse: bool = True,
) -> list[T]:
    """Keep items whose key text is not contained in (or containing) a kept key.

    Items are processed in ``sort_key`` order (descending by default, so the
    strongest/longest item wins) and an item is dropped when its key string is a
    substring of, or a superstring of, an already-kept item's key. Items with an
    empty key are skipped.
    """
    ordered = sorted(items, key=sort_key, reverse=reverse)
    kept: list[T] = []
    for item in ordered:
        k = key(item)
        if not k:
            continue
        if any(k in key(existing) or key(existing) in k for existing in kept):
            continue
        kept.append(item)
    return kept
