#!/usr/bin/env python3
"""
Prepare masks and review previews for price-tag / discount-badge sticker removal.

Target sticker layout (learned from cool_before.png reference):
- Bottom-left price block: "预估最低价 ¥XXX 起"
- Bottom-right discount badge: "满X件享X折"

This script does not modify source images. It creates:
- masks/: white sticker-removal masks on black background
- previews/: source images with semi-transparent red mask overlay
- work_order.jsonl: one inpainting job description per source image
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_EXCLUDE_KEYWORDS = ("去除", "clean", "output", "result", "mask", "preview")

PROMPT = """商品图片价格贴纸移除
请基于原图进行精修，只去除图片中的平台促销价格贴纸，保留所有品牌设计元素：

1. 去除左下角"预估最低价"标签及其下方的价格文字（如"¥198 起"），包括标签背景色与所有文字。
2. 去除右下角折扣徽章（如"满2件享9折"），包括徽章背景图形与所有文字。
3. 去除后请自然补全为干净的背景，质感与原图一致，不要出现明显修补痕迹。
4. 保留品牌 logo、产品文案、品质徽章（如"美利奴羊毛 × COOLMAX"）等所有品牌设计元素。
5. 保留模特、人物、服装、构图，不要改变人物比例或重绘五官。
6. 保持原图的光线、色彩和清晰度。
7. 最终效果应像一张干净的品牌商品图，没有任何平台叠加的价格或折扣贴纸。"""


@dataclass(frozen=True)
class RelativeRect:
    name: str
    left: float
    top: float
    right: float
    bottom: float

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        return (
            round(self.left * width),
            round(self.top * height),
            round(self.right * width),
            round(self.bottom * height),
        )


# Sticker regions — relative coordinates (0.0–1.0), learned from reference image:
# cool_before.png vs cool.jpg (1440×1440)
DEFAULT_RECTS = (
    RelativeRect("bottom_promo_bar", 0.0, 0.87, 1.0, 1.0),
)


def iter_images(input_dir: Path, exclude_keywords: Iterable[str]) -> list[Path]:
    images = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        if any(keyword in path.stem for keyword in exclude_keywords):
            continue
        images.append(path)
    return images


def make_mask(size: tuple[int, int], rects: Iterable[RelativeRect], feather: int) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for rect in rects:
        draw.rectangle(rect.to_pixels(width, height), fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return mask


def make_preview(source: Image.Image, mask: Image.Image) -> Image.Image:
    preview = source.convert("RGBA")
    overlay = Image.new("RGBA", source.size, (255, 0, 0, 0))
    alpha = mask.point(lambda value: int(value * 0.38))
    overlay.putalpha(alpha)
    return Image.alpha_composite(preview, overlay).convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare masks for price-tag / discount-badge sticker removal."
    )
    parser.add_argument("--input-dir", required=True, type=Path, help="Folder containing source images.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Folder for masks, previews, and work order.")
    parser.add_argument("--feather", type=int, default=8, help="Mask edge feather radius in pixels.")
    parser.add_argument(
        "--include-reference",
        action="store_true",
        help="Also process files whose names look like already-clean reference images.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    masks_dir = out_dir / "masks"
    previews_dir = out_dir / "previews"
    masks_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    exclude = () if args.include_reference else DEFAULT_EXCLUDE_KEYWORDS
    images = iter_images(input_dir, exclude)
    if not images:
        print(f"No source images found in {input_dir}")
        return 1

    work_order_path = out_dir / "work_order.jsonl"
    with work_order_path.open("w", encoding="utf-8") as work_order:
        for image_path in images:
            with Image.open(image_path) as image:
                source = image.convert("RGB")
                mask = make_mask(source.size, DEFAULT_RECTS, args.feather)
                preview = make_preview(source, mask)

            mask_path = masks_dir / f"{image_path.stem}.mask.png"
            preview_path = previews_dir / f"{image_path.stem}.preview.jpg"
            output_path = out_dir / "output" / f"{image_path.stem}.clean.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            mask.save(mask_path)
            preview.save(preview_path, quality=94)
            work_order.write(
                json.dumps(
                    {
                        "source": str(image_path),
                        "mask": str(mask_path),
                        "target_output": str(output_path),
                        "prompt": PROMPT,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            print(f"prepared: {image_path.name}")
            print(f"  mask:    {mask_path}")
            print(f"  preview: {preview_path}")

    print(f"work order: {work_order_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
