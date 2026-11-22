#!/usr/bin/env python3
"""Jibali v2: extreme realism from the owner's reference images (refs/v2/).

The owner's ten-panel storyboard sets the look. Each panel becomes a vertical 9:16
keyframe (p-image-edit: keep the photo, only remove captions/labels and extend the
frame), then p-video-2-pro adds restrained, physically real motion. The hoopoe reuses
the approved flight clip; the ending uses the REAL package photo.

Spending goes through the same ledger and guard as scripts/pruna.py.

  python3 scripts/v2.py keyframes [ID ...]
  python3 scripts/v2.py clips [ID ...]
  add --dry-run to preview
"""
import argparse
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pruna", HERE / "scripts/pruna.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

OUT = HERE / "out" / "v2"
REAL = ("Real documentary footage shot on a cinema camera, natural real-time motion, realistic physics, "
        "every object keeps its exact shape and size, no morphing, no warping, no new objects, no text.")
KEEP = ("Image 1 is a real photograph. Recreate it as a tall vertical 9:16 photograph of the SAME scene: keep the subject, "
        "composition, lighting, colours, textures and every detail exactly as in image 1, and extend the scene naturally "
        "above and below. Remove all overlaid text, Arabic captions, time labels, frames and borders. Natural camera "
        "photograph, photoreal, no stylisation, no added objects, no text.")

SHOTS = [
    # id, reference panel, extra keyframe note, motion, mode
    ("hermon", "hermon.jpg", "The mountain is Mount Hermon (Jabal al-Sheikh) at sunrise.",
     "The sun rises slowly behind the snowy ridge of Mount Hermon, low clouds drift gently through the valley, very slow aerial push-in.", "speed"),
    ("wheat", "wheat.jpg", "",
     "Ripe wheat ears sway gently in a light mountain breeze, awns catch the backlight, shallow depth of field, very slow push-in.", "speed"),
    ("grain", "grain-millstone.jpg", "",
     "Slow-motion: whole-wheat kernels keep pouring steadily from the wooden bowl onto the millstone and bounce naturally; the hand holds the bowl still.", "quality"),
    ("saltwater", "salt-water.jpg", "",
     "A pinch of coarse salt falls from the fingertips into the flour while a thin clear stream of water pours from the jug into the bowl; steady camera.", "speed"),
    ("knead", "kneading.jpg", "Hands have natural anatomy with five fingers each.",
     "The two hands slowly press the dough down with the heels of the palms and fold it once, a little flour dust rises; natural hand anatomy, slow real-time movement, steady camera.", "quality"),
    ("fire", "saj-fire.jpg", "The dark metal at the top is the curved underside of a traditional Lebanese saj: a convex steel dome like an upside-down wok, resting on stones over an open wood fire of burning logs; there is no stove, no box, no chimney and no pipe.",
     "The wood fire under the dark saj dome flickers and crackles, small sparks rise, thin wisps of smoke drift; the camera stays still.", "speed"),
    ("sajbread", "saj-bread.jpg", "The bread is a very thin Lebanese saj on the convex saj dome.",
     "Macro: the very thin bread on the hot saj dome gently puffs, small bubbles rise and turn golden, faint steam drifts up, very slow push-in.", "speed"),
    ("stack", "bread-stack.jpg", "",
     "Soft steam rises from the warm stack of freshly baked thin saj bread on the linen cloth, very slow push-in, warm light.", "speed"),
]


def keyframes(ids, dry):
    for sid, ref, note, _, _ in SHOTS:
        if ids and sid not in ids:
            continue
        dest = OUT / "keyframes" / f"{sid}.jpg"
        if dest.exists() and not ids:
            print(f"skip {sid} (exists)"); continue
        inp = {"prompt": f"{KEEP} {note}".strip(), "images": [P.resolve_ref(f"refs/v2/{ref}", dry)],
               "aspect_ratio": "9:16", "turbo": False}
        if P.charge("p-image-edit", P.PRICE["p-image-edit"], f"v2 keyframe {sid}", dry):
            P.predict("p-image-edit", inp, dest)


def clips(ids, dry):
    for sid, _, _, motion, mode in SHOTS:
        if ids and sid not in ids:
            continue
        dest = OUT / "clips-480p" / f"{sid}.mp4"
        if dest.exists() and not ids:
            print(f"skip {sid} (exists)"); continue
        kf = OUT / "keyframes" / f"{sid}.jpg"
        if not kf.exists() and not dry:
            sys.exit(f"missing keyframe {kf.name}")
        inp = {"prompt": f"{motion} {REAL}", "image": "DRY" if dry else P.upload(kf),
               "duration": 5, "resolution": "480p", "mode": mode, "aspect_ratio": "9:16"}
        rate = P.PRICE["p-video-2-pro"][("480p", mode)]
        if P.charge("p-video-2-pro", rate * 5, f"v2 clip {sid} 480p {mode}", dry):
            P.predict("p-video-2-pro", inp, dest)


NATURAL = ("Keep this exact scene, composition and subject, but make it look like an authentic, unedited smartphone photo "
           "taken in a real Lebanese village bakery: natural uneven daylight from a doorway, true-to-life colours, slight sensor "
           "noise, real imperfect textures, a little flour dust and wear, nothing glossy, polished or perfect, no cinematic "
           "colour grade, no shallow-depth-of-field glamour. Photoreal. No text.")
WAN_MOTION = {
    "sajbread": "Handheld phone video, real time: the very thin bread on the hot saj dome gently puffs and small bubbles rise and brown, faint steam drifts up. Nothing changes shape unnaturally.",
    "stack": "Handheld phone video, real time: faint steam rises from the warm stack of thin saj bread on the cloth, the camera moves very slightly. Nothing changes shape.",
}


def natural(ids, dry):
    for sid in ids:
        dest = OUT / "natural" / f"{sid}.jpg"
        inp = {"prompt": NATURAL, "images": [P.resolve_ref(f"out/v2/keyframes/{sid}.jpg", dry)], "aspect_ratio": "9:16", "turbo": False}
        if P.charge("p-image-edit", P.PRICE["p-image-edit"], f"v2 natural keyframe {sid}", dry):
            P.predict("p-image-edit", inp, dest)


def wan(ids, dry, res="480p"):
    for sid in ids:
        kf = OUT / "natural" / f"{sid}.jpg"
        dest = OUT / f"wan-{res}" / f"{sid}.mp4"
        inp = {"prompt": WAN_MOTION[sid], "image": "DRY" if dry else P.upload(kf), "num_frames": 81, "resolution": res,
               "frames_per_second": 16, "interpolate_output": True, "go_fast": False}
        if P.charge("wan-i2v", P.PRICE["wan-i2v"][res], f"wan 2.2 clip {sid} {res}", dry):
            P.predict("wan-i2v", inp, dest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["keyframes", "clips", "natural", "wan"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"keyframes": keyframes, "clips": clips, "natural": natural, "wan": wan}[a.cmd](a.ids, a.dry_run)
