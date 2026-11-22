#!/usr/bin/env python3
"""Jibali scene 06 (17-20 s): product reveal from the ORIGINAL package photo.

Free and local. A slow push-in on the authoritative front photo, made only by
cropping and resizing with sub-pixel precision (no repainting, no colour
grading, no generated pixels), so the green/gold label, the Arabic bird logo and
the printed words stay exactly as photographed. The whole label stays in frame
on every frame. The photo sits in a 4:5 panel above a band in the label's own
green, which holds the closing titles.

Output: 72 frames, 24 fps, 1080x1920, H.264 (BT.709), no audio stream.
The closing titles are NOT burned in here; they are added over the whole film
from output/brand-film-45/closing-titles.ass at final assembly (use --titles
for a standalone preview with them burned in).

Usage:
  python3 scripts/render-scene-06.py OUT.mp4 [--titles closing-titles.ass]
"""
import argparse
import math
import pathlib
import subprocess
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "references/bread-2026-11-20/WhatsApp Image 2026-11-20 at 8.38.25 PM.jpeg"

W, H, FPS, FRAMES = 1080, 1920, 24, 72

# Layout: the photo can't be push-in cropped to full 9:16 without cutting the
# label (it fills ~72 % of the photo's width), so the end card is composed:
#   - photo panel, 1080x1350 (4:5), top of frame, slow push-in
#   - 2 px gold rule (label gold, sampled from the photo)
#   - brand band in the label's own green (sampled), holding the closing titles
#     above the bottom ~320 px that the Reels interface covers
PANEL_W, PANEL_H = 1080, 1350
RULE_H = 2
GREEN = (45, 101, 96)     # median of label green in the source photo
GOLD = (206, 162, 115)    # median of label gold in the source photo
PANEL_ASPECT = PANEL_W / PANEL_H

# Measured label extent in the source (3120x4160, upright): x 537-2776, y 806-2890.
# Crop windows (source pixels) keep the whole tilted label with margin on every frame.
LABEL_CX = 1657
START = dict(cx=LABEL_CX, cy=1960, w=2900)   # label ~77 % of panel width
END = dict(cx=LABEL_CX, cy=1880, w=2560)     # ~1.13x push; label ~88 %, 160 px margins


def ease_out_sine(t: float) -> float:
    return math.sin(t * math.pi / 2)


def window(i: int):
    t = ease_out_sine(i / (FRAMES - 1))
    cx = START["cx"] + (END["cx"] - START["cx"]) * t
    cy = START["cy"] + (END["cy"] - START["cy"]) * t
    w = START["w"] + (END["w"] - START["w"]) * t
    h = w / PANEL_ASPECT
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--titles", help="ASS file to burn in (preview only); times shifted so 17 s = 0 s")
    args = ap.parse_args()

    src = Image.open(SOURCE).convert("RGB")
    sw, sh = src.size
    for i in (0, FRAMES - 1):
        x0, y0, x1, y1 = window(i)
        assert x0 >= 0 and y0 >= 0 and x1 <= sw and y1 <= sh, f"crop out of bounds at frame {i}"

    vf = ["scale=out_color_matrix=bt709:out_range=tv", "format=yuv420p"]
    tmpdir = tempfile.TemporaryDirectory()
    if args.titles:
        # Shift the film-time titles (17-20 s) to scene time (0-3 s).
        ass = pathlib.Path(args.titles).read_text(encoding="utf-8-sig")
        ass = ass.replace("0:00:17.00,0:00:20.00", "0:00:00.00,0:00:03.00")
        shifted = pathlib.Path(tmpdir.name) / "titles.ass"
        shifted.write_text(ass, encoding="utf-8")
        vf.insert(0, f"subtitles={shifted}")

    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-vf", ",".join(vf),
        "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-tune", "film",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-an", "-movflags", "+faststart", args.out,
    ]
    canvas = Image.new("RGB", (W, H), GREEN)
    canvas.paste(Image.new("RGB", (W, RULE_H), GOLD), (0, PANEL_H))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(FRAMES):
        canvas.paste(src.resize((PANEL_W, PANEL_H), Image.LANCZOS, box=window(i)), (0, 0))
        proc.stdin.write(canvas.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
