# Jibali × Pruna: cinematic version

This is a separate project from the original handover in `../output/brand-film-45`. It makes the
20-second vertical film with Pruna's photoreal models. It reuses the finished real-product reveal
(scene 06) and the Arabic closing titles from the main project.

## Pipeline

1. **Stills (keyframes).** Six images, 9:16.
   - `p-image` for new scenes.
   - `p-image-edit` when a reference must be kept: the Rashaya and Hermon photo, the real saj
     stack, and a hoopoe "character" still so the same bird appears in scenes 1 and 2.
2. **Demo at 480p.** `p-video-2-pro` (built on MiniMax) animates each still. It makes one 5 s clip
   per scene, in vertical 9:16, and **generates natural sound** with each clip.
3. **Cut (free, local).** Trim to the timeline, add the real package reveal and closing titles,
   then mix music with each clip's own sound at -14 LUFS.
4. **HD.** `p-video-upscale` takes the 17 s AI part from 480p to 1080p, then the film is re-cut.
   For more detail, the approved shots can instead be regenerated at 768p and upscaled.
5. **Later.** Add the Arabic voice tagline (`../audio/VOICE-RECORDING-GUIDE.md`) and
   AI-generated music.

| Time | Scene |
|---|---|
| 0–4 s | Hoopoe (hudhud, هدهد) flies over Rashaya and Mount Hermon at sunrise |
| 4–7 s | It lands on a limestone rock in golden wheat, folds its wings, raises its crest |
| 7–10 s | Stone mill: kernels in, whole-wheat flour out |
| 10–13 s | Water and salt into the flour, hands kneading |
| 13–17 s | Very thin saj baking on the dome over a small wood fire |
| 17–20 s | The **real** Jibali package and the closing titles |

All prompts are in [`shots.json`](shots.json).

## Cost

Pruna list prices, checked 2026-11-22 on docs.api.pruna.ai. Image prices are estimates.

| Step | Calculation | Cost |
|---|---|---|
| 6 stills | ~$0.01 each | $0.06 |
| 5 demo clips, 480p, `speed` | 5 s × $0.02/s each | $0.50 |
| Upscale 17 s to 1080p | $0.02/s | $0.34 |
| **One pass** | | **$0.90** |
| **With retries** (2× clips, 3× stills) | | **~$1.50** |
| Same with `--mode quality` (better motion) | | ~$1.40 one pass, ~$2.50 with retries |
| Best HD: regenerate at 768p `quality` + 1080p upscale | $0.095/s × 25 s | +$2.40 |

`python3 scripts/pruna.py estimate [--mode quality]` prints the current estimate.

## Running it (from `pruna-film/`)

```bash
python3 scripts/pruna.py stills            # out/stills/
python3 scripts/pruna.py demo              # out/clips-480p/   (add --mode quality for better motion)
python3 scripts/pruna.py cut               # out/jibali-480p.mp4  (free)
python3 scripts/pruna.py upscale           # out/jibali-1080p.mp4
```

Add `--dry-run` to preview any step without calling the API. Pass shot ids to redo one shot,
e.g. `demo 02`.

**Spending guard:** every paid call is checked against `spend-ledger.json`. Nothing runs until
`approved_limit` covers the call. Raise it only with the owner's approval. There are no automatic
retries.

**API key:** this uses Pruna's own API, `api.pruna.ai`. The key is sent in the `apikey` header.
In the cloud session it is stored as a network secret for `api.pruna.ai`. Locally, set
`PRUNA_API_KEY`.

## Notes

- The package label is never AI-generated. Scene 06 is the real photo.
- p-video-2-pro clips are at least 5 s, so each clip is billed for 5 s even though only 3–4 s is
  used.
- The music bed is the synthesized oud track from `../audio/music/bed.wav` until an AI music
  track is generated.
- The hoopoe call comes from the clip's generated sound if it is convincing; otherwise it is
  layered in. Use only commercially cleared or generated audio, never non-commercial
  recordings.
