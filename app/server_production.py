#!/usr/bin/env python3
"""Sticker Removal GUI — FastAPI backend (Production version)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# ── Paths ────────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent
ROOT_DIR = APP_DIR.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"

# 确保目录存在
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Python 解释器
PYTHON = os.getenv("PYTHON_BIN", "python3")

# 允许的根目录（生产环境只允许访问 data 目录）
ALLOWED_ROOTS = [DATA_DIR]

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict[str, str]:
    """从环境变量加载配置"""
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OPENAI_API_URL": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/images/edits"),
        "TENCENTCLOUD_SECRET_ID": os.getenv("TENCENTCLOUD_SECRET_ID", ""),
        "TENCENTCLOUD_SECRET_KEY": os.getenv("TENCENTCLOUD_SECRET_KEY", ""),
        "TENCENTCLOUD_REGION": os.getenv("TENCENTCLOUD_REGION", "ap-guangzhou"),
    }


def save_config(updates: dict[str, str]) -> None:
    """在生产环境中，配置通过环境变量管理，不支持运行时修改"""
    pass


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Sticker Removal GUI")

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/img", response_model=None)
async def serve_image(path: str) -> FileResponse | JSONResponse:
    p = Path(path).expanduser().resolve()
    if not any(str(p).startswith(str(r.resolve())) for r in ALLOWED_ROOTS):
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


# ── Upload endpoint ───────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)) -> JSONResponse:
    """上传图片文件"""
    uploaded = []
    for file in files:
        if not file.filename:
            continue

        file_path = UPLOADS_DIR / file.filename
        content = await file.read()
        file_path.write_bytes(content)
        uploaded.append(str(file_path))

    return JSONResponse({"uploaded": uploaded, "count": len(uploaded)})


# ── Prepare endpoint ──────────────────────────────────────────────────────────

@app.post("/api/prepare")
async def prepare(req: Request) -> StreamingResponse:
    body = await req.json()
    input_dir = body.get("input_dir", str(UPLOADS_DIR))
    job_dir = body.get("job_dir") or str(OUTPUTS_DIR / "_sticker_jobs")

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
    job_dir: str = body.get("job_dir", str(OUTPUTS_DIR / "_sticker_jobs"))
    work_order = str(Path(job_dir) / "work_order.jsonl")
    cfg = load_config()

    if engine == "openai2":
        env = {"OPENAI_API_KEY": cfg.get("OPENAI_API_KEY", "")}
        cmd = [
            PYTHON,
            str(SCRIPTS_DIR / "repair_with_openai.py"),
            "--work-order", work_order,
            "--api-url", cfg.get("OPENAI_API_URL", "https://api.openai.com/v1/images/edits"),
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
    # 生产环境不允许通过 API 修改配置
    return {"ok": False, "error": "Configuration is managed via environment variables"}


# ── Jobs status ───────────────────────────────────────────────────────────────

@app.get("/api/jobs")
async def get_jobs(job_dir: str = "") -> dict:
    if not job_dir:
        job_dir = str(OUTPUTS_DIR / "_sticker_jobs")

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
        job_dir = str(OUTPUTS_DIR / "_sticker_jobs")

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
        job_dir = str(OUTPUTS_DIR / "_sticker_jobs")

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


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "unsticker"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(app, host=host, port=port, log_level="info")
