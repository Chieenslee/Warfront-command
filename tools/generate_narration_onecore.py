from __future__ import annotations

import asyncio
import json
import subprocess
import argparse
import sys
from pathlib import Path

import imageio_ffmpeg
from winrt.windows.media.speechsynthesis import SpeechSynthesizer
from winrt.windows.storage.streams import Buffer, InputStreamOptions


async def stream_bytes(stream) -> bytes:
    stream.seek(0)
    buffer = Buffer(int(stream.size))
    result = await stream.read_async(buffer, int(stream.size), InputStreamOptions.NONE)
    return bytes(result)


async def synthesize(segments_name: str, output_name: str, total_seconds: str) -> None:
    project = Path(__file__).resolve().parents[1]
    release = project / "Warfront_Release"
    segments_path = release / segments_name
    clips_dir = release / f"narration_clips_{Path(segments_name).stem}"
    output_path = release / output_name
    clips_dir.mkdir(parents=True, exist_ok=True)
    segments = json.loads(segments_path.read_text(encoding="utf-8-sig"))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    synth = SpeechSynthesizer()
    voices = [voice for voice in SpeechSynthesizer.all_voices if voice.language == "vi-VN"]
    if not voices:
        raise RuntimeError("Microsoft An vi-VN voice is not installed")
    synth.voice = voices[0]
    print(f"voice {synth.voice.display_name}")

    for index, segment in enumerate(segments):
        source_path = clips_dir / f"segment_{index:03d}_onecore.wav"
        wav_path = clips_dir / f"segment_{index:03d}.wav"
        stream = await synth.synthesize_text_to_stream_async(str(segment["text"]))
        source_path.write_bytes(await stream_bytes(stream))
        stream.close()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
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
            total_seconds,
        ],
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", default="narration_segments.json")
    parser.add_argument("--output", default="WarfrontCommand_narration_vi.wav")
    parser.add_argument("--total-seconds", default="855")
    args = parser.parse_args()
    asyncio.run(synthesize(args.segments, args.output, args.total_seconds))
