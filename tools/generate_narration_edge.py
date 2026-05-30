from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg


VOICE = "vi-VN-NamMinhNeural"
RATE = "+8%"
TOTAL_SECONDS = "855"


async def synthesize() -> None:
    project = Path(__file__).resolve().parents[1]
    release = project / "Warfront_Release"
    segments_path = release / "narration_segments.json"
    clips_dir = release / "narration_clips"
    output_path = release / "WarfrontCommand_narration_vi.wav"
    clips_dir.mkdir(parents=True, exist_ok=True)
    segments = json.loads(segments_path.read_text(encoding="utf-8-sig"))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    for index, segment in enumerate(segments):
        mp3_path = clips_dir / f"segment_{index:03d}.mp3"
        wav_path = clips_dir / f"segment_{index:03d}.wav"
        communicate = edge_tts.Communicate(str(segment["text"]), VOICE, rate=RATE)
        await communicate.save(str(mp3_path))
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(mp3_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            check=True,
        )
        print(f"generated {wav_path.name}")

    subprocess.run(
        [
            sys.executable,
            str(project / "tools" / "combine_narration_wav.py"),
            str(segments_path),
            str(clips_dir),
            str(output_path),
            TOTAL_SECONDS,
        ],
        check=True,
    )


if __name__ == "__main__":
    asyncio.run(synthesize())
