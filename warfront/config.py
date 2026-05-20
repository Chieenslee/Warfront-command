from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

SCREEN_WIDTH = 1100
SCREEN_HEIGHT = 650
FPS = 60
TILE_SIZE = 48

PLAYER_SPEED = 230
PLAYER_MAX_HP = 120
SOLDIER_SPEED = 105
TANK_SPEED = 65

BULLET_SPEED = 620
ENEMY_BULLET_SPEED = 420
CAPTURE_SECONDS = 6.0

COLORS = {
    "grass": (67, 105, 63),
    "grass_alt": (78, 121, 71),
    "road": (87, 82, 73),
    "trench": (83, 62, 43),
    "wall": (76, 78, 72),
    "water": (45, 91, 115),
    "sand": (128, 117, 79),
    "shadow": (20, 20, 18),
    "ui": (238, 232, 207),
    "danger": (184, 59, 47),
    "ally": (83, 142, 91),
    "enemy": (148, 69, 58),
    "steel": (92, 102, 96),
}

