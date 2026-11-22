#!/usr/bin/env python3
"""Jibali x Pruna pipeline: stills -> 480p demo clips -> cut -> HD upscale.

Uses Pruna's own API (https://api.pruna.ai/v1), one key for everything:
  p-image / p-image-edit   keyframe stills (edit takes reference photos)
  p-video-2-pro            image-to-video, 480p/768p, 9:16, 5-15 s, returns generated sound
  p-video-upscale          video upscale to 1080p (also 2k/4k)

The key is sent in the `apikey` header. In the cloud session it is stored as a
network secret and injected by the proxy; locally, set PRUNA_API_KEY.

SPENDING GUARD: every paid call is checked against spend-ledger.json. Nothing
runs unless `approved_limit` there covers spent + this call's estimate. Raise the
limit only with the owner's explicit approval. No automatic retries.

Commands (run from pruna-film/):
  python3 scripts/pruna.py estimate            # cost of the planned run, no API calls
  python3 scripts/pruna.py stills [ID ...]     # generate keyframe stills -> out/stills/
  python3 scripts/pruna.py demo [ID ...]       # 480p clips from the stills -> out/clips-480p/
  python3 scripts/pruna.py cut                 # free: edit clips + real reveal + titles + audio -> out/
  python3 scripts/pruna.py upscale             # p-video-upscale the 0-17 s AI part to 1080p, re-cut
Options: --mode cost|speed|quality (demo, default speed)  --resolution 480p|768p  --dry-run
"""
import argparse
import json
import mimetypes
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
REPO = HERE.parent
API = "https://api.pruna.ai/v1"
OUT = HERE / "out"
LEDGER = HERE / "spend-ledger.json"

# List prices checked 2026-11-22 on docs.api.pruna.ai (images: Replicate listing; treat as estimates).
PRICE = {
    "p-image": 0.01,             # per image (estimate, conservative)
    "p-image-edit": 0.01,        # per image
    "p-video-2-pro": {           # per second of returned video
        ("480p", "cost"): 0.01, ("480p", "speed"): 0.02, ("480p", "quality"): 0.04,
        ("768p", "cost"): 0.025, ("768p", "speed"): 0.035, ("768p", "quality"): 0.075,
    },
    "p-video-upscale": {"720p": 0.01, "1080p": 0.02, "2k": 0.04, "4k": 0.08},  # per second, <=30 fps
    "wan-i2v": {"480p": 0.05, "720p": 0.11},  # per video (Wan 2.2 A14B on Pruna), checked 2026-11-22
}
CLIP_SECONDS = 5  # p-video-2-pro minimum; we use 3-4 s of each


# ------------------------------------------------------------------ ledger
def ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"currency": "USD", "approved_limit": 0, "spent_estimate": 0, "requests": []}


def charge(model, est, note, dry):
    lg = ledger()
    if dry:
        ok = lg["spent_estimate"] + est <= lg["approved_limit"] + 1e-9
        print(f"[dry-run] {model} for {note}: ~${est:.3f}" + ("" if ok else "  (NOT within approved limit)"))
        return False
    if lg["spent_estimate"] + est > lg["approved_limit"] + 1e-9:
        sys.exit(f"STOP: {model} ({note}) would cost ~${est:.3f}; spent ~${lg['spent_estimate']:.3f} of the "
                 f"approved ${lg['approved_limit']:.2f}. Ask the owner before raising approved_limit in {LEDGER.name}.")
    lg["spent_estimate"] = round(lg["spent_estimate"] + est, 4)
    lg["requests"].append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model, "note": note, "estimate": est})
    LEDGER.write_text(json.dumps(lg, indent=2) + "\n")
    return True


# ------------------------------------------------------------------ HTTP
class ApiError(Exception):
    pass


def refund_last(reason):
    """Undo the last reservation when the submission never reached the model (not billed)."""
    lg = ledger()
    if lg["requests"]:
        r = lg["requests"].pop()
        lg["spent_estimate"] = round(lg["spent_estimate"] - r["estimate"], 4)
        lg.setdefault("rejected_not_billed", []).append({**r, "reason": reason})
        LEDGER.write_text(json.dumps(lg, indent=2, ensure_ascii=False) + "\n")


def _key():
    # With the proxy-injected network secret any placeholder works; it is replaced in transit.
    return os.environ.get("PRUNA_API_KEY", "injected-by-proxy")


def http(method, url, body=None, headers=None, raw=False, timeout=120):
    h = {"apikey": _key(), "User-Agent": "jibali-pipeline/1.0", **(headers or {})}
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} from {url}: {e.read()[:500]!r}")
    return data if raw else json.loads(data)


def upload(path):
    """POST /v1/files (multipart field 'content'); returns the file URL to pass as input."""
    b = uuid.uuid4().hex
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"content\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    r = http("POST", f"{API}/files", body, {"Content-Type": f"multipart/form-data; boundary={b}"}, timeout=600)
    return r.get("urls", {}).get("get") or f"{API}/files/{r['id']}"


def predict(model, inp, dest):
    """Submit, poll get_url until done, download generation_url to dest. One attempt only."""
    try:
        r = http("POST", f"{API}/predictions", json.dumps({"input": inp}).encode(),
                 {"Content-Type": "application/json", "Model": model})
    except ApiError as e:
        refund_last(str(e)[:200])
        sys.exit(f"Submission rejected, nothing generated (ledger refunded): {e}")
    try:
        return _finish(model, inp, dest, r)
    except ApiError as e:
        sys.exit(f"{model} was submitted but polling/download failed: {e}. Check the Pruna dashboard; "
                 "do not resubmit until you know whether it ran.")


def _finish(model, inp, dest, r):
    t0 = time.time()
    while r.get("status") not in ("succeeded", "failed", "canceled", "error"):
        if "get_url" not in r and "id" not in r:
            sys.exit(f"Unexpected response from {model}: {json.dumps(r)[:500]}")
        if time.time() - t0 > 1800:
            sys.exit(f"{model} still running after 30 min; check the dashboard before doing anything else.")
        time.sleep(5)
        url = r.get("get_url") or f"{API}/predictions/status/{r['id']}"
        r = {**r, **http("GET", url)}
    if r["status"] != "succeeded":
        sys.exit(f"{model} {r['status']}: {json.dumps(r)[:800]}")
    gen = r["generation_url"]
    if gen.startswith("/"):
        gen = "https://api.pruna.ai" + gen
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(http("GET", gen, raw=True, timeout=600))
    (dest.with_suffix(dest.suffix + ".json")).write_text(json.dumps({"model": model, "input": inp, "result": r}, indent=2))
    print(f"saved {dest.relative_to(HERE)}")
    return dest


# ------------------------------------------------------------------ stages
PLAN = json.loads((HERE / "shots.json").read_text())


def still_path(sid):
    hits = sorted((OUT / "stills").glob(f"{sid}.*"))
    hits = [h for h in hits if not h.name.endswith(".json")]
    return hits[0] if hits else None


def resolve_ref(ref, dry):
    if dry:
        return f"https://api.pruna.ai/v1/files/DRY-RUN({ref})"
    if ref.startswith("@"):
        p = still_path(ref[1:])
        if not p:
            sys.exit(f"Missing still {ref[1:]}: generate it first (stills {ref[1:]}).")
    else:
        p = HERE / ref
    return upload(p)


def run_stills(ids, dry):
    for s in PLAN["stills"]:
        if ids and s["id"] not in ids:
            continue
        if still_path(s["id"]) and not ids:
            print(f"skip {s['id']} (exists)")
            continue
        inp = dict(s["input"])
        inp["prompt"] = f"{inp['prompt']} {PLAN['style']}"
        if s["model"] == "p-image-edit":
            inp["images"] = [resolve_ref(r, dry) for r in s["refs"]]
            inp["turbo"] = False
        if charge(s["model"], PRICE[s["model"]], f"still {s['id']}", dry):
            predict(s["model"], inp, OUT / "stills" / f"{s['id']}.jpg")


def run_demo(ids, mode, res, dry):
    rate = PRICE["p-video-2-pro"][(res, mode)]
    for c in PLAN["clips"]:
        if ids and c["id"] not in ids:
            continue
        dest = OUT / f"clips-{res}" / f"{c['id']}.mp4"
        if dest.exists() and not ids:
            print(f"skip clip {c['id']} (exists)")
            continue
        inp = {"prompt": f"{c['prompt']} {PLAN['style']}", "image": resolve_ref(c["image"], dry),
               "duration": CLIP_SECONDS, "resolution": res, "mode": mode, "aspect_ratio": "9:16"}
        if charge("p-video-2-pro", rate * CLIP_SECONDS, f"clip {c['id']} {res} {mode}", dry):
            predict("p-video-2-pro", inp, dest)


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def run_cut(src_dir, tag):
    """Free, local: trim each clip, scale to 1080x1920, add real reveal + titles, mix audio."""
    work = OUT / f"cut-{tag}"
    shutil.rmtree(work, ignore_errors=True)
    (work / "audio" / "sfx").mkdir(parents=True)
    parts = []
    for c in PLAN["clips"]:
        src = src_dir / f"{c['id']}.mp4"
        if not src.exists():
            sys.exit(f"Missing {src.relative_to(HERE)}")
        n = int(c["use_seconds"] * 24)
        p = work / f"{c['id']}.mp4"
        ff("-i", str(src), "-vf", f"scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=24,trim=end_frame={n},setpts=N/24/TB",
           "-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(p))
        # the clip's own generated sound becomes that scene's effects layer
        has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                    "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
        if has_audio:
            ff("-i", str(src), "-t", str(c["use_seconds"]), "-vn", "-ac", "2", "-ar", "48000", str(work / "audio" / "sfx" / f"{c['id']}.wav"))
        parts.append(p)
    reveal = (HERE / PLAN["reveal"]["file"]).resolve()
    titles = work / "titles.ass"
    shutil.copy(REPO / "output/brand-film-45/closing-titles.ass", titles)
    captions = work / "captions.ass"
    shutil.copy(HERE / "arabic-captions.ass", captions)
    inputs = sum([["-i", str(p)] for p in parts + [reveal]], [])
    chain = "".join(f"[{i}:v]" for i in range(len(parts) + 1))
    silent = work / f"jibali-{tag}-silent.mp4"
    ff(*inputs, "-filter_complex", f"{chain}concat=n={len(parts) + 1}:v=1:a=0,settb=1/24,setpts=N,fps=24,subtitles={captions},subtitles={titles}[v]",
       "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-an", str(silent))
    # music + hoopoe call: reuse the project's bed and scene-01 call until AI music is generated
    for name in ("music/bed.wav", "voice/tagline.wav"):
        s = REPO / "audio" / name
        if s.exists():
            (work / "audio" / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(s, work / "audio" / name)
    final = OUT / f"jibali-{tag}.mp4"
    env = {**os.environ, "AUDIO_DIR": str(work / "audio"), "MUSIC_DB": "-6", "SFX_DB": "0"}
    subprocess.run([str(REPO / "scripts/mix-audio.sh"), str(silent), str(final)], check=True, env=env)
    print(f"final: {final.relative_to(HERE)}")


def run_upscale(dry):
    """Upscale only the 17 s AI part, sent at its native 480p size, so we pay for 17 s, not 20."""
    clips = OUT / "clips-480p"
    work = OUT / "upscaled"; work.mkdir(parents=True, exist_ok=True)
    trimmed = []
    for c in PLAN["clips"]:
        src = clips / f"{c['id']}.mp4"
        if not src.exists():
            sys.exit(f"Missing {src.relative_to(HERE)}: run `demo` first.")
        t = work / f"src-{c['id']}.mp4"
        ff("-i", str(src), "-vf", f"fps=24,trim=end_frame={int(c['use_seconds'] * 24)},setpts=N/24/TB", "-an",
           "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(t))
        trimmed.append(t)
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{t}'\n" for t in trimmed))
    src = work / "ai-0-17s-480p.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(src))
    secs = 17
    if charge("p-video-upscale", PRICE["p-video-upscale"]["1080p"] * secs, "upscale 0-17 s to 1080p", dry):
        up = predict("p-video-upscale", {"video": upload(src), "target": "1080p"}, work / "ai-0-17s-1080p.mp4")
        # split back into per-scene clips, keeping each clip's generated sound
        d = OUT / "clips-1080p-up"; d.mkdir(parents=True, exist_ok=True)
        for c in PLAN["clips"]:
            ff("-ss", str(c["start"]), "-t", str(c["use_seconds"]), "-i", str(up), "-i", str(clips / f"{c['id']}.mp4"),
               "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac",
               "-shortest", str(d / f"{c['id']}.mp4"))
        run_cut(d, "1080p")


def estimate(mode, res):
    n_stills = len(PLAN["stills"])
    stills = sum(PRICE[s["model"]] for s in PLAN["stills"])
    clip = PRICE["p-video-2-pro"][(res, mode)] * CLIP_SECONDS
    demo = clip * len(PLAN["clips"])
    up = PRICE["p-video-upscale"]["1080p"] * 17
    print(f"Stills  {n_stills} x ~$0.01            ${stills:.2f}")
    print(f"Clips   {len(PLAN['clips'])} x {CLIP_SECONDS}s {res} {mode} @ ${PRICE['p-video-2-pro'][(res, mode)]}/s  ${demo:.2f}")
    print(f"Upscale 17 s to 1080p @ $0.02/s     ${up:.2f}")
    print(f"One pass total                      ${stills + demo + up:.2f}")
    print(f"With retries (2x clips, 3x stills)  ${stills * 3 + demo * 2 + up:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["estimate", "stills", "demo", "cut", "upscale"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--mode", default="speed", choices=["cost", "speed", "quality"])
    ap.add_argument("--resolution", default="480p", choices=["480p", "768p"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "estimate":
        estimate(a.mode, a.resolution)
    elif a.cmd == "stills":
        run_stills(a.ids, a.dry_run)
    elif a.cmd == "demo":
        run_demo(a.ids, a.mode, a.resolution, a.dry_run)
    elif a.cmd == "cut":
        run_cut(OUT / f"clips-{a.resolution}", a.resolution)
    elif a.cmd == "upscale":
        run_upscale(a.dry_run)


if __name__ == "__main__":
    main()
