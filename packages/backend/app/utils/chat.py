from __future__ import annotations

import re
from typing import Iterable, List

_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_-]+)")


def parse_page_mentions(message: str, existing_pages: Iterable[str]) -> List[str]:
    if not message:
        return []
    resolved_pages = list(existing_pages or [])
    if not resolved_pages:
        return []
    mentions = _MENTION_PATTERN.findall(message)
    if not mentions:
        return []
    page_lookup = {slug.lower(): slug for slug in resolved_pages if slug}
    results: List[str] = []
    seen = set()
    for mention in mentions:
        key = mention.lower()
        slug = page_lookup.get(key)
        if not slug or slug in seen:
            continue
        results.append(slug)
        seen.add(slug)
    return results


__all__ = ["parse_page_mentions"]
