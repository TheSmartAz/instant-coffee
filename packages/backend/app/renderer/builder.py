from __future__ import annotations

import asyncio
import json
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

    async def build_from_workspace_source(
        self,
        source_dir: Path,
        *,
        pages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Build from user/agent-authored React source files in the session workspace."""
        self._emit_start()
        try:
            result = await asyncio.to_thread(
                self._build_from_workspace_source_sync,
                Path(source_dir),
                pages or [],
            )
        except Exception as exc:
            self._emit_failed(exc)
            raise
        self._emit_done(result)
        return result

    def _build_from_workspace_source_sync(
        self,
        source_dir: Path,
        pages: list[dict[str, str]],
    ) -> dict[str, Any]:
        if not self.TEMPLATE_PATH.exists():
            raise BuildError("React SSG template not found", stage="template")
        if not source_dir.exists():
            raise BuildError("Workspace source directory not found", stage="workspace_source")

        self._reset_log()
        self._log(f"Build started (workspace source path): {source_dir}")
        self._check_cancelled("init")

        self._emit_progress("Copying template", 10)
        self._copy_template()

        self._emit_progress("Copying workspace source", 25)
        self._copy_workspace_source(source_dir)
        page_list = self._resolve_workspace_pages(pages)
        self._write_workspace_manifest(page_list)

        self._emit_progress("Installing dependencies", 45)
        install_cmd = ["npm", "ci"] if (self.work_dir / "package-lock.json").exists() else ["npm", "install"]
        self._run_command(install_cmd, stage="npm_install")

        self._emit_progress("Building project", 70)
        self._run_command(["npm", "run", "build"], stage="npm_build")

        build_dist = self.work_dir / "dist"
        if not build_dist.exists():
            raise BuildError("Build output not found", stage="npm_build")

        self._emit_progress("Publishing build artifacts", 85)
        self._publish_dist(build_dist)

        self._emit_progress("Applying mobile shell", 92)
        self._check_cancelled("mobile_shell")
        self._apply_mobile_shell()

        html_pages = sorted(
            str(path.relative_to(self.dist_dir))
            for path in self.dist_dir.rglob("*.html")
            if path.is_file()
        )
        self._emit_progress("Build complete", 100)

        return {
            **BuildResult(
                status="success",
                dist_path=str(self.dist_dir),
                pages=html_pages,
            ).__dict__,
            "source_mode": "workspace",
        }

    def _copy_template(self) -> None:
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        shutil.copytree(self.TEMPLATE_PATH, self.work_dir)

    def _copy_workspace_source(self, source_dir: Path) -> None:
        allowed_roots = {"src", "public"}
        allowed_root_files = {
            "index.html",
            "tailwind.config.js",
            "postcss.config.js",
            "vite.config.ts",
            "vite.config.js",
            "tsconfig.json",
        }
        for item in source_dir.iterdir():
            if item.name in allowed_roots and item.is_dir():
                target = self.work_dir / item.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target, ignore=self._workspace_ignore)
            elif item.name in allowed_root_files and item.is_file():
                shutil.copy2(item, self.work_dir / item.name)
        if not (self.work_dir / "src" / "App.tsx").exists():
            raise BuildError("Workspace source must include src/App.tsx", stage="workspace_source")

    @staticmethod
    def _workspace_ignore(_directory: str, names: list[str]) -> set[str]:
        ignored = {
            "node_modules",
            "dist",
            "build",
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".visual-check",
            "visual-check",
        }
        return {name for name in names if name in ignored or name.endswith((".db", ".sqlite"))}

    def _resolve_workspace_pages(self, pages: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized = [
            {
                "slug": str(page.get("slug") or "index"),
                "title": str(page.get("title") or page.get("slug") or "Index").replace("-", " ").title(),
            }
            for page in pages
            if isinstance(page, dict)
        ]
        if normalized:
            return normalized

        pages_dir = self.work_dir / "src" / "pages"
        if pages_dir.exists():
            discovered = []
            for path in sorted(pages_dir.glob("*.tsx")):
                if path.name.startswith("_"):
                    continue
                slug = path.stem
                discovered.append({"slug": slug, "title": slug.replace("-", " ").title()})
            if discovered:
                return discovered
        return [{"slug": "index", "title": "Index"}]

    def _write_workspace_manifest(self, pages: list[dict[str, str]]) -> None:
        data_dir = self.work_dir / "src" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = data_dir / "prerender-manifest.json"
        if manifest_path.exists():
            return
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
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _publish_dist(self, build_dist: Path) -> None:
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        shutil.move(str(build_dist), str(self.dist_dir))

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

    _APP_MODE_SCRIPT = (
        '<script id="ic-app-mode-runtime">'
        "(function(){"
        "var S='ic-app-mode',N='ic_nav',ST='ic_state',R='ic_ready',SI='ic_state_init',"
        "D='instant-coffee:update',MX=100,MR=200,AS={},EL=[],RL=[],AP=false;"
        "function ex(h){if(!h)return true;if(h[0]==='#')return true;if(h.indexOf('//')===0)return true;"
        "return /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(h)}"
        "function ns(h){if(!h)return null;if(ex(h))return null;var r=h.split('#')[0].split('?')[0];"
        "if(!r)return null;if(r.indexOf('./')===0)r=r.slice(2);if(r[0]==='/')r=r.slice(1);"
        "if(r==='index'||r==='index.html')return'index';if(r.indexOf('pages/')===0)r=r.slice(6);"
        "if(r.slice(-5)==='.html')r=r.slice(0,-5);if(!r||r.indexOf('/')!==-1)return null;return r}"
        "function gk(el){if(!el)return null;return el.getAttribute('data-ic-key')||el.name||el.id||null}"
        "function rv(el){if(!el)return undefined;var t=el.tagName;if(t==='INPUT'){var ty=el.type||'text';"
        "if(ty==='checkbox')return!!el.checked;if(ty==='radio')return el.checked?el.value:undefined;"
        "if(ty==='file')return undefined;return el.value}if(t==='SELECT'){if(el.multiple){var v=[];"
        "for(var i=0;i<el.options.length;i++)if(el.options[i].selected)v.push(el.options[i].value);"
        "return v}return el.value}if(t==='TEXTAREA')return el.value;return undefined}"
        "function wv(el,v){if(v===undefined||v===null)return;var t=el.tagName;if(t==='INPUT'){"
        "var ty=el.type||'text';if(ty==='checkbox'){el.checked=!!v;return}if(ty==='radio'){"
        "el.checked=String(v)===el.value;return}if(ty==='file')return;el.value=String(v);return}"
        "if(t==='SELECT'){if(el.multiple&&Array.isArray(v)){for(var i=0;i<el.options.length;i++)"
        "el.options[i].selected=v.indexOf(el.options[i].value)!==-1;return}el.value=String(v);return}"
        "if(t==='TEXTAREA')el.value=String(v)}"
        "function as(){AP=true;try{var fs=document.querySelectorAll('input,select,textarea');"
        "for(var i=0;i<fs.length;i++){var el=fs[i],k=gk(el);if(!k||!(k in AS))continue;wv(el,AS[k])}}"
        "finally{AP=false}}"
        "function eu(){if(!window.parent)return;window.parent.postMessage({type:D,state:AS,events:EL,"
        "records:RL,timestamp:Date.now()},'*')}"
        "function pe(n,d){if(!n)return;EL.unshift({name:String(n),data:d===undefined?null:d,"
        "timestamp:Date.now()});if(EL.length>MX)EL.length=MX;eu()}"
        "function pr(t,p){var rt=t==='order_submitted'||t==='booking_submitted'||t==='form_submission'?"
        "t:'form_submission';RL.unshift({type:rt,payload:p,created_at:new Date().toISOString()});"
        "if(RL.length>MR)RL.length=MR;eu()}"
        "function ts(v){if(!v)return v;if(typeof File!=='undefined'&&v instanceof File)"
        "return{name:v.name,size:v.size,type:v.type};return v}"
        "function cf(f){var d={};if(!f||typeof FormData==='undefined')return d;"
        "var fd=new FormData(f);fd.forEach(function(v,k){var c=ts(v);if(d[k]===undefined)d[k]=c;"
        "else if(Array.isArray(d[k]))d[k].push(c);else d[k]=[d[k],c]});return d}"
        "function ir(f){if(!f||!f.getAttribute)return'form_submission';"
        "var c=f.getAttribute('data-ic-record-type')||f.getAttribute('data-record-type')||"
        "f.getAttribute('data-record');if(c==='order_submitted'||c==='booking_submitted'||"
        "c==='form_submission')return c;return'form_submission'}"
        "function es(){if(!window.parent)return;window.parent.postMessage({source:S,type:ST,state:AS},'*')}"
        "function us(k,v){if(!k)return;AS[k]=v;es();pe('state_update',{key:k,value:v})}"
        "document.addEventListener('input',function(e){if(AP)return;var t=e.target,k=gk(t);"
        "if(!k)return;var v=rv(t);if(v===undefined)return;us(k,v)},true);"
        "document.addEventListener('change',function(e){if(AP)return;var t=e.target,k=gk(t);"
        "if(!k)return;var v=rv(t);if(v===undefined)return;us(k,v)},true);"
        "document.addEventListener('submit',function(e){var t=e.target;if(!t||t.tagName!=='FORM')return;"
        "var p=cf(t),rt=ir(t);pr(rt,p);pe('form_submit',{type:rt})},true);"
        "document.addEventListener('click',function(e){var t=e.target;if(!t||!t.closest)return;"
        "var a=t.closest('a');if(!a)return;var h=a.getAttribute('href'),s=ns(h);"
        "if(!s)return;e.preventDefault();pe('navigate',{slug:s,href:h});"
        "if(window.parent)window.parent.postMessage({source:S,type:N,slug:s},'*')},true);"
        "window.addEventListener('message',function(e){var d=e.data||{};if(!d||d.source!==S)return;"
        "if(d.type===SI){AS=d.state&&typeof d.state==='object'?d.state:{};as();eu()}});"
        "window.IC_APP={getState:function(){return AS},setState:function(k,v){"
        "if(typeof k==='string'){us(k,v);return}if(k&&typeof k==='object'){for(var key in k)"
        "if(Object.prototype.hasOwnProperty.call(k,key))AS[key]=k[key];es();"
        "pe('state_sync',{keys:Object.keys(k)})}},navigate:function(s){"
        "if(!s||!window.parent)return;window.parent.postMessage({source:S,type:N,slug:s},'*')}};"
        "if(window.parent){window.parent.postMessage({source:S,type:R},'*');eu()}"
        "})();"
        "</script>"
    )

    def _apply_mobile_shell(self) -> None:
        for path in self.dist_dir.rglob("*.html"):
            if not path.is_file():
                continue
            try:
                html = path.read_text(encoding="utf-8")
                patched = ensure_mobile_shell(html)
                # Inject app-mode runtime for iframe state sync / nav bridging
                if self._APP_MODE_SCRIPT not in patched:
                    if "</body>" in patched:
                        patched = patched.replace("</body>", f"{self._APP_MODE_SCRIPT}</body>")
                    elif "</head>" in patched:
                        patched = patched.replace("</head>", f"{self._APP_MODE_SCRIPT}</head>")
                    else:
                        patched = f"{patched}{self._APP_MODE_SCRIPT}"
                if patched != html:
                    path.write_text(patched, encoding="utf-8")
            except OSError:
                logger.warning("Failed to post-process %s", path)

    def _emit_start(self) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import build_start_event

            self.event_emitter.emit(build_start_event())
        except Exception:
            logger.debug("Failed to emit build start event")

    def _emit_progress(self, message: str, progress: int) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import build_progress_event

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
            from ..events.models import build_complete_event

            self.event_emitter.emit(build_complete_event(payload=result))
        except Exception:
            logger.debug("Failed to emit build done event")

    def _emit_failed(self, exc: Exception) -> None:
        if not self.event_emitter:
            return
        try:
            from ..events.models import build_failed_event

            self.event_emitter.emit(
                build_failed_event(
                    error=str(exc),
                    retry_count=0,
                )
            )
        except Exception:
            logger.debug("Failed to emit build failed event")


__all__ = ["BuildCancelled", "BuildError", "BuildResult", "ReactSSGBuilder"]
