"""Synthesise every sound effect and music loop used by the game.

All audio is generated from scratch with numpy, so there are no third-party
sound licences to worry about. Run from the repository root:

    python tools/generate_audio.py
"""

import os
import wave

import numpy as np

SR = 22050
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
rng = np.random.default_rng(2023)


# --- building blocks ---------------------------------------------------------
def t_axis(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, attack=0.005, decay=0.2, curve=4.0):
    """Fast attack, exponential decay envelope of n samples."""
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-curve * np.maximum(t - attack, 0) / max(decay, 1e-4))
    return a * d


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    t = np.arange(n) / SR
    total = n / SR
    out = np.full(n, s)
    out[t < a] = t[t < a] / a
    m = (t >= a) & (t < a + d)
    out[m] = 1 - (1 - s) * (t[m] - a) / d
    rel = t > total - r
    out[rel] *= np.clip((total - t[rel]) / r, 0, 1)
    return out


def sweep(f0, f1, dur, shape="sine"):
    t = t_axis(dur)
    f = f0 * (f1 / f0) ** (t / dur)
    phase = 2 * np.pi * np.cumsum(f) / SR
    if shape == "square":
        return np.sign(np.sin(phase)) * 0.6
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    return np.sin(phase)


def tone(freq, dur, shape="sine", detune=0.0):
    t = t_axis(dur)
    phase = 2 * np.pi * freq * t
    if shape == "saw":
        s = 2 * ((freq * t) % 1.0) - 1
        if detune:
            s = 0.5 * s + 0.5 * (2 * ((freq * (1 + detune) * t) % 1.0) - 1)
        return s
    if shape == "square":
        return np.sign(np.sin(phase)) * 0.7
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    return np.sin(phase)


def noise(dur):
    return rng.uniform(-1, 1, int(SR * dur))


def lowpass(x, cutoff):
    """One-pole low-pass filter (cutoff may be a scalar or per-sample array)."""
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    alpha = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha[i] * (x[i] - acc)
        y[i] = acc
    return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def echo(x, delay=0.12, feedback=0.35, taps=4):
    d = int(SR * delay)
    out = np.concatenate([x, np.zeros(d * taps)])
    for k in range(1, taps + 1):
        out[d * k:d * k + len(x)] += x * feedback ** k
    return out


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def note_freq(name):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7,
             "G#": 8, "A": 9, "A#": 10, "B": 11}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave + 1) - 69) / 12)


def save(name, x, peak=0.9):
    x = np.asarray(x, dtype=float)
    m = np.max(np.abs(x)) or 1.0
    x = x / m * peak
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"  {name:14s} {len(x) / SR:5.2f}s")


# --- sound effects -----------------------------------------------------------
def sfx_pop(pitch):
    dur = 0.28
    n = int(SR * dur)
    burst = highpass(noise(dur), 900 * pitch) * env(n, 0.001, 0.05, 5)
    snap = sweep(900 * pitch, 140 * pitch, dur) * env(n, 0.001, 0.06, 5)
    thump = sweep(180 * pitch, 60, dur) * env(n, 0.002, 0.09, 4)
    return mix(burst * 0.9, snap * 0.5, thump * 0.6)


def sfx_shoot():
    dur = 0.18
    n = int(SR * dur)
    zap = sweep(1400, 300, dur, "tri") * env(n, 0.002, 0.06, 4)
    air = lowpass(noise(dur), 3000) * env(n, 0.001, 0.04, 5)
    return mix(zap * 0.5, air * 0.5)


def sfx_clank():
    dur = 0.45
    n = int(SR * dur)
    parts = [tone(f, dur) * env(n, 0.001, 0.25 / (i + 1), 3) for i, f in enumerate([620, 1180, 1710, 2440])]
    hit = highpass(noise(dur), 2500) * env(n, 0.001, 0.02, 6)
    return mix(*parts, hit * 0.6)


def sfx_bomb():
    dur = 1.4
    n = int(SR * dur)
    rumble = lowpass(noise(dur), np.linspace(1800, 120, n)) * env(n, 0.002, 0.6, 3)
    boom = sweep(120, 35, dur) * env(n, 0.002, 0.45, 3)
    crack = highpass(noise(dur), 1500) * env(n, 0.001, 0.05, 6)
    return mix(rumble * 1.2, boom * 1.0, crack * 0.5)


def sfx_chime(notes, step=0.07, length=0.6, shape="sine"):
    parts = []
    for i, nname in enumerate(notes):
        f = note_freq(nname)
        n = int(SR * length)
        s = (tone(f, length, shape) + 0.3 * tone(f * 2, length)) * env(n, 0.002, length * 0.6, 3)
        parts.append(np.concatenate([np.zeros(int(SR * step * i)), s]))
    return echo(mix(*parts), 0.11, 0.3, 3)


def sfx_powerup():
    dur = 0.6
    n = int(SR * dur)
    up = sweep(300, 1500, dur, "square") * adsr(n, 0.01, 0.2, 0.5, 0.25)
    return echo(lowpass(up, 4000) * 0.6, 0.09, 0.3, 3)


def sfx_freeze():
    dur = 0.9
    n = int(SR * dur)
    shimmer = mix(*[tone(f, dur) * env(n, 0.01, 0.5, 2.5) for f in (1568, 2093, 2637, 3136)])
    wind = lowpass(noise(dur), np.linspace(6000, 600, n)) * adsr(n, 0.05, 0.2, 0.4, 0.4)
    down = sweep(1200, 300, dur) * env(n, 0.01, 0.5, 2.5)
    return mix(shimmer * 0.5, wind * 0.6, down * 0.3)


def sfx_nova():
    dur = 0.9
    n = int(SR * dur)
    whoom = sweep(80, 900, dur * 0.5, "tri")
    whoom = np.concatenate([whoom, sweep(900, 60, dur * 0.5, "tri")])
    whoom = whoom * env(len(whoom), 0.005, 0.45, 2.5)
    sparkle = highpass(noise(dur), 4000) * env(n, 0.001, 0.25, 3)
    return mix(whoom * 0.7, sparkle * 0.4, sfx_pop(0.7) * 0.8)


def sfx_blip():
    dur = 0.09
    n = int(SR * dur)
    return tone(880, dur, "square") * env(n, 0.001, 0.05, 4) * 0.5


def sfx_hover():
    dur = 0.06
    n = int(SR * dur)
    return tone(1320, dur, "tri") * env(n, 0.001, 0.03, 4) * 0.4


def sfx_click():
    dur = 0.12
    n = int(SR * dur)
    return mix(tone(660, dur, "tri") * env(n, 0.001, 0.05, 4), tone(990, dur) * env(n, 0.02, 0.05, 4) * 0.6)


def sfx_beep(freq, dur=0.22):
    n = int(SR * dur)
    return (tone(freq, dur, "square") * 0.5 + tone(freq * 2, dur) * 0.3) * adsr(n, 0.005, 0.05, 0.6, 0.1)


def sfx_escape():
    dur = 0.5
    n = int(SR * dur)
    return sweep(900, 260, dur, "tri") * env(n, 0.01, 0.3, 2.5) * 0.6


def sfx_lose():
    dur = 0.35
    n = int(SR * dur)
    return sweep(300, 90, dur, "square") * env(n, 0.005, 0.2, 3) * 0.6


def jingle(notes, step, length, shape="square"):
    parts = []
    for i, nname in enumerate(notes):
        if nname is None:
            continue
        f = note_freq(nname)
        n = int(SR * length)
        s = lowpass(tone(f, length, shape), 3500) * adsr(n, 0.005, 0.08, 0.6, 0.12)
        s += tone(f * 0.5, length, "tri") * adsr(n, 0.005, 0.08, 0.5, 0.12) * 0.5
        parts.append(np.concatenate([np.zeros(int(SR * step * i)), s]))
    return echo(mix(*parts), 0.14, 0.25, 3)


# --- music ---------------------------------------------------------------------
def kick(dur=0.35):
    n = int(SR * dur)
    return sweep(150, 40, dur) * env(n, 0.001, 0.15, 3)


def snare(dur=0.25):
    n = int(SR * dur)
    return mix(highpass(noise(dur), 1200) * env(n, 0.001, 0.1, 4) * 0.7,
               tone(190, dur, "tri") * env(n, 0.001, 0.05, 4) * 0.5)


def hat(dur=0.06):
    n = int(SR * dur)
    return highpass(noise(dur), 7000) * env(n, 0.001, 0.02, 5) * 0.35


def place(track, sample, at):
    i = int(at * SR)
    end = min(len(track), i + len(sample))
    track[i:end] += sample[:end - i]


def wrap_tail(track, loop_len):
    """Fold anything past the loop end back to the start for a seamless loop."""
    n = int(loop_len * SR)
    out = track[:n].copy()
    tail = track[n:]
    out[:len(tail)] += tail
    return out


def music_carnival():
    bpm = 124
    beat = 60 / bpm
    bars = 16
    loop = bars * 4 * beat
    track = np.zeros(int((loop + 2) * SR))
    prog = [("C", ["C4", "E4", "G4"]), ("G", ["B3", "D4", "G4"]),
            ("A", ["C4", "E4", "A4"]), ("F", ["C4", "F4", "A4"])]
    lead_scale = ["C5", "D5", "E5", "G5", "A5", "C6"]
    k, s, h = kick(), snare(), hat()
    for bar in range(bars):
        root, chord = prog[bar % 4]
        t0 = bar * 4 * beat
        # drums
        for b in range(4):
            if b in (0, 2):
                place(track, k * 0.9, t0 + b * beat)
            if b in (1, 3) and bar >= 2:
                place(track, s * 0.6, t0 + b * beat)
        for e in range(8):
            place(track, h * (0.8 if e % 2 else 0.5), t0 + e * beat / 2)
        # bass: bouncy root / fifth eighths
        bass_root = note_freq(root + "2")
        for e in range(8):
            f = bass_root * (1.5 if e in (3, 7) else 1.0)
            dur = beat / 2 * 0.9
            n = int(SR * dur)
            place(track, lowpass(tone(f, dur, "saw"), 700) * adsr(n, 0.005, 0.05, 0.6, 0.05) * 0.45,
                  t0 + e * beat / 2)
        # pad chord stabs on the off-beats
        for b in range(4):
            dur = beat * 0.45
            n = int(SR * dur)
            stab = mix(*[tone(note_freq(c), dur, "saw", 0.006) for c in chord])
            place(track, lowpass(stab, 1800) * adsr(n, 0.01, 0.08, 0.5, 0.1) * 0.14, t0 + b * beat + beat / 2)
        # lead melody in the second half
        if bar >= 8:
            r = np.random.default_rng(bar % 4)
            for e in range(8):
                if r.random() < 0.3:
                    continue
                f = note_freq(lead_scale[r.integers(len(lead_scale))])
                dur = beat / 2 * 0.95
                n = int(SR * dur)
                pluck = (tone(f, dur, "square") * 0.5 + tone(f * 2, dur, "tri") * 0.2) * env(n, 0.003, 0.18, 3)
                place(track, lowpass(pluck, 3200) * 0.22, t0 + e * beat / 2)
    out = wrap_tail(echo(track, beat * 0.75, 0.2, 2), loop)
    return out


def music_zen():
    bpm = 72
    beat = 60 / bpm
    bars = 8
    loop = bars * 4 * beat
    track = np.zeros(int((loop + 4) * SR))
    chords = [["F3", "A3", "C4", "E4"], ["E3", "G3", "B3", "D4"],
              ["D3", "F3", "A3", "C4"], ["C3", "E3", "G3", "B3"]]
    bells = ["C5", "D5", "E5", "G5", "A5", "C6", "E6"]
    r = np.random.default_rng(7)
    for bar in range(bars):
        chord = chords[bar % 4]
        t0 = bar * 4 * beat
        dur = 4 * beat + 1.0
        n = int(SR * dur)
        pad = mix(*[tone(note_freq(c), dur) + 0.3 * tone(note_freq(c) * 2.003, dur) for c in chord])
        place(track, pad * adsr(n, 1.2, 0.5, 0.7, 1.4) * 0.12, t0)
        for e in range(8):
            if r.random() < 0.55:
                continue
            f = note_freq(bells[r.integers(len(bells))])
            d = 1.6
            nn = int(SR * d)
            bell = (tone(f, d) + 0.25 * tone(f * 2.76, d) + 0.1 * tone(f * 5.4, d)) * env(nn, 0.004, 0.9, 3)
            place(track, bell * 0.16, t0 + e * beat / 2)
    out = wrap_tail(echo(track, beat * 0.66, 0.35, 4), loop)
    return lowpass(out, 5000)


def main():
    print("Generating sounds into", os.path.abspath(OUT))
    for i, p in enumerate((1.0, 1.15, 0.88)):
        save(f"pop{i + 1}", sfx_pop(p))
    save("shoot", sfx_shoot(), 0.6)
    save("clank", sfx_clank(), 0.7)
    save("bomb", sfx_bomb())
    save("gold", sfx_chime(["E6", "G6", "B6", "E7"], 0.06, 0.7))
    save("bonus", sfx_chime(["C6", "E6", "G6"], 0.07, 0.5))
    save("powerup", sfx_powerup(), 0.7)
    save("freeze", sfx_freeze(), 0.8)
    save("nova", sfx_nova())
    save("blip", sfx_blip(), 0.5)
    save("hover", sfx_hover(), 0.35)
    save("click", sfx_click(), 0.6)
    save("count", sfx_beep(660), 0.6)
    save("go", sfx_beep(1320, 0.45), 0.7)
    save("escape", sfx_escape(), 0.5)
    save("lose", sfx_lose(), 0.6)
    save("gameover", jingle(["G4", "E4", "C4", None, "D4", "B3", "C4"], 0.16, 0.4), 0.8)
    save("newbest", jingle(["C5", "E5", "G5", "C6", None, "G5", "C6", "E6"], 0.11, 0.35), 0.8)
    save("music_carnival", music_carnival(), 0.75)
    save("music_zen", music_zen(), 0.75)


if __name__ == "__main__":
    main()
