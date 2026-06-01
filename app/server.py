#!/usr/bin/env python3
"""Sticker Removal GUI — FastAPI backend."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# ── Paths ────────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent
ROOT_DIR = APP_DIR.parent
CONFIG_FILE = ROOT_DIR / ".env"
SCRIPTS_DIR = Path("/Users/anthony/Documents/Playground/sticker_removal_batch")

_CODEX_PY = Path(
    "/Users/anthony/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/bin/python3"
)
PYTHON = str(_CODEX_PY) if _CODEX_PY.exists() else "/opt/homebrew/bin/python3"

ALLOWED_ROOTS = [
    Path("/Users/anthony"),
]

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    cfg: dict[str, str] = {}
    for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def save_config(updates: dict[str, str]) -> None:
    cfg = load_config()
    cfg.update({k: v for k, v in updates.items() if v != ""})
    lines = [f'{k}="{v}"' for k, v in cfg.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Sticker Removal GUI")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/img", response_model=None)
async def serve_image(path: str) -> FileResponse | JSONResponse:
    p = Path(path).expanduser().resolve()
    if not any(str(p).startswith(str(r)) for r in ALLOWED_ROOTS):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p)


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_proc(
    cmd: list[str],
    env: dict[str, str] | None = None,
) -> AsyncGenerator[str, None]:
    merged_env = {**os.environ, **(env or {}), "PYTHONUNBUFFERED": "1"}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=merged_env,
    )
    assert proc.stdout
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        yield _sse({"log": line})
    await proc.wait()
    yield _sse({"done": True, "code": proc.returncode})


# ── Prepare endpoint ──────────────────────────────────────────────────────────

@app.post("/api/prepare")
async def prepare(req: Request) -> StreamingResponse:
    body = await req.json()
    input_dir = body.get("input_dir", str(Path.home() / "smallOne"))
    job_dir = body.get("job_dir") or str(Path(input_dir) / "_sticker_jobs")

    cmd = [
        PYTHON,
        str(SCRIPTS_DIR / "remove_sticker_prepare_price_tag.py"),
        "--input-dir", input_dir,
        "--out-dir", job_dir,
    ]

    return StreamingResponse(
        _stream_proc(cmd),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Repair endpoint ───────────────────────────────────────────────────────────

@app.post("/api/repair")
async def repair(req: Request) -> StreamingResponse:
    body = await req.json()
    engine: str = body.get("engine", "openai2")
    job_dir: str = body.get("job_dir", str(Path.home() / "smallOne/_sticker_jobs"))
    work_order = str(Path(job_dir) / "work_order.jsonl")
    cfg = load_config()

    if engine == "openai2":
        env = {"OPENAI_API_KEY": cfg.get("OPENAI_API_KEY", "")}
        cmd = [
            PYTHON,
            str(SCRIPTS_DIR / "repair_with_openai.py"),
            "--work-order", work_order,
            "--api-url", cfg.get("OPENAI_API_URL", "https://www.packyapi.com/v1/images/edits"),
            "--model", "gpt-image-2",
            "--size", "auto",
            "--quality", "medium",
            "--input-fidelity", "medium",
            "--concurrency", "8",
        ]
    else:  # tencent
        env = {
            "TENCENTCLOUD_SECRET_ID": cfg.get("TENCENTCLOUD_SECRET_ID", ""),
            "TENCENTCLOUD_SECRET_KEY": cfg.get("TENCENTCLOUD_SECRET_KEY", ""),
        }
        cmd = [
            PYTHON,
            str(SCRIPTS_DIR / "repair_with_tencent.py"),
            "--work-order", work_order,
            "--region", cfg.get("TENCENTCLOUD_REGION", "ap-guangzhou"),
            "--concurrency", "8",
        ]

    return StreamingResponse(
        _stream_proc(cmd, env),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Config endpoints ──────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config() -> dict:
    cfg = load_config()
    masked: dict[str, Any] = {}
    for k, v in cfg.items():
        masked[k] = ("●" * 8) if any(s in k for s in ("KEY", "SECRET")) and v else v
    masked["_has_openai"] = bool(cfg.get("OPENAI_API_KEY"))
    masked["_has_tencent"] = bool(
        cfg.get("TENCENTCLOUD_SECRET_ID") and cfg.get("TENCENTCLOUD_SECRET_KEY")
    )
    return masked


@app.post("/api/config")
async def set_config(req: Request) -> dict:
    data = await req.json()
    to_save = {k: v for k, v in data.items() if not k.startswith("_") and "●" not in str(v)}
    save_config(to_save)
    return {"ok": True}


# ── Jobs status ───────────────────────────────────────────────────────────────

@app.get("/api/jobs")
async def get_jobs(job_dir: str = "") -> dict:
    if not job_dir:
        return {"total": 0, "completed": 0, "jobs": []}
    jd = Path(job_dir).expanduser().resolve()
    wo = jd / "work_order.jsonl"
    if not wo.exists():
        return {"total": 0, "completed": 0, "jobs": []}

    jobs: list[dict] = []
    for line in wo.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                jobs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    result = []
    for j in jobs:
        out = Path(j.get("target_output", ""))
        result.append({"source": j["source"], "done": out.exists()})

    completed = sum(1 for r in result if r["done"])
    return {"total": len(result), "completed": completed, "jobs": result}


# ── Previews ──────────────────────────────────────────────────────────────────

@app.get("/api/previews")
async def get_previews(job_dir: str = "") -> dict:
    if not job_dir:
        return {"images": []}
    jd = Path(job_dir).expanduser().resolve()
    previews_dir = jd / "previews"
    if not previews_dir.exists():
        return {"images": []}
    images = sorted(
        p for p in previews_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    return {"images": [str(p) for p in images]}


# ── Results ───────────────────────────────────────────────────────────────────

@app.get("/api/results")
async def get_results(job_dir: str = "", engine: str = "openai2") -> dict:
    if not job_dir:
        return {"pairs": []}
    jd = Path(job_dir).expanduser().resolve()

    comp_dir = jd / ("comparisons_openai" if engine == "openai2" else "comparisons_tencent")

    wo = jd / "work_order.jsonl"
    if not wo.exists():
        return {"pairs": []}

    pairs = []
    for line in wo.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            continue

        source = Path(job["source"])
        stem = source.stem

        if engine == "openai2":
            # OpenAI writes to target_output from work_order (= job_dir/output/stem.clean.png)
            output = Path(job.get("target_output", ""))
        else:
            output = jd / "output_tencent" / f"{stem}.clean.png"

        comparison = comp_dir / f"{stem}.before-after.jpg"

        if output.exists():
            pairs.append({
                "source": str(source),
                "output": str(output),
                "comparison": str(comparison) if comparison.exists() else None,
                "name": source.name,
            })

    return {"pairs": pairs}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser
    import uvicorn

    webbrowser.open("http://localhost:7788")
    uvicorn.run(app, host="127.0.0.1", port=7788, log_level="warning")
