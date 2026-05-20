import urllib.request
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSIC_DIR = ROOT / "warfront" / "assets" / "audio" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# Delete old .wav files to clean up
for old_wav in MUSIC_DIR.glob("*.wav"):
    try:
        old_wav.unlink()
    except OSError as exc:
        print(f"Failed to remove {old_wav.name}: {exc}")

TRACKS = {
    "battlefield_loop.ogg": "https://upload.wikimedia.org/wikipedia/commons/1/1b/Richard_Wagner_-_The_Valkyrie_-_Ride_of_the_Valkyries.ogg",
    "jungle_outpost.ogg": "https://upload.wikimedia.org/wikipedia/commons/2/23/Vivaldi_-_The_Four_Seasons%2C_Summer%2C_3._Presto.ogg",
    "trench_line.ogg": "https://upload.wikimedia.org/wikipedia/commons/6/6c/Beethoven_Symphony_No.5_Op.67_-_01_Allegro_con_brio.ogg",
    "river_bridge.ogg": "https://upload.wikimedia.org/wikipedia/commons/e/e6/Holst_-_The_Planets%2C_Op._32_-_I._Mars%2C_the_Bringer_of_War.ogg",
    "armored_front.ogg": "https://upload.wikimedia.org/wikipedia/commons/e/ea/Tchaikovsky_-_1812_Overture.ogg",
}

for filename, url in TRACKS.items():
    dest = MUSIC_DIR / filename
    print(f"Downloading {filename}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print(f"Saved {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
