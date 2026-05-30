from __future__ import annotations

import json
import re
from pathlib import Path


MAIN_VIDEO_SECONDS = 854.83
SECTION_RE = re.compile(r"^### (\d{2}):(\d{2}) - (\d{2}):(\d{2})$")


def seconds(minutes: str, value: str) -> float:
    return int(minutes) * 60 + int(value)


def srt_time(value: float) -> str:
    milliseconds = round(value * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    release = project / "Warfront_Release"
    source = release / "LOI_THOAI_VIDEO_DEMO.md"
    segments_path = release / "narration_segments_v2.json"
    subtitles_path = release / "WarfrontCommand_subtitles_vi.srt"
    lines = source.read_text(encoding="utf-8-sig").splitlines()

    segments: list[dict[str, object]] = []
    index = 0
    while index < len(lines):
        match = SECTION_RE.match(lines[index].strip())
        index += 1
        if not match:
            continue

        start = seconds(match.group(1), match.group(2))
        end = seconds(match.group(3), match.group(4))
        text_lines: list[str] = []
        while index < len(lines) and not lines[index].startswith("### "):
            line = lines[index].strip()
            index += 1
            if line and not line.startswith("## "):
                text_lines.append(line)

        text = " ".join(text_lines)
        if not text or start >= MAIN_VIDEO_SECONDS:
            continue
        segments.append({"start": start, "end": min(end, MAIN_VIDEO_SECONDS), "text": text})

    segments_path.write_text(
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    subtitles = []
    for number, segment in enumerate(segments, start=1):
        subtitles.extend(
            [
                str(number),
                f"{srt_time(float(segment['start']))} --> {srt_time(float(segment['end']))}",
                str(segment["text"]),
                "",
            ]
        )
    subtitles_path.write_text("\n".join(subtitles), encoding="utf-8-sig")
    print(f"wrote {segments_path}")
    print(f"wrote {subtitles_path}")
    print(f"segments {len(segments)}")


if __name__ == "__main__":
    main()
