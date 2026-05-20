# Warfront Command Asset Manifest

Nguon tai nguyen duoc doc tu `D:\My\Games\TN` va sap xep lai vao project.

## Da sap xep va doi ten

| File goc trong `TN` | Ten moi | Vi tri | Vai tro |
| --- | --- | --- | --- |
| `Player.png` | `allied_soldier_sheet.png` | `warfront/assets/characters/` | Linh dong minh/player, nhieu tu the di chuyen va ban |
| `Gemini_Generated_Image_vafhd9vafhd9vafh.png` | `axis_soldier_sheet.png` | `warfront/assets/characters/` | Linh doi dich, nhieu tu the di chuyen va ban |
| `Gemini_Generated_Image_1sasye1sasye1sas.png` | `allied_m4_sherman_sheet.png` | `warfront/assets/vehicles/` | Xe tang M4 Sherman, ban, no, hu hong |
| `Gemini_Generated_Image_s7r3vls7r3vls7r3.png` | `axis_heavy_bomber_sheet.png` | `warfront/assets/aircraft/` | May bay nem bom, bom, dan, no |
| `Gemini_Generated_Image_3a0g9v3a0g9v3a0g.png` | `jungle_base_reference_and_props.png` | `warfront/assets/maps/` | Can cu rung tham khao, cong trinh, vat can, do hau can |
| `Gemini_Generated_Image_tv3n3otv3n3otv3n.png` | `military_support_logistics_sheet.png` | `warfront/assets/props/` | Phuy, bao cat, thung dan, radio, cuu thuong, min, dung cu |
| `Gemini_Generated_Image_astnv1astnv1astn.png` | `labeled_support_items_vi_sheet.png` | `warfront/assets/source_sheets/` | Sheet co nhan tieng Viet dung de tham chieu/cat asset |

## Danh gia do day du

Du cho ban chien tranh top-down co cac thanh phan chinh:

- Player va enemy soldier.
- Tank.
- May bay/bom.
- Can cu/map tham khao.
- Vat can va do trang tri chien truong: bao cat, phuy, hop dan, radio, ho cuu thuong, min, no.

Chua hoan toan du neu muon dua vao game san xuat ngay:

- Can cat frame rieng tu cac sheet lon thanh tung sprite nho co nen trong suot.
- Can tileset map rieng dang o luoi deu, vi `jungle_base_reference_and_props.png` hien la anh minh hoa + sheet props, khong phai map tile chuan.
- Chua co UI rieng: icon mau, ammo, minimap, menu, cursor.
- Chua co am thanh: ban sung, no, xe tang, may bay, nhac nen.
- Chua co asset rieng cho phe dich bang xe tang; co the tam dung Sherman va doi mau trong code.

## De xuat buoc tiep theo

1. Cat tu cac sheet thanh sprite rieng: `characters`, `vehicles`, `aircraft`, `props`, `effects`.
2. Tao file metadata JSON mo ta tung frame animation.
3. Sua game load sprite tu asset that thay vi ve bang shape Pygame.
4. Bo sung audio hoac bao nguoi dung tao/cung cap bo am thanh rieng.

