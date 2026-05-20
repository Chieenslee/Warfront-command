import random
import math

def clear_spawns(grid, spawns):
    for key, val in spawns.items():
        if isinstance(val, tuple):
            val = [val]
        for (x, y) in val:
            if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                if grid[y][x] not in ['.', 'r', 'S']:
                    grid[y][x] = '.'

def build_jungle_mega():
    w, h = 112, 84
    # Fill with .
    grid = [['.' for _ in range(w)] for _ in range(h)]
    
    # 1. Generate dense forests (perlin-like blobs of #)
    for _ in range(120):
        cx, cy = random.randint(0, w-1), random.randint(0, h-1)
        radius = random.randint(3, 8)
        for y in range(max(0, cy-radius), min(h, cy+radius)):
            for x in range(max(0, cx-radius), min(w, cx+radius)):
                if (x-cx)**2 + (y-cy)**2 <= radius**2:
                    grid[y][x] = '#'
                    
    # 2. Carve some roads 'r' connecting major points
    def carve_path(x1, y1, x2, y2, thickness=3):
        steps = int(math.hypot(x2-x1, y2-y1))
        for i in range(steps):
            t = i / max(1, steps)
            px = int(x1 + (x2-x1)*t)
            py = int(y1 + (y2-y1)*t)
            for dy in range(-thickness, thickness+1):
                for dx in range(-thickness, thickness+1):
                    if 0 <= py+dy < h and 0 <= px+dx < w:
                        grid[py+dy][px+dx] = 'r'
                        
    carve_path(10, h-10, w//2, h//2, 4)
    carve_path(w-10, h-10, w//2, h//2, 4)
    carve_path(w//2, h//2, w//2, 10, 4)
    carve_path(w//2, h//2, 10, 20, 3)
    carve_path(w//2, h//2, w-10, 20, 3)

    # 3. Create the Safe Zone at the bottom center (size: 20x10)
    sx, sy = w//2 - 10, h - 15
    for y in range(sy, sy+10):
        for x in range(sx, sx+20):
            if y == sy or y == sy+9 or x == sx or x == sx+19:
                grid[y][x] = 'S'
            else:
                grid[y][x] = '.'
    
    # Add Door
    grid[sy][w//2 - 2] = 'D'
    grid[sy][w//2 - 1] = 'D'
    grid[sy][w//2] = 'D'
    grid[sy][w//2 + 1] = 'D'

    # Add single Medic and Ammo
    grid[sy+5][sx+5] = 'M'
    grid[sy+5][sx+14] = 'A'

    # Ensure borders are trees
    for x in range(w):
        grid[0][x] = '#'
        grid[h-1][x] = '#'
    for y in range(h):
        grid[y][0] = '#'
        grid[y][w-1] = '#'
        
    spawns = {
        "player": (w//2, h - 10),
        "enemies": [
            (w//2, 10), (10, 20), (w-10, 20), (w//2 - 20, h//2 - 10), (w//2 + 20, h//2 - 10),
            (10, 40), (w-10, 40)
        ],
        "tanks": [(w//2, 15), (20, 30), (w-20, 30)]
    }
    clear_spawns(grid, spawns)
        
    rows = ["".join(row) for row in grid]
    
    return {
        "title": "MEGA: Tiền Đồn Rừng Sâu",
        "briefing": "Khu rừng khổng lồ (112x84). Nhiều đường mòn rẽ nhánh và các lùm cây dày đặc. Căn cứ đã được quy hoạch lại với 1 trạm đạn/máu.",
        "rows": rows,
        "spawns": spawns,
        "safe_zones": [
            {"rect": (sx, sy, 20, 10)}
        ]
    }

def build_trench_mega():
    w, h = 112, 84
    grid = [['.' for _ in range(w)] for _ in range(h)]
    
    # Add random craters 'r'
    for _ in range(80):
        cx, cy = random.randint(0, w-1), random.randint(0, h//2 + 20)
        radius = random.randint(2, 6)
        for y in range(max(0, cy-radius), min(h, cy+radius)):
            for x in range(max(0, cx-radius), min(w, cx+radius)):
                if (x-cx)**2 + (y-cy)**2 <= radius**2:
                    grid[y][x] = 'r'
                    
    # Generate zigzag trenches
    def draw_trench(start_y, segments):
        points = [(0, start_y)]
        px, py = 0, start_y
        for _ in range(segments):
            px += w // segments
            py = start_y + random.randint(-15, 15)
            points.append((px, py))
            
        for i in range(len(points)-1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            steps = int(math.hypot(x2-x1, y2-y1))
            for j in range(steps):
                t = j / max(1, steps)
                cx = int(x1 + (x2-x1)*t)
                cy = int(y1 + (y2-y1)*t)
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if 0 <= cy+dy < h and 0 <= cx+dx < w:
                            grid[cy+dy][cx+dx] = 't'

    draw_trench(30, 8)
    draw_trench(55, 6)

    # Some bunkers
    for _ in range(15):
        bx, by = random.randint(10, w-10), random.randint(10, 60)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if max(abs(dx), abs(dy)) == 3:
                    grid[by+dy][bx+dx] = '#'
                else:
                    grid[by+dy][bx+dx] = '.'

    # Safe Zone
    sx, sy = w//2 - 12, h - 12
    for y in range(sy, sy+8):
        for x in range(sx, sx+24):
            if y == sy or y == sy+7 or x == sx or x == sx+23:
                grid[y][x] = 'S'
            else:
                grid[y][x] = '.'
                
    grid[sy][w//2 - 2] = 'D'
    grid[sy][w//2 - 1] = 'D'
    grid[sy][w//2] = 'D'
    grid[sy][w//2 + 1] = 'D'
    grid[sy+4][sx+6] = 'M'
    grid[sy+4][sx+18] = 'A'

    # Boundaries
    for x in range(w): grid[0][x] = '#'
    for y in range(h): grid[y][0] = '#'; grid[y][w-1] = '#'
    
    spawns = {
        "player": (w//2, h - 8),
        "enemies": [(20, 20), (w//2, 10), (w-20, 20), (30, 40), (w-30, 40)],
        "tanks": [(20, 15), (w-20, 15), (w//2, 25)]
    }
    clear_spawns(grid, spawns)
    
    return {
        "title": "MEGA: Trận Địa Chiến Hào",
        "briefing": "Gấp 16 lần diện tích cũ. Rất nhiều chiến hào và bong-ke kiên cố. Cẩn thận các ổ phục kích trong hố bom.",
        "rows": ["".join(row) for row in grid],
        "spawns": spawns,
        "safe_zones": [{"rect": (sx, sy, 24, 8)}]
    }

def build_river_mega():
    w, h = 112, 84
    grid = [['.' for _ in range(w)] for _ in range(h)]
    
    # 1. Draw River
    for y in range(h):
        center_x = int(w//2 + math.sin(y/10.0) * 10)
        for x in range(center_x - 15, center_x + 15):
            if 0 <= x < w:
                grid[y][x] = 'w'
                
    # 2. Draw Bridges
    bridge_ys = [20, 40, 60]
    for by in bridge_ys:
        center_x = int(w//2 + math.sin(by/10.0) * 10)
        for dy in range(-3, 4):
            for x in range(center_x - 16, center_x + 16):
                if 0 <= x < w:
                    grid[by+dy][x] = 'r'

    # 3. Add some bushes
    for _ in range(80):
        cx, cy = random.randint(0, w-1), random.randint(0, h-1)
        if grid[cy][cx] != 'w' and grid[cy][cx] != 'r':
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if 0 <= cy+dy < h and 0 <= cx+dx < w and grid[cy+dy][cx+dx] == '.':
                        grid[cy+dy][cx+dx] = '#' if random.random() < 0.6 else 'g'

    # Safe Zone
    sx, sy = 5, h - 20
    for y in range(sy, sy+15):
        for x in range(sx, sx+25):
            if y == sy or y == sy+14 or x == sx or x == sx+24:
                grid[y][x] = 'S'
            else:
                grid[y][x] = '.'
    
    grid[sy][sx+10:sx+15] = ['D']*5
    grid[sy+5][sx+6] = 'M'
    grid[sy+5][sx+18] = 'A'

    for x in range(w): grid[0][x] = '#'
    for y in range(h): grid[y][0] = '#'; grid[y][w-1] = '#'

    spawns = {
        "player": (15, h - 12),
        "enemies": [(w-20, 20), (w-20, 50), (w-10, 70), (w//2, 10)],
        "tanks": [(w-30, 20), (w-30, 60), (w-15, 40)]
    }
    clear_spawns(grid, spawns)

    return {
        "title": "MEGA: Cầu Huyết Mạch",
        "briefing": "Con sông lớn (112x84) với 3 cây cầu bắc ngang. Một chiến trường hoàn hảo cho xe tăng và bộ binh.",
        "rows": ["".join(row) for row in grid],
        "spawns": spawns,
        "safe_zones": [{"rect": (sx, sy, 25, 15)}]
    }

def build_armored_mega():
    w, h = 168, 104
    grid = [['r' for _ in range(w)] for _ in range(h)]
    
    # Generate city blocks
    for by in range(10, h-25, 18):
        for bx in range(10, w-10, 24):
            if random.random() < 0.8:
                for dy in range(12):
                    for dx in range(16):
                        if by+dy < h and bx+dx < w:
                            grid[by+dy][bx+dx] = '#'
                            if random.random() < 0.1:
                                grid[by+dy][bx+dx] = '.' # ruined building

    # Safe Zone
    sx, sy = w//2 - 15, h - 20
    for y in range(sy, sy+15):
        for x in range(sx, sx+30):
            if y == sy or y == sy+14 or x == sx or x == sx+29:
                grid[y][x] = 'S'
            else:
                grid[y][x] = '.'
    
    grid[sy][w//2 - 4 : w//2 + 4] = ['D']*8
    grid[sy+7][sx+8] = 'M'
    grid[sy+7][sx+22] = 'A'

    for x in range(w): grid[0][x] = '#'; grid[h-1][x] = '#'
    for y in range(h): grid[y][0] = '#'; grid[y][w-1] = '#'

    spawns = {
        "player": (w//2, h - 12),
        "enemies": [(30, 20), (w//2, 20), (w-30, 20), (20, 50), (w-20, 50)],
        "tanks": [(40, 30), (w//2, 30), (w-40, 30), (50, 60), (w-50, 60), (w//2, 10)]
    }
    clear_spawns(grid, spawns)

    return {
        "title": "MEGA: Tuyến Đầu Bọc Thép",
        "briefing": "Siêu chiến trường (168x104) dành riêng cho xe tăng bọc thép. Các khu nhà quy hoạch dạng ô cờ.",
        "rows": ["".join(row) for row in grid],
        "spawns": spawns,
        "safe_zones": [{"rect": (sx, sy, 30, 15)}]
    }

def main():
    mega_maps = {
        "jungle_outpost_mega": build_jungle_mega(),
        "trench_line_mega": build_trench_mega(),
        "river_bridge_mega": build_river_mega(),
        "armored_front_mega": build_armored_mega(),
    }
    
    with open("tools/mega_maps_output.py", "w", encoding="utf-8") as f:
        f.write("MEGA_MAPS = {\n")
        for map_id, map_data in mega_maps.items():
            f.write(f'    "{map_id}": {{\n')
            for k, v in map_data.items():
                if k == "rows":
                    f.write(f'        "{k}": [\n')
                    for row in v:
                        f.write(f'            "{row}",\n')
                    f.write(f'        ],\n')
                elif isinstance(v, dict) or isinstance(v, list) or isinstance(v, tuple):
                    f.write(f'        "{k}": {repr(v)},\n')
                else:
                    f.write(f'        "{k}": {repr(v)},\n')
            f.write(f'    }},\n')
        f.write("}\n")
    print("Successfully generated mega_maps_output.py with procedural algorithms!")

if __name__ == "__main__":
    main()
