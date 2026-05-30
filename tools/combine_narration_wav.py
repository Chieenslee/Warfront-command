from __future__ import annotations

import json
import sys
import wave
from array import array
from pathlib import Path


def silence_frames(seconds: float, rate: int, channels: int, sample_width: int) -> bytes:
    return b"\0" * max(0, round(seconds * rate) * channels * sample_width)


def main() -> None:
    segments_path = Path(sys.argv[1])
    clips_dir = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    total_seconds = float(sys.argv[4])
    segments = json.loads(segments_path.read_text(encoding="utf-8-sig"))

    first_path = clips_dir / "segment_000.wav"
    with wave.open(str(first_path), "rb") as first:
        channels = first.getnchannels()
        sample_width = first.getsampwidth()
        rate = first.getframerate()

    total_frames = round(total_seconds * rate)
    track = array("h", [0]) * (total_frames * channels)
    frame_size = channels * sample_width
    warnings: list[str] = []
    for index, segment in enumerate(segments):
        clip_path = clips_dir / f"segment_{index:03d}.wav"
        with wave.open(str(clip_path), "rb") as clip:
            if (clip.getnchannels(), clip.getsampwidth(), clip.getframerate()) != (channels, sample_width, rate):
                raise RuntimeError(f"Unexpected WAV format: {clip_path}")
            clip_data = clip.readframes(clip.getnframes())

        clip_samples = array("h")
        clip_samples.frombytes(clip_data)
        start_sample = round(float(segment["start"]) * rate) * channels
        end_sample = min(start_sample + len(clip_samples), len(track))
        for sample_index, clip_sample in enumerate(clip_samples[: end_sample - start_sample], start=start_sample):
            mixed = track[sample_index] + clip_sample
            track[sample_index] = max(-32768, min(32767, mixed))
        declared_end = float(segment.get("end", total_seconds))
        actual_end = float(segment["start"]) + len(clip_samples) / rate / channels
        if actual_end > declared_end:
            warnings.append(f"segment {index:03d} exceeds subtitle window by {actual_end - declared_end:.2f}s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(rate)
        output.writeframes(track.tobytes())

    print(f"wrote {output_path.resolve()}")
    print(f"duration {total_frames / rate:.2f}s")
    for warning in warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
