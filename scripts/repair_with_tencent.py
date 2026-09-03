#!/usr/bin/env python3
"""
Run sticker removal jobs with Tencent Cloud Hunyuan ImageInpaintingRemoval.

Prerequisite:
  export TENCENTCLOUD_SECRET_ID="your_secret_id"
  export TENCENTCLOUD_SECRET_KEY="your_secret_key"

The Tencent API removes the white area in MaskImage and preserves the black area.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image


ENDPOINT = "aiart.tencentcloudapi.com"
SERVICE = "aiart"
VERSION = "2022-12-29"
ACTION = "ImageInpaintingRemoval"
DEFAULT_REGION = "ap-guangzhou"


def validate_secret_env(name: str, value: str | None) -> str | None:
    if not value:
        return f"{name} is not set"
    if any(marker in value for marker in ("你的", "export ", "“", "”", "\n")):
        return f"{name} contains placeholder text, nested export text, curly quotes, or a newline"
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return f"{name} contains non-ASCII characters; use straight quotes and the raw Tencent value"
    return None


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
            for key in ("source", "mask", "target_output"):
                if key not in job:
                    raise SystemExit(f"Missing {key!r} in work order line {line_no}")
            jobs.append(job)
    return jobs


def prepare_tencent_mask(mask_path: Path, source_path: Path, out_dir: Path) -> Path:
    """Tencent expects a one-channel grayscale mask, same size as the source."""
    with Image.open(source_path) as source_image:
        source_size = source_image.size
    with Image.open(mask_path) as mask_image:
        mask_l = mask_image.convert("L")
        if mask_l.size != source_size:
            raise SystemExit(
                f"Mask size mismatch for {source_path.name}: "
                f"source={source_size}, mask={mask_l.size}"
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{mask_path.stem}.tencent-mask.png"
    mask_l.save(out_path)
    return out_path


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def sign(secret_key: str, date: str, string_to_sign: str) -> str:
    secret_date = hmac.new(("TC3" + secret_key).encode(), date.encode(), hashlib.sha256).digest()
    secret_service = hmac.new(secret_date, SERVICE.encode(), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    return hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()


def make_headers(
    secret_id: str,
    secret_key: str,
    payload_json: str,
    region: str,
) -> dict[str, str]:
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{ENDPOINT}\nx-tc-action:{ACTION.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_request_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        [
            http_request_method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            hashed_request_payload,
        ]
    )

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join(
        [algorithm, str(timestamp), credential_scope, hashed_canonical_request]
    )
    signature = sign(secret_key, date, string_to_sign)
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": ENDPOINT,
        "X-TC-Action": ACTION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VERSION,
        "X-TC-Region": region,
    }


def call_tencent(
    secret_id: str,
    secret_key: str,
    source_path: Path,
    mask_path: Path,
    region: str,
    rsp_img_type: str,
    timeout: int,
) -> bytes:
    payload = {
        "InputImage": image_to_base64(source_path),
        "Mask": image_to_base64(mask_path),
        "RspImgType": rsp_img_type,
        "LogoAdd": 0,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    request = urllib.request.Request(
        f"https://{ENDPOINT}",
        data=payload_json.encode("utf-8"),
        headers=make_headers(secret_id, secret_key, payload_json, region),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tencent API error {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    data = json.loads(response_body)
    response = data.get("Response", {})
    if "Error" in response:
        raise RuntimeError(json.dumps(response["Error"], ensure_ascii=False))

    result_b64 = response.get("ResultImage")
    if result_b64:
        return base64.b64decode(result_b64)

    result_url = response.get("ResultImageUrl")
    if result_url:
        with urllib.request.urlopen(result_url, timeout=timeout) as image_response:
            return image_response.read()

    raise RuntimeError(f"Unexpected Tencent response: {json.dumps(data, ensure_ascii=False)}")


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
    total: int,
    args: argparse.Namespace,
    masks_dir: Path,
    output_dir: Path,
    comparisons_dir: Path,
    secret_id: str,
    secret_key: str,
    print_lock: threading.Lock,
) -> tuple[str, str]:
    """Process a single job. Returns (status, message): status = 'completed'|'skipped'|'failed'."""
    source_path = Path(job["source"]).expanduser().resolve()
    mask_path = Path(job["mask"]).expanduser().resolve()
    output_path = output_dir / f"{source_path.stem}.clean.png"
    comparison_path = comparisons_dir / f"{source_path.stem}.before-after.jpg"

    if output_path.exists() and not args.force:
        with print_lock:
            print(f"[{index}/{total}] skip existing: {source_path.name}")
        return ("skipped", "")

    tencent_mask_path = prepare_tencent_mask(mask_path, source_path, masks_dir)

    with print_lock:
        print(f"[{index}/{total}] repairing with Tencent: {source_path.name}")
        print(f"  starting: {source_path.name}", flush=True)

    if args.dry_run:
        with print_lock:
            print(f"  dry run target: {output_path}")
        return ("completed", "")

    image_bytes = call_tencent(
        secret_id=secret_id,
        secret_key=secret_key,
        source_path=source_path,
        mask_path=tencent_mask_path,
        region=args.region,
        rsp_img_type=args.rsp_img_type,
        timeout=args.timeout,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)
    with Image.open(output_path) as generated:
        generated.verify()
    make_comparison(source_path, output_path, comparison_path)

    with print_lock:
        print(f"  output: {output_path}")
        print(f"  comparison: {comparison_path}")

    return ("completed", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tencent sticker removal jobs.")
    parser.add_argument("--work-order", required=True, type=Path)
    parser.add_argument("--region", default=os.environ.get("TENCENTCLOUD_REGION", DEFAULT_REGION))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--rsp-img-type", choices=("base64", "url"), default="base64")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=1,
        help="Number of concurrent API calls (default 1).",
    )
    args = parser.parse_args()

    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID")
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY")
    secret_errors = [
        error
        for error in (
            validate_secret_env("TENCENTCLOUD_SECRET_ID", secret_id),
            validate_secret_env("TENCENTCLOUD_SECRET_KEY", secret_key),
        )
        if error
    ]
    if secret_errors and not args.dry_run:
        for error in secret_errors:
            print(error, file=sys.stderr)
        return 2

    work_order = args.work_order.expanduser().resolve()
    base_dir = work_order.parent
    masks_dir = base_dir / "tencent_masks"
    output_dir = base_dir / "output_tencent"
    comparisons_dir = base_dir / "comparisons_tencent"

    jobs = load_jobs(work_order)
    if args.limit is not None:
        jobs = jobs[: args.limit]

    total = len(jobs)
    completed = 0
    skipped = 0
    failed = 0
    print_lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_idx = {
            executor.submit(
                process_one_job,
                job, index, total, args,
                masks_dir, output_dir, comparisons_dir,
                secret_id or "", secret_key or "",
                print_lock,
            ): index
            for index, job in enumerate(jobs, start=1)
        }

        for future in concurrent.futures.as_completed(future_to_idx):
            try:
                status, _ = future.result()
                if status == "completed":
                    completed += 1
                elif status == "skipped":
                    skipped += 1
            except Exception as exc:
                failed += 1
                idx = future_to_idx[future]
                with print_lock:
                    print(f"  [{idx}/{total}] failed: {exc}", file=sys.stderr)

    print()
    print(f"done: completed={completed}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
