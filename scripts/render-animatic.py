#!/usr/bin/env python3
"""Jibali 20 s PREVIEW animatic (free, local). NOT the final film.

Lays out the full 480-frame timeline so pacing can be judged before any paid
generation:
  01 0-4 s    Hermon/Rashaya reference photo, slow push    (hoopoe flight pending)
  02 4-7 s    placeholder card                             (hoopoe landing pending)
  03 7-10 s   storyboard mill panel, slow push             (reference only; mill clip pending)
  04 10-13 s  placeholder cards: salt, water, kneading     (pending)
  05 13-17 s  real saj reference photo, slow push          (saj-on-fire clip pending)
  06 17-20 s  FINAL product reveal (scenes/06-product-reveal.mp4)
Closing titles from closing-titles.ass are burned in at 17-20 s.
Every unfinished shot carries a visible "PREVIEW" tag. No audio stream.

Usage: python3 scripts/render-animatic.py OUT.mp4
"""
import math
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILM = ROOT / "output/brand-film-45"
W, H, FPS = 1080, 1920, 24
GREEN, GOLD, CREAM = (45, 101, 96), (206, 162, 115), (255, 245, 234)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def ease(t):
    return math.sin(t * math.pi / 2)


def fitted_still(img, t, push=0.06):
    """Image fit to frame width on a blurred fill of itself, with a slow push-in."""
    img = img.convert("RGB")
    bg = img.resize((W, H), Image.BICUBIC, box=cover_box(img)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.35)
    z = 1 + push * ease(t)
    fw = W
    fh = round(W * img.height / img.width)
    sw, sh = img.width / z, img.height / z
    box = ((img.width - sw) / 2, (img.height - sh) / 2, (img.width + sw) / 2, (img.height + sh) / 2)
    fg = img.resize((fw, fh), Image.LANCZOS, box=box)
    bg.paste(fg, (0, (H - fh) // 2))
    return bg


def cover_box(img):
    a = W / H
    if img.width / img.height > a:
        w = img.height * a
        return ((img.width - w) / 2, 0, (img.width + w) / 2, img.height)
    h = img.width / a
    return (0, (img.height - h) / 2, img.width, (img.height + h) / 2)


def card(title, lines):
    im = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(im)
    d.rectangle((60, 260, W - 60, H - 260), outline=GOLD, width=3)
    y = 760
    d.text((W / 2, y), title, font=font(64, True), fill=GOLD, anchor="mm")
    y += 110
    for ln in lines:
        d.text((W / 2, y), ln, font=font(38), fill=CREAM, anchor="mm")
        y += 62
    return im


def tag(im, text):
    d = ImageDraw.Draw(im, "RGBA")
    f = font(30, True)
    x0, y0 = 40, 230
    l, t, r, b = d.textbbox((x0 + 24, y0 + 14), text, font=f)
    d.rounded_rectangle((x0, y0, r + 24, b + 14), radius=22, fill=(0, 0, 0, 150))
    d.text((x0 + 24, y0 + 14), text, font=f, fill=(255, 255, 255, 235))
    return im


def frames():
    hermon = Image.open(ROOT / "references/rashaya-and-saj/images (6).jfif")
    saj = Image.open(ROOT / "references/rashaya-and-saj/images (7).jfif")
    sb = Image.open(ROOT / "output/concepts/jibali-rashaya-saj-storyboard-v2.png").convert("RGB")
    pw = sb.width / 4
    mill = sb.crop((round(pw * 1) + 6, 6, round(pw * 2) - 6, sb.height - 6))

    plan = [
        (96, lambda t: tag(fitted_still(hermon, t), "PREVIEW · 01 · Hermon · hoopoe clip pending")),
        (72, lambda t: tag(card("02 · Hoopoe lands", ["Same hoopoe descends onto a", "limestone in golden mountain wheat"]),
                           "PREVIEW · 02 · AI clip pending")),
        (72, lambda t: tag(fitted_still(mill, t), "PREVIEW · 03 · mill (storyboard ref) · clip pending")),
        (18, lambda t: tag(card("04a · Salt", ["A pinch of salt into", "whole-wheat flour"]), "PREVIEW · 04 · still pending")),
        (18, lambda t: tag(card("04b · Water", ["Water poured into", "the same bowl"]), "PREVIEW · 04 · still pending")),
        (36, lambda t: tag(card("04 · Kneading", ["Artisan hands knead", "flour, water and salt"]), "PREVIEW · 04 · AI clip pending")),
        (96, lambda t: tag(fitted_still(saj, t), "PREVIEW · 05 · saj photo · fire clip pending")),
    ]
    for n, fn in plan:
        for i in range(n):
            yield fn(i / max(n - 1, 1))


def main():
    out = sys.argv[1]
    with tempfile.TemporaryDirectory() as td:
        part = pathlib.Path(td) / "01-05.mp4"
        enc = ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                              "-vf", "scale=out_color_matrix=bt709:out_range=tv", *enc, str(part)],
                             stdin=subprocess.PIPE)
        count = 0
        for f in frames():
            p.stdin.write(f.tobytes())
            count += 1
        p.stdin.close()
        assert p.wait() == 0 and count == 408, count

        ass = pathlib.Path(td) / "titles.ass"
        ass.write_bytes((FILM / "closing-titles.ass").read_bytes())
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(part), "-i", str(FILM / "scenes/06-product-reveal.mp4"),
                        "-filter_complex", f"[0:v][1:v]concat=n=2:v=1:a=0,settb=1/24,setpts=N,fps=24,subtitles={ass}[v]",
                        "-map", "[v]", *enc, "-an", "-movflags", "+faststart", out], check=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
