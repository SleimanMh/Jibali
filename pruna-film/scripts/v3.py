#!/usr/bin/env python3
"""Jibali v3: the owner's scene frames (refs/v3, from the ChatGPT session) animated with
p-video-2-pro using first + last frame, following the owner's PRUNA MOTION SCRIPT.

Settings per job (owner's script, resolution set to 480p by the owner): duration 5 s,
mode quality, prompt_upsampler off; the vertical input frames set the canvas.
Spending goes through spend-ledger.json and its guard; no automatic retries.

  python3 scripts/v3.py 09            # one job
  python3 scripts/v3.py 02 03 --dry-run
"""
import argparse
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pruna", HERE / "scripts/pruna.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

REFS = HERE / "refs" / "v3"
OUT = HERE / "out" / "v3"
RES, MODE = "480p", "quality"

JOBS = {
    "02": ("02-Hoopoe", "01.jpg", "04.jpg",
           "A Eurasian hoopoe already in flight crosses left to right over Rashaya. Its head stays steady as its barred wings sweep down and recover in a natural, gently undulating flight. Keep the bird prominent until it exits through the right edge. As the last wingtip clears, settle focus on the bent golden wheat ear in the foreground. End on the supplied view of wheat with the bird fully out of frame. The roofs and mountain ridge stay fixed."),
    "03": ("03-Wheat", "01.jpg", "04.jpg",
           "Begin on the bent wheat ear. An older baker's right hand in a charcoal cuff enters from the lower left. Two fingertips brush the ripe head once toward the right. The stalk bends at contact and begins to spring back as the fingers pass. Keep the terrace and distant ridge steady in the same daylight."),
    "04": ("04-Mill", "01.jpg", "04.jpg",
           "Fixed overhead view of the horizontal millstones. The baker rotates her wrist to tip the copper scoop. A narrow stream of individual wheat kernels falls directly into the center hole and tapers as the scoop empties. Keep the scoop, stone rim and opening the same size and shape throughout."),
    "05": ("05-Water", "01.jpg", "04.jpg",
           "In the supplied window light, the baker tilts the clay jug. A thin stream of clear water falls into the well in the fine whole-wheat flour. A shallow pool forms; the flour darkens only where the water touches it. The surrounding powder stays loose and dry. The stream narrows to one last drop. Hold the same bowl, worktable, camera angle and chest-down crop."),
    "06": ("06-Kneading", "01.jpg", "04.jpg",
           "In the same bowl on the same table, one hand steadies a single soft mass of hydrated dough. The other lifts its near edge into a smooth elastic fold. She folds it inward, presses once with the heel of her palm, then releases. A shallow crease remains. Keep her hands, charcoal cuffs and the direction of the window light consistent. Frame her from the chest down."),
    "07": ("07-Kara", "01.jpg", "04.jpg",
           "The baker supports a thin beige dough sheet across both hands above the rounded ivory kara cushion. She lowers it until its center touches the taut cotton, then slides her hands outward. The soft edges settle over the curve under their own weight. The cushion stays firm, its seam stays fixed, and the dough moves independently. Keep the camera on her naturally connected forearms, dough and worktable."),
    "08": ("08-Fire", "01.jpg", "04.jpg",
           "Locked low view beneath the convex steel saj. Several yellow-orange flames rise from the edges of three charred logs and fill the opening below the dome. The flame tips briefly join, divide and curl around the wood; the embers brighten underneath. The logs, supports and steel stay still. Preserve the natural daylight exposure."),
    "09": ("09-Saj", "01.jpg", "04.jpg",
           "One whole, very thin Lebanese saj loaf covers the convex steel. The baker loosens the near edge and uses both hands to peel the entire loaf away in one continuous lift. The exposed steel grows from a narrow strip to half the dome. The last edge releases. The intact full-size loaf sags broadly between her hands. Finish with visible air beneath its lowest edge and the entire empty dome below. Hold that final pose. Camera stays fixed."),
    "10A": ("10-Bread-at-home", "01.jpg", "03.jpg",
            "The folded stack rests on the striped cloth. The baker's hand enters, pinches the near corner of the top full-size folded saj and gently lifts it. The rest of that same sheet is still visibly draped across the stack. Everything below the top sheet stays in place."),
    "10B": ("10-Bread-at-home", "03.jpg", "04.jpg",
            "Continue from the raised corner. In one smooth motion the hand carries the entire top folded loaf upward and out of frame. Its far edge follows the gripped corner at full size. Finish on the remaining flat stack alone, in exactly the final reference composition. Keep the camera fixed."),
    "11": ("11-Packing-JIBALI", "01.jpg", "04.jpg",
           "Chest-down view of the same baker. One hand steadies the upright clear JIBALI sleeve while the other guides the aligned stack of folded bread farther inside. The exposed bread above the opening gets progressively shorter. Once it is fully inside, both hands press the top seam together. Keep the green-and-gold label facing the camera, flat, readable and clear of fingers. The bread stays full-size. Hold the packed sleeve at the end."),
}


def run(ids, dry):
    rate = P.PRICE["p-video-2-pro"][(RES, MODE)]
    for jid in ids:
        folder, first, last, prompt = JOBS[jid]
        dest = OUT / f"clips-{RES}" / f"{jid}.mp4"
        inp = {"prompt": prompt, "duration": 5, "resolution": RES, "mode": MODE, "prompt_upsampler": "off",
               "image": "DRY" if dry else P.upload(REFS / folder / first),
               "last_frame_image": "DRY" if dry else P.upload(REFS / folder / last)}
        if P.charge("p-video-2-pro", rate * 5, f"v3 job {jid} ({folder} {first}->{last}) {RES} {MODE}", dry):
            P.predict("p-video-2-pro", inp, dest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+", choices=sorted(JOBS))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.ids, a.dry_run)
