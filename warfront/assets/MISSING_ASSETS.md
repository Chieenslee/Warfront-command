# Missing Or To-Be-Generated Assets

Da co day du sheet lon cho nhan vat, xe tang, may bay, map tham khao va props.

Da tu sinh/cat cac anh can thiet de game co the load truc tiep:

- `cut_sprites/characters/`: player va enemy soldier da cat frame rieng.
- `cut_sprites/vehicles/`: tank da cat frame rieng.
- `cut_sprites/aircraft/`: bomber da cat frame rieng.
- `cut_sprites/props/`: vat pham hau can da cat rieng.
- `cut_sprites/effects/`: no, khoi, lua, dan lua da cat rieng.
- `ui/icons/`: icon UI co ban.
- `ui/cursor/`: crosshair.
- `tilemaps/tileset/`: tile co ban cho grass, road, trench, water, wall, sandbag, capture.

Con can tao/cung cap them neu muon day du san xuat:

| Thu muc | Can co | Co the tao bang code? | Ghi chu |
| --- | --- | --- | --- |
| `audio/sfx/` | `rifle.wav`, `tank_fire.wav`, `explosion.wav`, `hit.wav`, `capture.wav` | Co | Day la am thanh, khong phai anh |
| `audio/music/` | Nhac nen chien truong loop | Nen cung cap | Nen dung file rieng hoac asset co license ro |

Uu tien tiep theo nen lam:

1. Tao/cai thien am thanh.
2. Tao `animations.json` chi tiet hon de khai bao tung hang animation co y nghia.
3. Gan vao game thay vi ve entity bang shape.
