import asyncio
from pathlib import Path

from app.renderer.builder import ReactSSGBuilder
from app.renderer.file_generator import SchemaFileGenerator


def test_schema_file_generator_writes_json_and_pages(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "src" / "pages").mkdir(parents=True)
    (project_root / "src" / "pages" / "_template.tsx").write_text(
        "export const template = true\n",
        encoding="utf-8",
    )
    (project_root / "public" / "assets").mkdir(parents=True)

    asset_path = tmp_path / "logo.png"
    asset_path.write_bytes(b"fake")

    generator = SchemaFileGenerator(project_root)
    generator.generate(
        page_schemas=[
            {"slug": "index", "title": "Home", "layout": "default", "components": []},
            {"slug": "about", "title": "About", "layout": "default", "components": []},
        ],
        component_registry={"components": []},
        style_tokens={"colors": {"primary": "#000"}},
        assets={"files": [{"path": str(asset_path), "filename": "logo.png"}]},
    )

    data_dir = project_root / "src" / "data"
    assert (data_dir / "schemas.json").exists()
    assert (data_dir / "tokens.json").exists()
    assert (data_dir / "registry.json").exists()
    assert (data_dir / "assets.json").exists()

    pages_dir = project_root / "src" / "pages"
    assert (pages_dir / "index.tsx").exists()
    assert (pages_dir / "about.tsx").exists()

    copied_asset = project_root / "public" / "assets" / "logo.png"
    assert copied_asset.exists()


def test_react_ssg_builder_builds_with_mocked_npm(tmp_path: Path, monkeypatch) -> None:
    session_id = "session-test"
    base_dir = tmp_path / "sessions"

    def fake_run_command(self, command, stage):
        if stage == "npm_build":
            dist_dir = self.work_dir / "dist"
            (dist_dir / "pages" / "about").mkdir(parents=True, exist_ok=True)
            (dist_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
            (dist_dir / "pages" / "about" / "index.html").write_text(
                "<html>about</html>",
                encoding="utf-8",
            )
        return None

    monkeypatch.setattr(ReactSSGBuilder, "_run_command", fake_run_command)

    builder = ReactSSGBuilder(session_id, base_dir=base_dir)
    result = asyncio.run(
        builder.build(
            page_schemas=[{"slug": "index", "title": "Home", "layout": "default", "components": []}],
            component_registry={},
            style_tokens={},
            assets=None,
        )
    )

    assert result["status"] == "success"
    assert builder.dist_dir.exists()
    assert (builder.dist_dir / "index.html").exists()
    assert "index.html" in result["pages"]
