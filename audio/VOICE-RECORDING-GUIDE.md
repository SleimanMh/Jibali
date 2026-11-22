# Jibali voice tagline: recording guide

Recording this costs nothing and takes about ten minutes. A real Lebanese voice
will sound far more authentic than AI text-to-speech.

## The line

> **جبالي… من قلب الجبل، لقلب البيت.**
>
> *Jibāli … min ʔalb ij-jabal, la-ʔalb il-bēt.*

- Say it in Lebanese dialect: **ق is a glottal stop** ("ʔalb", not "qalb").
- Pause briefly (about a third of a second) after **جبالي**.
- The words must match the on-screen title exactly. Don't add or change words.

## Timing

The voice plays over the product reveal, from **17.2 s** to no later than
**19.8 s**. The whole line should take **2.2–2.6 seconds**. Say it calmly, but
don't drag it out. Time a few takes on a stopwatch.

## Delivery

Warm, close and unhurried, like a grandparent telling you where the bread comes
from. Use a mid-to-low voice. It should sound like a storyteller, not a radio
announcer: no "advert" energy.

## How to record on a phone

1. Pick a **small, soft room**: a bedroom with curtains, a closet full of
   clothes, or sit in a parked car. Avoid kitchens and tiled rooms because
   they echo.
2. Turn off fans, the AC and the fridge if you can. Put the phone on silent
   and airplane mode.
3. Use the phone's built-in voice recorder, set to the highest quality or
   lossless setting if it has one.
4. Hold the phone **about 20 cm (a hand-span) from your mouth**, slightly to
   the side so your breath doesn't hit the microphone.
5. Record **2 seconds of silence first**, then **5–6 takes** of the line with a
   pause between each one. Try a few small variations (a bit slower, softer,
   warmer).
6. Send the file as a **document or file**, not a WhatsApp voice note, because
   voice notes are heavily compressed.

## Then

Save the chosen take as `audio/voice/tagline.wav`. The mixing script
(`scripts/mix-audio.sh`) trims the silence, positions it at 17.2 s and lowers
the music under it automatically. Any format works: if you have an `.m4a` or
`.mp3`, convert it with:

```bash
ffmpeg -i take.m4a -ac 1 -ar 48000 audio/voice/tagline.wav
```
