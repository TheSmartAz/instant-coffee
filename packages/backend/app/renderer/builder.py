from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any

from ..services.mobile_shell import ensure_mobile_shell
from .file_generator import SchemaFileGenerator

logger = logging.getLogger(__name__)


class BuildError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.stdout = stdout
        self.stderr = stderr

    def summary(self) -> str:
        parts = [str(self)]
        if self.stderr:
            parts.append(self._truncate(self.stderr))
        elif self.stdout:
            parts.append(self._truncate(self.stdout))
        return "\n".join(parts)

    @staticmethod
    def _truncate(value: str, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."


class BuildCancelled(BuildError):
    pass


@dataclass(frozen=True)
class BuildResult:
    status: str
    dist_path: str
    pages: list[str]


class ReactSSGBuilder:
    TEMPLATE_PATH = Path(__file__).parent / "templates" / "react-ssg"

    def __init__(
        self,
        session_id: str,
        *,
        base_dir: Path | None = None,
        event_emitter: Any | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.event_emitter = event_emitter
        self._cancel_event = cancel_event
        base = Path(base_dir) if base_dir is not None else Path("~/.instant-coffee/sessions").expanduser()
        self.base_dir = base
        self.session_dir = (base / session_id).resolve()
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir = (self.session_dir / "build").resolve()
        self.dist_dir = (self.session_dir / "dist").resolve()
        self.log_path = self.session_dir / "build.log"
        self._task_id = f"build:{session_id}"

    async def build(
        self,
        page_schemas: list[dict[str, Any]],
        component_registry: dict[str, Any],
        style_tokens: dict[str, Any],
        assets: Any,
    ) -> dict[str, Any]:
        self._emit_start()
        try:
            result = await asyncio.to_thread(
                self._build_sync,
                page_schemas,
                component_registry,
                style_tokens,
                assets,
            )
        except Exception as exc:
            self._emit_failed(exc)
            raise
        self._emit_done(result)
        return result

    def _build_sync(
        self,
        page_schemas: list[dict[str, Any]],
        component_registry: dict[str, Any],
        style_tokens: dict[str, Any],
        assets: Any,
    ) -> dict[str, Any]:
        if not self.TEMPLATE_PATH.exists():
            raise BuildError("React SSG template not found", stage="template")

        self._reset_log()
        self._log("Build started")
        self._check_cancelled("init")

        self._emit_progress("Copying template", 10)
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        shutil.copytree(self.TEMPLATE_PATH, self.work_dir)

        self._emit_progress("Writing schema files", 25)
        self._check_cancelled("schema")
        generator = SchemaFileGenerator(
            self.work_dir,
            session_id=self.session_id,
            assets_base_dir=self.base_dir,
        )
        generator.generate(page_schemas, component_registry, style_tokens, assets)

        self._emit_progress("Installing dependencies", 45)
        install_cmd = ["npm", "ci"] if (self.work_dir / "package-lock.json").exists() else ["npm", "install"]
        self._run_command(install_cmd, stage="npm_install")

        self._emit_progress("Building project", 70)
        self._run_command(["npm", "run", "build"], stage="npm_build")

        build_dist = self.work_dir / "dist"
        if not build_dist.exists():
            raise BuildError("Build output not found", stage="npm_build")

        self._emit_progress("Publishing build artifacts", 85)
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        shutil.move(str(build_dist), str(self.dist_dir))

        self._emit_progress("Applying mobile shell", 92)
        self._check_cancelled("mobile_shell")
        self._apply_mobile_shell()

        pages = sorted(
            str(path.relative_to(self.dist_dir))
            for path in self.dist_dir.rglob("*.html")
            if path.is_file()
        )
        self._emit_progress("Build complete", 100)

        return BuildResult(
            status="success",
            dist_path=str(self.dist_dir),
            pages=pages,
        ).__dict__

    def _run_command(self, command: list[str], *, stage: str) -> None:
        self._check_cancelled(stage)
        self._log(f"$ {' '.join(command)}")
        process = subprocess.Popen(
            command,
            cwd=self.work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        while True:
            if self._cancel_event and self._cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                self._log("Build cancelled")
                raise BuildCancelled("Build cancelled", stage=stage)
            return_code = process.poll()
            if return_code is not None:
                break
            time.sleep(0.1)
        stdout, stderr = process.communicate()
        if stdout:
            self._log(stdout)
        if stderr:
            self._log(stderr)
        if return_code != 0:
            message = f"{' '.join(command)} failed"
            raise BuildError(
                message,
                stage=stage,
                stdout=stdout,
                stderr=stderr,
            )

    def _reset_log(self) -> None:
        try:
            self.log_path.write_text("", encoding="utf-8")
        except OSError:
            logger.debug("Failed to reset build log")

    def _log(self, message: str) -> None:
        if message is None:
            return
        try:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            entry = f"[{timestamp}] {message.rstrip()}\n"
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(entry)
        except OSError:
            logger.debug("Failed to append build log")

    def _check_cancelled(self, stage: str | None = None) -> None:
        if self._cancel_event and self._cancel_event.is_set():
            raise BuildCancelled("Build cancelled", stage=stage)

    def _apply_mobile_shell(self) -> None:
        for path in self.dist_dir.rglob("*.html"):
            if not path.is_file():
                continue
            try:
                html = path.read_text(encoding="utf-8")
                patched = ensure_mobile_shell(html)
                if patched != html:
                    path.write_text(patched, encoding="utf-8")
            except OSError:
                logger.warning("Failed to post-process %s", path)

    def _emit_start(self) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import TaskStartedEvent, build_start_event

            self.event_emitter.emit(
                TaskStartedEvent(task_id=self._task_id, task_title="React SSG Build")
            )
            self.event_emitter.emit(build_start_event())
        except Exception:
            logger.debug("Failed to emit build start event")

    def _emit_progress(self, message: str, progress: int) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import TaskProgressEvent, build_progress_event

            self.event_emitter.emit(
                TaskProgressEvent(task_id=self._task_id, progress=progress, message=message)
            )
            self.event_emitter.emit(
                build_progress_event(
                    step=message,
                    percent=progress,
                    message=message,
                )
            )
        except Exception:
            logger.debug("Failed to emit build progress event")

    def _emit_done(self, result: dict[str, Any]) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import TaskDoneEvent, build_complete_event

            self.event_emitter.emit(TaskDoneEvent(task_id=self._task_id, result=result))
            self.event_emitter.emit(build_complete_event(payload=result))
        except Exception:
            logger.debug("Failed to emit build done event")

    def _emit_failed(self, exc: Exception) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import TaskFailedEvent, build_failed_event

            error_type = "dependency" if isinstance(exc, BuildError) and exc.stage in {
                "npm_install",
                "npm_build",
            } else "logic"
            self.event_emitter.emit(
                TaskFailedEvent(
                    task_id=self._task_id,
                    error_type=error_type,
                    error_message=str(exc),
                    retry_count=0,
                    max_retries=0,
                    available_actions=["retry"],
                    blocked_tasks=[],
                )
            )
            self.event_emitter.emit(
                build_failed_event(
                    error=str(exc),
                    retry_count=0,
                )
            )
        except Exception:
            logger.debug("Failed to emit build failed event")


__all__ = ["BuildCancelled", "BuildError", "BuildResult", "ReactSSGBuilder"]
