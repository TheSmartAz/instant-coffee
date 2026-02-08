"""Project management - each project = conversation + workspace."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Project:
    id: str
    title: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProjectStore:
    """Manages project directories.

    Each project lives at:
        {base_dir}/projects/{project_id}/
        ├── meta.json        # project metadata
        ├── context.jsonl    # conversation history
        └── workspace/       # generated code
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "projects"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, title: str = "") -> Project:
        now = datetime.now().isoformat()
        project = Project(
            id=uuid.uuid4().hex[:12],
            title=title or f"Project {now[:10]}",
            created_at=now,
            updated_at=now,
        )
        project_dir = self.base_dir / project.id
        project_dir.mkdir(exist_ok=True)
        (project_dir / "workspace").mkdir(exist_ok=True)
        self._save_meta(project)
        return project

    def list_projects(self, limit: int = 20) -> list[Project]:
        projects = []
        for d in sorted(self.base_dir.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            meta_path = d / "meta.json"
            if meta_path.exists():
                data = json.loads(meta_path.read_text())
                projects.append(Project(**data))
            if len(projects) >= limit:
                break
        return projects

    def get(self, project_id: str) -> Project | None:
        meta_path = self.base_dir / project_id / "meta.json"
        if not meta_path.exists():
            return None
        return Project(**json.loads(meta_path.read_text()))

    def project_dir(self, project_id: str) -> Path:
        return self.base_dir / project_id

    def workspace_dir(self, project_id: str) -> Path:
        return self.base_dir / project_id / "workspace"

    def context_path(self, project_id: str) -> Path:
        return self.base_dir / project_id / "context.jsonl"

    def update_timestamp(self, project: Project):
        project.updated_at = datetime.now().isoformat()
        self._save_meta(project)

    def _save_meta(self, project: Project):
        meta_path = self.base_dir / project.id / "meta.json"
        meta_path.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2))
