from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


def run(args: list[str]) -> None:
    print(" ".join(args))
    subprocess.run(args, check=True)


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    release = project / "Warfront_Release"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    intro = release / "2026-05-30 17-26-45.mp4"
    demo = release / "2026-05-30 17-32-07.mp4"
    outro = release / "Video Project 5.mp4"
    narration = release / "WarfrontCommand_narration_vi_v2.wav"
    subtitles = "Warfront_Release/WarfrontCommand_subtitles_vi.srt"
    output = release / "WarfrontCommand_demo_thuyet_minh_v3_sub_nho.mp4"

    filter_complex = (
        "[0:v]setpts=PTS-STARTPTS[v0];"
        "[1:v]setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[main_video];"
        f"[main_video]subtitles='{subtitles}':"
        "force_style='FontName=Arial,FontSize=6,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,"
        "Alignment=2,MarginV=18'[main_sub];"
        "[2:v]fps=60,setpts=PTS-STARTPTS[outro_video];"
        "[main_sub][outro_video]concat=n=2:v=1:a=0[v];"
        "[0:a]volume=0.10[a0];"
        "[1:a]volume=0.10[a1];"
        "[a0][a1]concat=n=2:v=0:a=1[game];"
        "[game][3:a]amix=inputs=2:duration=first:normalize=0[main_audio];"
        "[2:a]asetpts=PTS-STARTPTS[outro_audio];"
        "[main_audio][outro_audio]concat=n=2:v=0:a=1[a]"
    )
    run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(intro),
            "-i",
            str(demo),
            "-i",
            str(outro),
            "-i",
            str(narration),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
