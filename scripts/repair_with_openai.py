#!/usr/bin/env python3
"""
Run AI inpainting jobs from work_order.jsonl with OpenAI Images API.

Prerequisite:
  export OPENAI_API_KEY="your_api_key"

The script intentionally uses only the Python standard library plus Pillow, so it
works in Codex's bundled runtime without installing the OpenAI SDK.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_API_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = "gpt-image-1.5"


def load_jobs(work_order: Path) -> list[dict[str, Any]]:
    jobs = []
    with work_order.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                job = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_no}: {exc}") from exc
            for key in ("source", "mask", "target_output", "prompt"):
                if key not in job:
                    raise SystemExit(f"Missing {key!r} in work order line {line_no}")
            jobs.append(job)
    return jobs


def ensure_api_source(source_path: Path, out_dir: Path) -> Path:
    """Create a PNG copy for the API so source and mask formats match."""
    out_dir.mkdir(parents=True, exist_ok=True)
    api_source_path = out_dir / f"{source_path.stem}.source.png"
    with Image.open(source_path) as source_image:
        source_image.convert("RGB").save(api_source_path)
    return api_source_path


def ensure_alpha_mask(mask_path: Path, api_source_path: Path, out_dir: Path) -> Path:
    """Convert a black/white mask into an RGBA PNG mask with alpha."""
    with Image.open(api_source_path) as source_image:
        source_size = source_image.size
    with Image.open(mask_path) as mask_image:
        mask_l = mask_image.convert("L")
        if mask_l.size != source_size:
            raise SystemExit(
                f"Mask size mismatch for {api_source_path.name}: "
                f"source={source_size}, mask={mask_l.size}"
            )
        mask_rgba = mask_l.convert("RGBA")
        mask_rgba.putalpha(mask_l)

    out_dir.mkdir(parents=True, exist_ok=True)
    alpha_path = out_dir / f"{mask_path.stem}.alpha.png"
    mask_rgba.save(alpha_path)
    return alpha_path


def encode_multipart(
    fields: dict[str, str],
    files: list[tuple[str, Path]],
) -> tuple[bytes, str]:
    boundary = f"----codex-sticker-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    for name, path in files:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def call_openai_edit(
    api_key: str,
    source_path: Path,
    alpha_mask_path: Path,
    prompt: str,
    model: str,
    size: str,
    quality: str | None,
    input_fidelity: str | None,
    timeout: int,
    api_url: str = DEFAULT_API_URL,
) -> bytes:
    fields = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "output_format": "png",
        "response_format": "b64_json",
    }
    if quality:
        fields["quality"] = quality
    if input_fidelity:
        fields["input_fidelity"] = input_fidelity

    body, content_type = encode_multipart(
        fields=fields,
        files=[
            ("image[]", source_path),
            ("mask", alpha_mask_path),
        ],
    )
    request = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    payload = json.loads(response_body)
    try:
        b64_json = payload["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected API response: {payload}") from exc
    return base64.b64decode(b64_json)


def make_comparison(source_path: Path, output_path: Path, comparison_path: Path) -> None:
    with Image.open(source_path) as before, Image.open(output_path) as after:
        before_rgb = before.convert("RGB")
        after_rgb = after.convert("RGB")
        if after_rgb.size != before_rgb.size:
            after_rgb = after_rgb.resize(before_rgb.size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (before_rgb.width * 2, before_rgb.height), "white")
        canvas.paste(before_rgb, (0, 0))
        canvas.paste(after_rgb, (before_rgb.width, 0))
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(comparison_path, quality=94)


def process_one_job(
    job: dict[str, Any],
    index: int,
    args: argparse.Namespace,
    base_dir: Path,
    api_sources_dir: Path,
    alpha_masks_dir: Path,
    comparisons_dir: Path,
    api_key: str,
    print_lock: threading.Lock,
) -> tuple[int, str, str]:
    """Process a single job. Returns (result_code, source_name, message)."""
    source_path = Path(job["source"]).expanduser().resolve()
    mask_path = Path(job["mask"]).expanduser().resolve()
    output_path = Path(job["target_output"]).expanduser().resolve()
    comparison_path = comparisons_dir / f"{source_path.stem}.before-after.jpg"

    if output_path.exists() and not args.force:
        return (1, source_path.name, f"  skip existing: {output_path}")

    api_source_path = ensure_api_source(source_path, api_sources_dir)
    alpha_mask_path = ensure_alpha_mask(mask_path, api_source_path, alpha_masks_dir)

    if args.dry_run:
        return (0, source_path.name, f"  dry run target: {output_path}")

    with print_lock:
        print(f"  starting: {source_path.name}", flush=True)

    image_bytes = call_openai_edit(
        api_key=api_key,
        source_path=api_source_path,
        alpha_mask_path=alpha_mask_path,
        prompt=job["prompt"],
        model=args.model,
        size=args.size,
        quality=args.quality,
        input_fidelity=args.input_fidelity,
        timeout=args.timeout,
        api_url=args.api_url,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)

    with Image.open(BytesIO(image_bytes)) as generated:
        generated.verify()
    make_comparison(source_path, output_path, comparison_path)

    msg = f"  output:     {output_path}\n  comparison: {comparison_path}"
    return (0, source_path.name, msg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sticker removal inpainting jobs.")
    parser.add_argument("--work-order", required=True, type=Path)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default="auto")
    parser.add_argument("--quality", default="high")
    parser.add_argument("--input-fidelity", default="high")
    parser.add_argument("--limit", type=int, help="Process only the first N pending jobs.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing clean outputs.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to pause between API calls.")
    parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=1,
        help="Number of concurrent API calls (default 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate jobs and create alpha masks without calling the API.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        print('Run: export OPENAI_API_KEY="your_api_key"', file=sys.stderr)
        return 2

    work_order = args.work_order.expanduser().resolve()
    base_dir = work_order.parent
    api_sources_dir = base_dir / "api_sources"
    alpha_masks_dir = base_dir / "api_masks"
    comparisons_dir = base_dir / "comparisons_openai"

    jobs = load_jobs(work_order)
    if args.limit is not None:
        jobs = jobs[: args.limit]

    print_lock = threading.Lock()
    completed = 0
    skipped = 0
    failed = 0
    total = len(jobs)
    done_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_job = {
            executor.submit(
                process_one_job,
                job,
                index,
                args,
                base_dir,
                api_sources_dir,
                alpha_masks_dir,
                comparisons_dir,
                api_key or "",
                print_lock,
            ): (index, job)
            for index, job in enumerate(jobs, start=1)
        }

        for future in concurrent.futures.as_completed(future_to_job):
            index, job = future_to_job[future]
            try:
                result_code, source_name, msg = future.result()
            except Exception as exc:
                failed += 1
                done_count += 1
                with print_lock:
                    print(f"[{done_count}/{total}] failed: {job['source']}: {exc}", file=sys.stderr)
                continue

            done_count += 1
            if result_code == 1:  # skipped
                skipped += 1
                with print_lock:
                    print(f"[{done_count}/{total}] skip: {source_name}")
            elif result_code == 0:  # completed
                completed += 1
                with print_lock:
                    print(f"[{done_count}/{total}] repaired: {source_name}")
                    print(msg)
            else:  # failed
                failed += 1
                with print_lock:
                    print(f"[{done_count}/{total}] failed: {source_name}: {msg}", file=sys.stderr)

            if args.sleep > 0 and done_count < total:
                time.sleep(args.sleep)

    print()
    print(f"done: completed={completed}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
