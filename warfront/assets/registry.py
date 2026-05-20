from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent

CHARACTERS = {
    "allied_soldier": ASSET_DIR / "characters" / "allied_soldier_sheet.png",
    "axis_soldier": ASSET_DIR / "characters" / "axis_soldier_sheet.png",
}

VEHICLES = {
    "allied_m4_sherman": ASSET_DIR / "vehicles" / "allied_m4_sherman_sheet.png",
}

AIRCRAFT = {
    "axis_heavy_bomber": ASSET_DIR / "aircraft" / "axis_heavy_bomber_sheet.png",
}

MAPS = {
    "jungle_base_reference": ASSET_DIR / "maps" / "jungle_base_reference_and_props.png",
}

PROPS = {
    "military_support_logistics": ASSET_DIR / "props" / "military_support_logistics_sheet.png",
}

SOURCE_SHEETS = {
    "labeled_support_items_vi": ASSET_DIR / "source_sheets" / "labeled_support_items_vi_sheet.png",
}

