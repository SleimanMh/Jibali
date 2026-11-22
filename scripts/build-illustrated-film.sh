#!/usr/bin/env bash
# Build the illustrated Jibali film end to end — free, local, no API keys.
#   1. scenes 01-05 (0-17 s) rendered from motion/jibali-motion.html in headless Chromium
#   2. scene 06 (17-20 s) product reveal from the original package photo
#   3. closing titles burned in at 17-20 s
#   4. synthesized music + sound effects (+ voice if audio/voice/tagline.wav exists), -14 LUFS
# Output: output/brand-film-45/illustrated/jibali-20s-illustrated.mp4
# Needs: ffmpeg, python3 (numpy, scipy, Pillow), node with playwright.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
OUT=output/brand-film-45/illustrated
mkdir -p "$OUT"

echo "== 1/4 scenes 01-05"
node motion/render-motion.js video "$OUT/scenes-01-05.mp4"
echo "== 2/4 scene 06"
python3 scripts/render-scene-06.py output/brand-film-45/scenes/06-product-reveal.mp4
echo "== 3/4 picture + closing titles"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp output/brand-film-45/closing-titles.ass "$TMP/titles.ass"
ffmpeg -v error -y -i "$OUT/scenes-01-05.mp4" -i output/brand-film-45/scenes/06-product-reveal.mp4 \
  -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0,settb=1/24,setpts=N,fps=24,subtitles=$TMP/titles.ass[v]" \
  -map "[v]" -c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv -an \
  "$OUT/jibali-20s-illustrated-silent.mp4"
echo "== 4/4 audio"
python3 scripts/synth-audio.py
MUSIC_DB=${MUSIC_DB:--4} SFX_DB=${SFX_DB:-0} scripts/mix-audio.sh \
  "$OUT/jibali-20s-illustrated-silent.mp4" "$OUT/jibali-20s-illustrated.mp4"
