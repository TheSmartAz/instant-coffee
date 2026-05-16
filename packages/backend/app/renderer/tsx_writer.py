"""Write AI-generated TSX files into a React SSG template workspace."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConvertedFile:
    path: str
    content: str


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
            import_path = self._resolve_page_import_path(slug)
            imports.append(
                f"import {component_name} from './pages/{import_path}'"
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

    def _resolve_page_import_path(self, slug: str) -> str:
        """Resolve the actual page module for a slug.

        The React SSG template includes placeholder pages that call back into
        App via createPage(). Importing those placeholders directly causes
        App -> Page -> App recursion during prerender.
        """
        pages_dir = self.root / "src" / "pages"
        slug_path = pages_dir / f"{slug}.tsx"
        if slug_path.exists() and not self._is_template_page(slug_path):
            return slug

        candidates = [
            path
            for path in sorted(pages_dir.glob("*.tsx"))
            if path.stem != "_template" and not self._is_template_page(path)
        ]
        preferred = next((path for path in candidates if path.stem == slug), None)
        if preferred is None and slug == "index" and len(candidates) == 1:
            preferred = candidates[0]

        if preferred is not None:
            self._write_slug_wrapper(slug_path, preferred)
        return slug

    @staticmethod
    def _is_template_page(path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return False
        return "createPage(" in content and "from './_template'" in content

    @staticmethod
    def _relative_import(from_path: Path, to_path: Path) -> str:
        relative = to_path.with_suffix("").relative_to(from_path.parent)
        value = relative.as_posix()
        return value if value.startswith(".") else f"./{value}"

    def _write_slug_wrapper(self, slug_path: Path, target_path: Path) -> None:
        import_path = self._relative_import(slug_path, target_path)
        slug_path.parent.mkdir(parents=True, exist_ok=True)
        slug_path.write_text(
            f"export {{ default }} from '{import_path}'\n",
            encoding="utf-8",
        )


__all__ = ["ConvertedFile", "TsxFileWriter"]
