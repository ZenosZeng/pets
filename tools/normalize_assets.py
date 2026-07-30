"""将所有桌宠 GIF 规范到统一透明画布，并按可见内容底部居中。"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageSequence

STATES = ("xiaobai", "xiaojimao", "together")
DEFAULT_CANVAS_SIZE = 220


def _load_frames(path: Path) -> tuple[list[Image.Image], list[int], int]:
    with Image.open(path) as source:
        default_duration = int(source.info.get("duration", 100))
        loop = int(source.info.get("loop", 0))
        frames: list[Image.Image] = []
        durations: list[int] = []

        for frame in ImageSequence.Iterator(source):
            frames.append(frame.convert("RGBA").copy())
            duration = int(frame.info.get("duration", default_duration))
            durations.append(max(0, duration))

    if not frames:
        raise ValueError("动画没有可读取的帧")
    return frames, durations, loop


def _visible_union(frames: list[Image.Image]) -> tuple[int, int, int, int]:
    boxes = [
        box
        for frame in frames
        if (box := frame.getchannel("A").getbbox()) is not None
    ]
    if not boxes:
        raise ValueError("动画所有帧均完全透明")

    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _already_normalized(
    frames: list[Image.Image],
    visible_union: tuple[int, int, int, int],
    canvas_size: int,
) -> bool:
    left, top, right, bottom = visible_union
    content_width = right - left
    content_height = bottom - top
    return (
        all(frame.size == (canvas_size, canvas_size) for frame in frames)
        and bottom == canvas_size
        and abs((left + right) - canvas_size) <= 1
        and (
            content_width >= canvas_size - 1
            or content_height >= canvas_size - 1
        )
    )


def _prepare_gif_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """生成共享调色板的 GIF 帧，并固定 255 号索引为透明色。"""

    width, height = frames[0].size
    palette_source = Image.new(
        "RGB",
        (width, height * len(frames)),
        (255, 255, 255),
    )
    rgb_frames: list[Image.Image] = []

    for index, frame in enumerate(frames):
        alpha = frame.getchannel("A")
        rgb = Image.new("RGB", frame.size, (255, 255, 255))
        rgb.paste(frame.convert("RGB"), mask=alpha)
        rgb_frames.append(rgb)
        palette_source.paste(rgb, (0, index * height))

    # 只使用 0..254，明确为透明像素保留索引 255。
    master_palette = palette_source.quantize(
        colors=255,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )

    gif_frames: list[Image.Image] = []
    for frame, rgb in zip(frames, rgb_frames, strict=True):
        paletted = rgb.quantize(
            palette=master_palette,
            dither=Image.Dither.NONE,
        )
        alpha = frame.getchannel("A")
        transparent_mask = alpha.point(
            lambda value: 255 if value == 0 else 0,
        )
        paletted.paste(255, mask=transparent_mask)
        paletted.info["transparency"] = 255
        gif_frames.append(paletted)

    return gif_frames


def normalize_gif(path: Path, canvas_size: int, force: bool = False) -> bool:
    """规范单个 GIF；发生修改时返回 True。"""

    frames, durations, loop = _load_frames(path)
    visible_union = _visible_union(frames)
    if not force and _already_normalized(frames, visible_union, canvas_size):
        return False

    left, top, right, bottom = visible_union
    content_width = right - left
    content_height = bottom - top
    scale = min(canvas_size / content_width, canvas_size / content_height)
    target_width = max(1, round(content_width * scale))
    target_height = max(1, round(content_height * scale))
    paste_x = (canvas_size - target_width) // 2
    paste_y = canvas_size - target_height

    normalized_frames: list[Image.Image] = []
    for frame in frames:
        content = frame.crop(visible_union)
        if content.size != (target_width, target_height):
            content = content.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS,
            )

        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        canvas.alpha_composite(content, (paste_x, paste_y))
        normalized_frames.append(canvas)

    gif_frames = _prepare_gif_frames(normalized_frames)
    temporary_path = path.with_name(f".{path.stem}.normalized.gif")
    try:
        gif_frames[0].save(
            temporary_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,
            transparency=255,
            # Pillow must optimize transparent delta frames here; without it,
            # a fully transparent frame can cause all following frames to drop.
            optimize=True,
        )
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_CANVAS_SIZE,
        help="正方形透明画布边长，默认 220",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已经规范化也重新处理",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.size <= 0:
        raise SystemExit("--size 必须为正整数")

    assets_root = Path(__file__).resolve().parents[1] / "assets"
    paths = sorted(
        path
        for state in STATES
        for path in (assets_root / state).glob("*.gif")
        if path.is_file()
    )

    changed = 0
    for path in paths:
        if normalize_gif(path, args.size, args.force):
            changed += 1
            print(f"normalized: {path.relative_to(assets_root)}")
        else:
            print(f"unchanged:  {path.relative_to(assets_root)}")

    print(
        f"GIF normalization complete: {changed} changed, "
        f"{len(paths) - changed} unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
