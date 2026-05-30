# Warfront Command - Checklist hien tai

Ngay cap nhat: 2026-05-27

## Trang thai tong quan

| Hang muc | Trang thai | Ghi chu |
|---|---|---|
| 4 map MEGA moi | Done, can playtest | Da co `jungle_outpost_mega`, `trench_line_mega`, `river_bridge_mega`, `armored_front_mega`. |
| Map audit / so do TXT | Done | Da co file audit va map design txt. |
| Chong ket do tiep te | Done | TileMap tu repair duong vao item bi phong kin. |
| Chan ra ngoai map | Done | Actor/vehicle bi chan o bien world. |
| Nuoc cho dan ban qua | Done | Nuoc van chan di chuyen, khong chan dan. |
| Decoration map | Partial | Da them corpse, barrel, debris, wreck, radio spawn; can them neu thay map con trong. |
| Lag menu truoc khi vao game | Improved | Da cache text/menu preview/tile/prop; can playtest may that. |
| Lag khi choi map lon | Improved, can playtest | Da camera-load culling, prop bucket, pathfinding cap. |
| Remote player animation | Improved, can verify online | Da dong bo anim state/time/moving/shoot flash; can test 2 may. |
| Remote player lai tank online | Partial | Host co serialize vehicle owner/state; can test lai input/exit/enter online. |
| Inventory rieng tung nguoi online | Partial | Host co session inventory rieng; can test sync HUD client. |
| PvP online team win/lose | Partial | Da co blue/red alive check; can test 2v2 that. |
| Reconnect/lobby/team that | Partial | Lobby co player list/team; reconnect can lam tiep. |

## Gameplay da sua gan day

| Hang muc | Trang thai | Ghi chu test |
|---|---|---|
| Chi dung AK-47 | Done | Loadout ep `ak47`, action bar chi hien AK. |
| Nang cap AK 9 cap | Done | Cap 9 = 200 damage. |
| Nang cap bot dong minh 9 cap | Done | Cap 9 = 200 damage cho bot offline ally. |
| Giam cap AK / bot | Done | Nut `-` trong shop hoan tien tung cap. |
| Xe tang bat/tat va hoan tien | Done | Click tank trong shop de toggle; tat hoan cost. |
| Save theo ten nguoi choi | Done | Moi ten dung file save rieng `save_<ten>.json`. |
| Tien mac dinh | Done | Profile moi bat dau voi 500 credits. |
| Code admin | Done | Nhap `admin` trong shop de set credits len 99999, khong mo map/che do. |
| 4 map cuoi them may bay/boss tank | Done | MEGA 1/2/3/4 co 2/3/4/5 aircraft va boss tank. |
| Boss tank extra | Done, can balance | Boss dung `super_heavy`, hp tang 25%. |
| Hoat anh xe tang | Improved | Bo nong ve tay; dung frame cut sprite idle/move/fire/wreck. |
| Hit/death animation linh | Done | Allied hit=019, axis hit=000, allied dead=176, axis dead=173. |
| Cot truyen 8 map campaign | Done | 4 map nho va 4 map MEGA deu co dialogue/cutscene truoc tran. |
| Nhac nen fallback | Done | Neu map chua co nhac rieng thi chay `assets/audio/music/placeholder_loop.wav`. |

## Checklist test nhanh trong game

| Test | Ket qua mong doi | Trang thai |
|---|---|---|
| Vao shop, nhap code `admin` | Credits len 99999, khong tu mo map | Can test UI |
| Mua AK upgrade 9 lan | HUD hien AK D200 | Can test UI |
| Giam AK upgrade | Credits duoc hoan, AK damage giam | Done smoke |
| Mua bot upgrade 9 lan | Bot ban damage gan 200 | Can test combat |
| Giam bot upgrade | Credits duoc hoan, bot damage giam | Done smoke |
| Toggle tank ON/OFF | ON co xe, OFF mat xe va hoan tien | Can test UI/play |
| Ban qua nuoc | Dan bay qua nuoc, trung dich ben kia | Can test play |
| Lai tank den mep map | Tank khong vuot bien | Can test play |
| Map cuoi item tiep te | Tat ca item co duong vao | Done smoke |
| Map MEGA dau | 2 aircraft, 2 boss tank | Done smoke |
| Map MEGA thu hai | 3 aircraft, 3 boss tank | Done smoke |
| Map MEGA thu ba | 4 aircraft, 4 boss tank | Done smoke |
| Map MEGA thu tu | 5 aircraft, 5 boss tank | Done smoke |
| Xe tang ban | Fire frame khong con nong que dai | Can visual test |
| Linh bi trung dan | Player/NPC doi sang frame hit dung phe | Done smoke |
| Linh chet | Player/NPC dung frame death dung phe | Done smoke |
| Cutscene map nho/lon | Moi map campaign co dialogue de doc truoc tran | Done smoke |
| Nhac nen map nho/lon | Co file fallback de mixer load khi chua co nhac rieng | Done smoke |
| Remote player ban/chay | Animation giong local hon | Can online test |
| Remote player len/xuong tank | Client khong bi desync | Can online test |
| PvP online het team dich | Dung team win/lose | Can online test |

## Viec nen lam tiep

| Uu tien | Viec | Ly do |
|---|---|---|
| P0 | Chay playtest 10-15 phut map `armored_front_mega` | Map lon nhieu AI/tank/may bay de lo lag va loi path. |
| P0 | Test shop admin + upgrade + tank toggle | Day la luong moi vua them. |
| P0 | Test profile theo ten | Doi ten phai ra tien/save rieng, profile moi = 500 credits. |
| P0 | Thay nhac that vao `warfront/assets/audio/music/` | Dat theo ten map hoac thay `placeholder_loop.wav`. |
| P1 | Test online host/client voi remote tank | De chot muc tieu remote player lai tank online. |
| P1 | Them accessibility audit vao tool map | De bat item/phong kin tu file design truoc khi vao game. |
| P1 | Balance so boss tank/may bay | 5 boss + 5 aircraft co the qua nang/qua kho. |
| P2 | Lam reconnect that | Luu session va gan lai actor khi client vao lai. |
| P2 | Lam UI hien level upgrade ro hon | Shop hien level, nhung co the can panel rieng de de doc. |
