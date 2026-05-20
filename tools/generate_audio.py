from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SFX_DIR = ROOT / "warfront" / "assets" / "audio" / "sfx"
MUSIC_DIR = ROOT / "warfront" / "assets" / "audio" / "music"
SAMPLE_RATE = 44_100
MAX_AMPLITUDE = 32_767


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def envelope(t: float, duration: float, attack: float, release: float) -> float:
    if t < attack:
        return t / attack if attack > 0 else 1.0
    tail = duration - t
    if tail < release:
        return max(0.0, tail / release) if release > 0 else 0.0
    return 1.0


def sine(freq: float, t: float) -> float:
    return math.sin(math.tau * freq * t)


def square(freq: float, t: float) -> float:
    return 1.0 if sine(freq, t) >= 0.0 else -1.0


def fade(samples: list[float], attack: float = 0.004, release: float = 0.03) -> list[float]:
    duration = len(samples) / SAMPLE_RATE
    return [
        sample * envelope(index / SAMPLE_RATE, duration, attack, release)
        for index, sample in enumerate(samples)
    ]


def write_wav(path: Path, samples: list[float]) -> None:
    frames = bytearray()
    for sample in samples:
        value = int(clamp(sample) * MAX_AMPLITUDE)
        frames.extend(struct.pack("<h", value))

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))


def render(duration: float, make_sample) -> list[float]:
    count = int(SAMPLE_RATE * duration)
    return [make_sample(index / SAMPLE_RATE) for index in range(count)]


def rifle() -> list[float]:
    rng = random.Random(11)
    duration = 0.16

    def sample(t: float) -> float:
        snap = rng.uniform(-1.0, 1.0) * math.exp(-t * 42.0)
        body = sine(150.0 - 55.0 * t, t) * math.exp(-t * 20.0)
        crack = square(1_900.0, t) * math.exp(-t * 70.0)
        return 0.62 * snap + 0.22 * body + 0.14 * crack

    return fade(render(duration, sample), attack=0.001, release=0.035)


def explosion() -> list[float]:
    rng = random.Random(23)
    duration = 0.72
    drift = 0.0

    def sample(t: float) -> float:
        nonlocal drift
        drift = drift * 0.93 + rng.uniform(-1.0, 1.0) * 0.07
        boom = sine(62.0 - 28.0 * min(t, 0.5), t) * math.exp(-t * 3.5)
        grit = rng.uniform(-1.0, 1.0) * math.exp(-t * 5.0)
        rumble = drift * math.exp(-t * 2.4)
        return 0.52 * boom + 0.38 * grit + 0.42 * rumble

    return fade(render(duration, sample), attack=0.004, release=0.18)


def pickup() -> list[float]:
    notes = [660.0, 880.0, 1_320.0]
    duration = 0.28

    def sample(t: float) -> float:
        note = notes[min(int(t / (duration / len(notes))), len(notes) - 1)]
        local = t % (duration / len(notes))
        ping = sine(note, t) + 0.28 * sine(note * 2.0, t)
        return ping * math.exp(-local * 14.0) * 0.45

    return fade(render(duration, sample), attack=0.002, release=0.04)


def heal() -> list[float]:
    duration = 0.62

    def sample(t: float) -> float:
        sweep = 430.0 + 420.0 * (t / duration)
        shimmer = sine(sweep, t) + 0.4 * sine(sweep * 1.5, t)
        pulse = 0.72 + 0.28 * sine(7.0, t)
        return shimmer * pulse * 0.32

    return fade(render(duration, sample), attack=0.04, release=0.16)


def grenade() -> list[float]:
    rng = random.Random(37)
    duration = 0.42

    def sample(t: float) -> float:
        toss = sine(180.0 - 95.0 * t, t) * math.exp(-t * 7.0)
        scrape = rng.uniform(-1.0, 1.0) * math.exp(-t * 11.0)
        click = square(820.0, t) * math.exp(-t * 26.0)
        return 0.46 * toss + 0.26 * scrape + 0.16 * click

    return fade(render(duration, sample), attack=0.003, release=0.09)


def menu_select() -> list[float]:
    duration = 0.12

    def sample(t: float) -> float:
        blip = sine(920.0, t) + 0.32 * sine(1_840.0, t)
        return blip * math.exp(-t * 28.0) * 0.42

    return fade(render(duration, sample), attack=0.001, release=0.035)


def tank_fire() -> list[float]:
    rng = random.Random(51)
    duration = 0.52

    def sample(t: float) -> float:
        cannon = sine(46.0 - 18.0 * t, t) * math.exp(-t * 5.4)
        blast = rng.uniform(-1.0, 1.0) * math.exp(-t * 9.5)
        metal = square(320.0, t) * math.exp(-t * 18.0)
        return 0.62 * cannon + 0.34 * blast + 0.16 * metal

    return fade(render(duration, sample), attack=0.002, release=0.14)


def hit() -> list[float]:
    rng = random.Random(67)
    duration = 0.18

    def sample(t: float) -> float:
        thud = sine(110.0, t) * math.exp(-t * 18.0)
        grit = rng.uniform(-1.0, 1.0) * math.exp(-t * 24.0)
        return 0.36 * thud + 0.42 * grit

    return fade(render(duration, sample), attack=0.001, release=0.045)


def capture() -> list[float]:
    duration = 0.78
    notes = [392.0, 523.25, 659.25, 784.0]

    def sample(t: float) -> float:
        step = min(int(t / (duration / len(notes))), len(notes) - 1)
        note = notes[step]
        local = t % (duration / len(notes))
        tone = sine(note, t) + 0.25 * sine(note * 2.0, t)
        return tone * math.exp(-local * 5.5) * 0.34

    return fade(render(duration, sample), attack=0.01, release=0.12)


def battlefield_loop() -> list[float]:
    rng = random.Random(83)
    duration = 8.0

    def sample(t: float) -> float:
        pulse = sine(55.0, t) * (0.45 + 0.25 * sine(0.5, t))
        distant = rng.uniform(-1.0, 1.0) * 0.12 * (0.4 + 0.6 * max(0.0, sine(0.17, t)))
        low = sine(82.0, t) * 0.12
        return 0.18 * pulse + distant + low

    return fade(render(duration, sample), attack=0.25, release=0.55)


def jungle_outpost_loop() -> list[float]:
    rng = random.Random(91)
    duration = 8.0

    def sample(t: float) -> float:
        pulse = sine(65.0, t) * (0.4 + 0.3 * sine(2.0, t))
        distant = rng.uniform(-1.0, 1.0) * 0.08 * (0.3 + 0.7 * max(0.0, sine(0.3, t)))
        shimmer = sine(120.0 + 30.0 * sine(1.5, t), t) * 0.06
        return 0.16 * pulse + distant + shimmer

    return fade(render(duration, sample), attack=0.25, release=0.55)


def trench_line_loop() -> list[float]:
    rng = random.Random(105)
    duration = 8.0

    def sample(t: float) -> float:
        pulse = square(45.0, t) * 0.04 * (0.5 + 0.5 * sine(0.25, t))
        distant = rng.uniform(-1.0, 1.0) * 0.15
        low = sine(70.0, t) * 0.14
        return pulse + distant + low

    return fade(render(duration, sample), attack=0.25, release=0.55)


def river_bridge_loop() -> list[float]:
    rng = random.Random(119)
    duration = 8.0

    def sample(t: float) -> float:
        pulse = sine(80.0, t) * 0.12 * (0.6 + 0.4 * sine(0.8, t))
        distant = rng.uniform(-1.0, 1.0) * 0.09 * (0.5 + 0.5 * sine(0.12, t))
        flowing = sine(150.0, t) * 0.08 * (0.5 + 0.5 * sine(4.0, t))
        return pulse + distant + flowing

    return fade(render(duration, sample), attack=0.25, release=0.55)


def armored_front_loop() -> list[float]:
    rng = random.Random(133)
    duration = 8.0

    def sample(t: float) -> float:
        clank = square(90.0, t) * 0.05 * math.exp(-(t % 1.0) * 8.0)
        distant = rng.uniform(-1.0, 1.0) * 0.12
        low = sine(60.0, t) * 0.18
        return clank + distant + low

    return fade(render(duration, sample), attack=0.25, release=0.55)


SOUNDS = {
    "rifle.wav": rifle,
    "explosion.wav": explosion,
    "pickup.wav": pickup,
    "heal.wav": heal,
    "grenade.wav": grenade,
    "menu_select.wav": menu_select,
    "tank_fire.wav": tank_fire,
    "hit.wav": hit,
    "capture.wav": capture,
}


def main() -> int:
    for filename, maker in SOUNDS.items():
        path = SFX_DIR / filename
        write_wav(path, maker())
        print(f"Wrote {path.relative_to(ROOT)}")

    # Write music loops
    loops = {
        "battlefield_loop.wav": battlefield_loop,
        "jungle_outpost.wav": jungle_outpost_loop,
        "trench_line.wav": trench_line_loop,
        "river_bridge.wav": river_bridge_loop,
        "armored_front.wav": armored_front_loop,
    }
    for filename, maker in loops.items():
        music_path = MUSIC_DIR / filename
        write_wav(music_path, maker())
        print(f"Wrote {music_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
