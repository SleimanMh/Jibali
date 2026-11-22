#!/usr/bin/env python3
"""Jibali x Pruna: smooth 20 s edit (free, local). No API calls.

- Picture: the five 480p clips, each trimmed to its best moment, joined with
  0.5 s dissolves, then a soft dissolve into the real package reveal (scene 06).
  Scaled locally to 1080x1920 (no paid upscale). Arabic verse captions and the
  closing titles are typeset on top.
- Sound: each clip's own generated sound, crossfaded scene to scene in step with
  the dissolves, under one continuous music bed, plus the hoopoe's call during
  the flight; fades out into the reveal. Two-pass loudness to -14 LUFS / -1.5 dBTP.

Usage: python3 pruna-film/scripts/edit.py [v1|v2]   (v1 = first demo, v2 = owner's reference look)
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
REPO = HERE.parent
OUT = HERE / "out"
FPS = 24
TOTAL = 480                 # 20 s
XF_REVEAL = 10              # dissolve into the package reveal
REVEAL = OUT / "reveal-3.4s.mp4"   # 82 frames, from scripts/render-scene-06.py --seconds 3.4
C1, C2 = OUT / "clips-480p", OUT / "v2" / "clips-480p"

# (clip file, in-point seconds, length in frames) — chosen by eye for the fullest action
PLANS = {
    "v1": dict(xf=12, call=1.5, captions="arabic-captions.ass", out="jibali-480p-demo.mp4", cuts=[
        (C1 / "01.mp4", 0.30, 103),   # flight over Rashaya and Jabal al-Sheikh
        (C1 / "02.mp4", 1.20, 94),    # settles on the rock, crest fans
        (C1 / "03.mp4", 1.00, 82),    # grain streams through the millstones
        (C1 / "04.mp4", 0.00, 86),    # kneading
        (C1 / "05.mp4", 1.30, 91),    # saj steaming over the fire
    ]),
    "v2": dict(xf=10, call=2.8, captions="arabic-captions-v2.ass", out="jibali-v2-480p.mp4", cuts=[
        (C2 / "hermon.mp4", 0.60, 60),
        (C1 / "01.mp4", 0.30, 64),    # the approved hoopoe flight
        (C2 / "wheat.mp4", 1.00, 52),
        (C2 / "grain.mp4", 1.00, 56),
        (C2 / "saltwater.mp4", 0.20, 52),    # salt still falling
        (C2 / "knead.mp4", 0.00, 56),        # first 2.3 s only: later the dough morphs
        (C2 / "fire.mp4", 1.00, 48),
        (C2 / "sajbread.mp4", 0.60, 52),
        (C2 / "stack.mp4", 1.50, 48),        # more steam later in the clip
    ]),
}
W2 = OUT / "v2" / "wan-480p"
# v3: Wan 2.2 where the P-Video clip overacted; audio borrowed from the P-Video clip of the same scene (Wan has no sound)
PLANS["v3"] = dict(xf=10, call=2.8, captions="arabic-captions-v2.ass", out="jibali-v3-480p.mp4", cuts=[
    (C2 / "hermon.mp4", 0.60, 60),
    (C1 / "01.mp4", 0.30, 64),
    (C2 / "wheat.mp4", 1.00, 52),
    (W2 / "grain.mp4", 0.30, 56, C2 / "grain.mp4"),
    (W2 / "saltwater.mp4", 0.20, 52, C2 / "saltwater.mp4"),
    (W2 / "knead.mp4", 0.30, 56, C2 / "knead.mp4"),
    (C2 / "fire.mp4", 1.00, 48),
    (W2 / "sajbread.mp4", 0.30, 52, C2 / "sajbread.mp4"),
    (W2 / "stack.mp4", 0.50, 48, C2 / "stack.mp4"),
])
PLAN = PLANS[sys.argv[1] if len(sys.argv) > 1 else "v1"]
CUTS, XF = PLAN["cuts"], PLAN["xf"]


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], check=True)


def hoopoe_call(path):
    spec = importlib.util.spec_from_file_location("synth", REPO / "scripts/synth-audio.py")
    m = importlib.util.module_from_spec(spec)
    sys_argv, sys.argv = sys.argv, ["synth", str(OUT / "unused")]
    spec.loader.exec_module(m)
    sys.argv = sys_argv
    call = m.hoopoe_call()
    call = call / (np.max(np.abs(call)) + 1e-9) * 0.5
    m.write(path, m.stereo(call))


def main():
    n_reveal = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                                   "stream=nb_read_packets", "-of", "csv=p=0", str(REVEAL)], capture_output=True, text=True).stdout)
    total = sum(c[2] for c in CUTS) - XF * (len(CUTS) - 1) - XF_REVEAL + n_reveal
    assert total == TOTAL, f"timeline is {total} frames, expected {TOTAL}"

    call = OUT / "hoopoe-call.wav"
    hoopoe_call(call)
    music = REPO / "audio/music/bed.wav"

    inputs, v, a, extra = [], [], [], []
    for i, cut in enumerate(CUTS):
        clip, t_in, n = cut[:3]
        inputs += ["-i", str(clip)]
        s = round(t_in * FPS)
        v.append(f"[{i}:v]fps={FPS},trim=start_frame={s}:end_frame={s + n},setpts=PTS-STARTPTS,"
                 f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1,format=yuv420p,settb=1/{FPS}[v{i}]")
        asrc = f"{i}:a"
        if len(cut) > 3:                       # sound from another clip of the same scene
            extra.append(str(cut[3])); asrc = f"EXTRA{len(extra) - 1}:a"
        a.append(f"[{asrc}]atrim=start={s / FPS}:duration={n / FPS},asetpts=PTS-STARTPTS,"
                 f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
    k = len(CUTS)
    inputs += ["-i", str(REVEAL), "-i", str(music), "-i", str(call)]
    for j, e in enumerate(extra):
        inputs += ["-i", e]
        a = [x.replace(f"[EXTRA{j}:a]", f"[{k + 3 + j}:a]") for x in a]
    v.append(f"[{k}:v]fps={FPS},setsar=1,format=yuv420p,settb=1/{FPS}[v{k}]")

    # picture: dissolve chain
    chain, cur, length = [], "v0", CUTS[0][2]
    for i in range(1, k + 1):
        d = XF if i < k else XF_REVEAL
        nxt = CUTS[i][2] if i < k else n_reveal
        off = (length - d) / FPS
        out = f"x{i}"
        chain.append(f"[{cur}][v{i}]xfade=transition=fade:duration={d / FPS}:offset={off}[{out}]")
        cur, length = out, length - d + nxt
    caps, titles = HERE / PLAN["captions"], REPO / "output/brand-film-45/closing-titles.ass"
    chain.append(f"[{cur}]subtitles={caps},subtitles={titles}[vout]")

    # sound: clip sounds crossfaded in step with the dissolves, under music + hoopoe call
    achain, cur = [], "a0"
    for i in range(1, k):
        achain.append(f"[{cur}][a{i}]acrossfade=d={XF / FPS}:c1=tri:c2=tri[ac{i}]")
        cur = f"ac{i}"
    clips_end = (TOTAL - n_reveal + XF_REVEAL) / FPS        # when the clip sound has to be gone
    achain.append(f"[{cur}]afade=t=out:st={clips_end - 0.7}:d=0.7,volume=-8dB,apad,atrim=0:{TOTAL / FPS}[scene]")
    achain.append(f"[{k + 1}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{TOTAL / FPS},"
                  f"asetpts=PTS-STARTPTS,afade=t=in:d=1.2,afade=t=out:st={TOTAL / FPS - 1.2}:d=1.2,volume=-1dB[music]")
    achain.append(f"[{k + 2}:a]aresample=48000,adelay={int(PLAN["call"] * 1000)}:all=1,volume=-9dB,apad,atrim=0:{TOTAL / FPS}[call]")
    achain.append("[scene][music][call]amix=inputs=3:normalize=0:duration=first[mix]")

    graph = ";".join(v + chain + a + achain)
    # pass 1: measure loudness
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *inputs, "-filter_complex",
                           graph.replace("[mix]", "[mix0];[mix0]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[mix]"),
                           "-map", "[vout]", "-map", "[mix]", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", meas, re.S)
    if not m:
        sys.exit("loudness pass failed:\n" + meas[-1500:])
    j = json.loads(m.group(0))
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000")
    final = OUT / PLAN["out"]
    ff(*inputs, "-filter_complex", graph.replace("[mix]", f"[mix0];[mix0]{ln}[mix]"),
       "-map", "[vout]", "-map", "[mix]", "-frames:v", str(TOTAL), "-t", str(TOTAL / FPS),
       "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
       "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(final))
    print(f"wrote {final.relative_to(REPO)}")
    starts, t = [], 0
    for i, cut in enumerate(CUTS):
        n = cut[2]
        starts.append(round(t / FPS, 2)); t += n - XF
    print("scene starts (s):", starts, "| reveal from", round((TOTAL - n_reveal) / FPS, 2), "fully in at", round((TOTAL - n_reveal + XF_REVEAL) / FPS, 2))


if __name__ == "__main__":
    main()
