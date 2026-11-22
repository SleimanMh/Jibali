#!/usr/bin/env python3
"""Jibali soundtrack, synthesized in code (free; no samples, so no licensing issues).

Writes (48 kHz, stereo, 16-bit):
  audio/music/bed.wav     21 s: plucked oud-like melody in maqam Bayati on D
                          (with the quarter-tone E), soft ney-like drone, light
                          frame drum from the mill scene, resolving at 17 s.
  audio/sfx/01.wav  4 s   mountain wind, passing wingbeats, synthesized hoopoe call
  audio/sfx/02.wav  3 s   wheat rustle, approaching wings, landing tap, wing fold
  audio/sfx/03.wav  3 s   stone-mill rumble and grit, grain trickle, flour hiss
  audio/sfx/04.wav  3 s   salt sprinkle, water pour, kneading presses
  audio/sfx/05.wav  4 s   wood-fire crackle and roar, saj sizzle
Timings follow motion/jibali-motion.html and output/brand-film-45/audio-timeline.csv.

Usage: python3 scripts/synth-audio.py [AUDIO_DIR]   (default: audio/)
"""
import pathlib
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(2026)
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "audio"


# ---------------------------------------------------------------- helpers
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "lowpass", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x)


def noise(n):
    return RNG.standard_normal(n)


def brown(n):
    b = np.cumsum(noise(n))
    return hp(b - b.mean(), 20)


def pink(n):
    w = noise(n)
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, w)


def smooth_env(n, rate, depth=0.6, seed=0):
    """Slowly wandering 0..1 envelope (gusts)."""
    r = np.random.default_rng(seed)
    pts = r.random(int(n / SR * rate) + 3)
    e = np.interp(np.arange(n), np.linspace(0, n, len(pts)), pts)
    e = lp(e, rate * 2, 1)
    return 1 - depth + depth * e


def rms_to(x, dbfs):
    r = np.sqrt(np.mean(x ** 2)) + 1e-12
    return x * (10 ** (dbfs / 20) / r)


def place(buf, x, start_s, gain=1.0):
    i = int(start_s * SR)
    if i >= len(buf):
        return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n] * gain


def fades(x, fin=0.01, fout=0.05):
    n = len(x)
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def reverb(x, secs=1.1, wet=0.22, bright=5000):
    ir = noise(int(secs * SR)) * np.exp(-np.linspace(0, 7, int(secs * SR)))
    ir = lp(ir, bright)
    ir /= np.sqrt(np.sum(ir ** 2))
    return x * (1 - wet) + signal.fftconvolve(x, ir)[:len(x)] * wet


def stereo(l, r=None, width=0.0):
    if r is None:
        r = l
    m, s = (l + r) / 2, (l - r) / 2
    return np.stack([m + s * (1 + width), m - s * (1 + width)], axis=1)


def write(path, st):
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(st))
    if peak > 0.98:
        st = st * (0.98 / peak)
    pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  {len(st) / SR:.2f}s")


# ---------------------------------------------------------------- music
D3 = 146.83
BAYATI = {  # maqam Bayati on D; E is a quarter-tone flat
    "D2": D3 / 2, "A2": 110.0, "D3": D3, "Eq3": D3 * 2 ** (1.5 / 12), "F3": 174.61, "G3": 196.00,
    "A3": 220.00, "Bb3": 233.08, "C4": 261.63, "D4": 293.66, "Eq4": D3 * 2 * 2 ** (1.5 / 12), "F4": 349.23,
}


def oud(freq, dur=2.2, vel=1.0):
    """Karplus-Strong pluck with a plectrum-like excitation and a warm body."""
    n = int(dur * SR)
    # Two-tap averaging loop filter adds half a sample of delay.
    Ni = max(2, int(round(SR / freq - 0.5)))
    exc = np.zeros(n)
    burst = lp(noise(Ni), 2500 + 2000 * vel) * np.hanning(Ni) ** 0.5
    exc[:Ni] = burst
    g = 0.996
    a = np.zeros(Ni + 2)
    a[0], a[Ni], a[Ni + 1] = 1, -g / 2, -g / 2
    y = signal.lfilter([1], a, exc)
    y = lp(y, 3200) + 0.25 * bp(y, 180, 420)  # wooden body warmth
    y *= np.exp(-np.linspace(0, 3.2, n))
    return fades(y / (np.max(np.abs(y)) + 1e-9) * vel, 0.002, 0.15)


def ney(freq, dur, breath=0.35):
    t = t_axis(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 4.6 * t) * np.clip(t / 1.5, 0, 1)
    ph = 2 * np.pi * np.cumsum(freq * vib) / SR
    tone = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph)
    air = bp(noise(len(t)), freq * 0.8, freq * 3.2) * breath
    return tone + air * 3


def dum():
    t = t_axis(0.5)
    f = 58 + 40 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    return x + lp(noise(len(t)), 400) * np.exp(-t * 40) * 0.3


def tak():
    t = t_axis(0.12)
    return bp(noise(len(t)), 1800, 5200) * np.exp(-t * 55) * 0.8 + np.sin(2 * np.pi * 420 * t) * np.exp(-t * 60) * 0.3


def music():
    dur = 21.0
    n = int(dur * SR)
    L, R = np.zeros(n), np.zeros(n)
    # ney-like drone on D with a soft fifth
    drone = ney(BAYATI["D3"], dur, 0.25) * 0.55 + ney(BAYATI["A3"], dur, 0.15) * 0.18
    drone *= smooth_env(n, 0.6, 0.35, 3)
    env = np.clip(t_axis(dur) / 2.0, 0, 1) ** 1.5
    env *= np.where(t_axis(dur) > 17.0, 1.25, 1.0)  # slight bloom on the resolution
    drone = lp(drone, 1800) * env
    L += drone * 0.11; R += drone * 0.11
    # oud melody (time, note, velocity)
    melody = [
        (0.8, "D3", .8), (1.7, "A3", .75), (2.4, "G3", .6), (2.8, "F3", .6), (3.2, "Eq3", .65), (3.7, "D3", .8),
        (4.3, "F3", .65), (4.75, "G3", .65), (5.2, "A3", .75), (5.9, "Bb3", .7), (6.3, "A3", .65), (6.8, "G3", .7),
        (7.2, "A3", .8), (7.65, "A3", .55), (8.1, "G3", .65), (8.55, "F3", .6), (9.0, "G3", .7), (9.45, "A3", .75),
        (9.9, "D4", .8), (10.35, "C4", .65), (10.8, "Bb3", .65), (11.25, "A3", .7), (11.7, "G3", .65), (12.15, "A3", .7),
        (12.6, "Bb3", .7), (13.05, "C4", .75), (13.5, "D4", .85), (13.95, "D4", .6), (14.4, "C4", .7), (14.85, "Bb3", .7),
        (15.3, "A3", .75), (15.75, "G3", .7), (16.2, "F3", .7), (16.6, "Eq3", .75),
        (17.0, "D3", .9), (17.03, "A3", .7), (17.06, "D4", .75),  # final strum
        (18.3, "D4", .35), (18.75, "A3", .3),  # quiet echo under the voice
    ]
    for i, (st, nt, v) in enumerate(melody):
        ring = 3.0 if st >= 17 else 1.8
        x = oud(BAYATI[nt], ring, v)
        pan = 0.08 * np.sin(i * 1.7)
        place(L, x, st, 0.5 - pan); place(R, x, st, 0.5 + pan)
    # bass plucks on the downbeats of the drum section
    for st in np.arange(7.2, 16.7, 1.8):
        x = oud(BAYATI["D2"], 1.6, 0.6)
        place(L, x, st, 0.3); place(R, x, st, 0.3)
    # light frame drum, baladi-like: D D . t D . t .  (eighth = 0.225 s)
    pat = ["D", "D", "", "t", "D", "", "t", ""]
    k = 0
    for st in np.arange(7.2, 16.95, 0.225):
        hit = pat[k % 8]; k += 1
        if not hit:
            continue
        grow = 0.55 + 0.45 * np.clip((st - 7.2) / 6, 0, 1)
        if hit == "D":
            x = dum() * 0.55 * grow
            place(L, x, st); place(R, x, st)
        else:
            x = tak() * 0.22 * grow
            place(L, x, st, 0.7); place(R, x, st, 1.0)
    st = stereo(reverb(L, 1.3, 0.25), reverb(R, 1.25, 0.25), 0.2)
    st *= np.clip((dur - t_axis(dur)) / 1.5, 0, 1)[:, None]  # tail fade (mix script also fades)
    return rms_to(st, -21)


# ---------------------------------------------------------------- sound effects
def wingbeats(dur, rate, amp_env, seed):
    t = t_axis(dur)
    phase = (t * rate) % 1
    pulse = np.exp(-((phase - 0.3) / 0.08) ** 2)
    whoosh = bp(noise(len(t)), 250, 1600) * pulse
    return whoosh * amp_env


def hoopoe_call():
    """'oop-oop-oop': three soft, hollow hoots with a slight downward glide."""
    out = np.zeros(int(1.2 * SR))
    for k in range(3):
        t = t_axis(0.16)
        f = 520 - 50 * t / 0.16
        ph = 2 * np.pi * np.cumsum(f) / SR
        env = np.sin(np.pi * np.clip(t / 0.16, 0, 1)) ** 1.6
        hoot = (np.sin(ph) + 0.12 * np.sin(2 * ph)) * env
        place(out, hoot, k * 0.3)
    return lp(reverb(out, 1.6, 0.35, 3000), 2500)


def sfx01():
    dur = 4.0; n = int(dur * SR); t = t_axis(dur)
    wl = lp(pink(n), 700) * smooth_env(n, 0.8, 0.7, 11)
    wr = lp(pink(n), 700) * smooth_env(n, 0.8, 0.7, 12)
    whistle = bp(noise(n), 900, 1300) * smooth_env(n, 1.2, 0.9, 13) * 0.25
    L = rms_to(wl + whistle, -31); R = rms_to(wr + whistle, -31)
    # bird passes left to right ~1.0-3.3 s
    pass_env = np.exp(-((t - 2.0) / 0.75) ** 2) * 0.05
    wb = wingbeats(dur, 3.2, pass_env, 1)
    pan = np.clip((t - 0.5) / 3, 0, 1)
    L += wb * (1 - pan); R += wb * pan
    call = hoopoe_call() * 0.035
    place(L, call, 1.75, 0.7); place(R, call, 1.75, 0.9)
    return stereo(L, R)


def rustle(n, seed, level):
    x = hp(noise(n), 2200) * smooth_env(n, 1.4, 0.8, seed)
    crackle = (RNG.random(n) < 0.004) * noise(n) * 0.6
    return rms_to(lp(x + hp(crackle, 3000), 9000), level)


def sfx02():
    dur = 3.0; n = int(dur * SR); t = t_axis(dur)
    L, R = rustle(n, 21, -33), rustle(n, 22, -33)
    land = 1.55
    app = np.clip(t / land, 0, 1) ** 2 * (t < land) * 0.07
    rate = 3 + 1.5 * np.clip(t / land, 0, 1)
    phase = np.cumsum(rate) / SR % 1
    wb = bp(noise(n), 250, 1800) * np.exp(-((phase - 0.3) / 0.09) ** 2) * app
    L += wb * 0.9; R += wb * 0.7
    tt = t_axis(0.08)
    tap = bp(noise(len(tt)), 1200, 3500) * np.exp(-tt * 90) * 0.06 + np.sin(2 * np.pi * 900 * tt) * np.exp(-tt * 120) * 0.03
    place(L, tap, land); place(R, tap, land, 0.8)
    fold = bp(noise(int(0.45 * SR)), 1500, 6000) * np.hanning(int(0.45 * SR)) * 0.02
    place(L, fold, land + 0.05); place(R, fold, land + 0.05)
    return stereo(L, R)


def sfx03():
    dur = 3.0; n = int(dur * SR); t = t_axis(dur)
    rot = 1 + 0.25 * np.sin(2 * np.pi * t / 5.5 * 2) + 0.15 * np.sin(2 * np.pi * 7 * t)
    rumble = lp(brown(n), 180) * rot
    grit = bp(noise(n), 300, 1100) * smooth_env(n, 18, 0.9, 31) * 0.5
    base = rms_to(rumble, -29) + rms_to(grit, -36)
    trickle = np.zeros(n)
    for s in RNG.random(int(55 * dur)) * dur:
        c = bp(noise(int(0.006 * SR)), 3000, 7000) * np.hanning(int(0.006 * SR))
        place(trickle, c, s, 0.02 + 0.02 * RNG.random())
    hiss = rms_to(hp(noise(n), 5000) * smooth_env(n, 3, 0.5, 33), -44)
    L = base + trickle * 0.9 + hiss
    R = base * 0.95 + np.roll(trickle, 300) * 0.7 + rms_to(hp(noise(n), 5000), -45)
    return stereo(L, R, 0.1)


def sfx04():
    dur = 3.0; n = int(dur * SR)
    L, R = np.zeros(n), np.zeros(n)
    # salt sprinkle 0-0.75 s: tiny bright crystal ticks landing in flour
    for s in RNG.random(80) * 0.65 + 0.08:
        c = bp(noise(int(0.004 * SR)), 4000, 11000) * np.hanning(int(0.004 * SR))
        g = 0.03 + 0.03 * RNG.random()
        place(L, c, s, g); place(R, c, s + 0.0005, g * 0.8)
    # water pour 0.75-1.5 s: filtered stream + small bubbles
    m = int(0.8 * SR)
    stream = bp(noise(m), 500, 2800) * smooth_env(m, 25, 0.6, 41)
    stream = rms_to(stream, -30) * np.clip(np.linspace(0, 6, m), 0, 1) * np.clip(np.linspace(6, 0, m), 0, 1)
    place(L, stream, 0.75); place(R, stream, 0.75, 0.9)
    for s in RNG.random(60) * 0.7 + 0.78:
        bt = t_axis(0.02 + 0.02 * RNG.random())
        f0 = 500 + 900 * RNG.random()
        b = np.sin(2 * np.pi * np.cumsum(f0 * (1 + bt * 25)) / SR) * np.exp(-bt * 120)
        place(L, b, s, 0.012); place(R, b, s + 0.001, 0.01)
    # kneading 1.5-3.0 s: soft thuds and squish on each press (presses peak at (k+0.5)/2.4 s)
    for k in range(4):
        s = 1.5 + (k + 0.5) / 2.4 - 0.08
        tt = t_axis(0.25)
        thud = np.sin(2 * np.pi * (85 + 40 * np.exp(-tt * 40)) * tt) * np.exp(-tt * 22) * 0.06
        squish = bp(noise(len(tt)), 250, 1400) * np.sin(np.pi * np.clip(tt / 0.25, 0, 1)) * 0.02
        side = 0.8 if k % 2 else 1.0
        place(L, thud + squish, s, side); place(R, thud + squish, s, 1.8 - side)
    return stereo(reverb(L, 0.5, 0.15), reverb(R, 0.5, 0.15))


def sfx05():
    dur = 4.0; n = int(dur * SR); t = t_axis(dur)
    roar = rms_to(lp(brown(n), 320) * smooth_env(n, 2.5, 0.4, 51), -31)
    L, R = roar.copy(), roar * 0.95
    for s in RNG.random(int(14 * dur)) * dur:
        ln = int((0.003 + 0.01 * RNG.random()) * SR)
        pop = hp(noise(ln), 800) * np.exp(-np.linspace(0, 6, ln))
        g = 0.02 + 0.05 * RNG.random() ** 2
        pan = RNG.random()
        place(L, pop, s, g * (1 - pan * 0.6)); place(R, pop, s, g * (0.4 + pan * 0.6))
    sizzle = hp(noise(n), 4500) * smooth_env(n, 8, 0.6, 52) * np.clip(t / 2.6, 0.2, 1)
    sizzle = rms_to(sizzle, -40)
    return stereo(L + sizzle, R + np.roll(sizzle, 400), 0.15)


def main():
    write(OUT / "music/bed.wav", music())
    for name, fn in [("01", sfx01), ("02", sfx02), ("03", sfx03), ("04", sfx04), ("05", sfx05)]:
        st = fn()
        st[:, 0] = fades(st[:, 0], 0.02, 0.06); st[:, 1] = fades(st[:, 1], 0.02, 0.06)
        write(OUT / f"sfx/{name}.wav", st)


if __name__ == "__main__":
    main()
