from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from ...db.models import Page

_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_-]+)")


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


class PageTargetResolver:
    def parse(self, message: str, pages: Sequence[Page] | Iterable[str]) -> List[str]:
        if not message:
            return []

        page_items = list(pages or [])
        if not page_items:
            return []

        slugs: List[str] = []
        titles: List[str] = []
        title_to_slug: dict[str, str] = {}
        for page in page_items:
            if isinstance(page, Page):
                if page.slug:
                    slugs.append(page.slug)
                if page.title:
                    titles.append(page.title)
                    if page.slug:
                        title_to_slug[_normalize(page.title)] = page.slug
            else:
                slug = str(page or "").strip()
                if slug:
                    slugs.append(slug)

        slug_lookup = {slug.lower(): slug for slug in slugs if slug}
        title_lookup = {_normalize(title): title for title in titles if title}

        mentions = _MENTION_PATTERN.findall(message)
        if not mentions:
            return []

        resolved: List[str] = []
        seen = set()

        for mention in mentions:
            key = mention.lower()
            if key in slug_lookup:
                slug = slug_lookup[key]
                if slug not in seen:
                    resolved.append(slug)
                    seen.add(slug)
                continue

            title_key = _normalize(mention)
            if title_key in title_lookup:
                slug = title_to_slug.get(title_key)
                if slug and slug not in seen:
                    resolved.append(slug)
                    seen.add(slug)
                    continue
                title = title_lookup[title_key]
                slug = slug_lookup.get(title.lower())
                if slug and slug not in seen:
                    resolved.append(slug)
                    seen.add(slug)
                    continue

            partial_slug = self._match_partial(key, slug_lookup)
            if partial_slug and partial_slug not in seen:
                resolved.append(partial_slug)
                seen.add(partial_slug)

        return resolved

    def _match_partial(self, mention: str, slug_lookup: dict[str, str]) -> str | None:
        if not mention:
            return None
        candidates = []
        for slug_lower, slug in slug_lookup.items():
            if mention == slug_lower:
                return slug
            if mention in slug_lower or slug_lower in mention:
                candidates.append(slug)
        if len(candidates) == 1:
            return candidates[0]
        return None


__all__ = ["PageTargetResolver"]
