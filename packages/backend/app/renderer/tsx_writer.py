"""Write AI-generated TSX files into a React SSG template workspace."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .html_to_react import ConvertedFile

logger = logging.getLogger(__name__)


class TsxFileWriter:
    """Writes converted React files into the build workspace."""

    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root)

    def write_files(self, files: list[ConvertedFile]) -> None:
        """Write all converted files into the workspace."""
        for f in files:
            target = self.root / f.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.content, encoding="utf-8")
            logger.debug("Wrote %s", target)

    def write_entry_points(self, pages: list[dict]) -> None:
        """Generate App.tsx routing and prerender manifest.

        Args:
            pages: list of dicts with keys: slug, title
        """
        self._write_app_tsx(pages)
        self._write_prerender_manifest(pages)

    def _write_app_tsx(self, pages: list[dict]) -> None:
        """Generate src/App.tsx with page routing."""
        imports: list[str] = []
        routes: list[str] = []

        for page in pages:
            slug = page["slug"]
            component_name = self._slug_to_component(slug)
            imports.append(
                f"import {component_name} from './pages/{slug}'"
            )
            if slug == "index":
                routes.append(
                    f'    {{ path: "/", element: <{component_name} /> }}'
                )
            else:
                routes.append(
                    f'    {{ path: "/{slug}", element: <{component_name} /> }}'
                )

        imports_str = "\n".join(imports)
        routes_str = ",\n".join(routes)

        app_tsx = f"""\
import React from 'react'
{imports_str}

export interface AppProps {{
  pageSlug?: string
  schemas?: any[]
  tokens?: Record<string, any>
  assets?: Record<string, any>
}}

const routes = [
{routes_str}
]

export default function App({{ pageSlug = 'index' }}: AppProps) {{
  const route = routes.find(
    r => r.path === '/' + pageSlug || (pageSlug === 'index' && r.path === '/')
  )
  if (!route) return <div>Page not found</div>
  return route.element
}}
"""
        target = self.root / "src" / "App.tsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(app_tsx, encoding="utf-8")
        logger.debug("Wrote App.tsx with %d routes", len(routes))

    def _write_prerender_manifest(self, pages: list[dict]) -> None:
        """Generate prerender-manifest.json for the prerender script."""
        manifest = {
            "pages": [
                {
                    "slug": page["slug"],
                    "title": page["title"],
                    "entry": f"src/pages/{page['slug']}.tsx",
                }
                for page in pages
            ]
        }
        data_dir = self.root / "src" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "prerender-manifest.json"
        target.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Wrote prerender-manifest.json with %d pages", len(pages))

    @staticmethod
    def _slug_to_component(slug: str) -> str:
        """Convert a slug like 'about-us' to 'AboutUsPage'."""
        parts = slug.replace("-", " ").replace("_", " ").split()
        name = "".join(word.capitalize() for word in parts) if parts else "Index"
        return f"{name}Page"


__all__ = ["TsxFileWriter"]
