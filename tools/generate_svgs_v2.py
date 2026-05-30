import os

output_dir = r"d:\My\Games\warfront-command\projects\warfront_ppt_ppt169_20260521\svg_output"
os.makedirs(output_dir, exist_ok=True)

slides = [
    {
        "id": "P01",
        "title": "WARFRONT COMMAND",
        "subtitle": "Bản Thuyết Trình V2 - Đậm Chất Chiến Tranh",
        "content": ["Nhóm thực hiện: Nhóm 2", "Mã nguồn: https://github.com/Chieenslee/Warfront-command"],
        "bg_image": "warfront_cover_1779316358822.png"
    },
    {
        "id": "P02",
        "title": "Cốt truyện & Bối cảnh",
        "subtitle": "Chiến trường rực lửa",
        "content": ["Người chơi hóa thân thành một vị chỉ huy chiến trường, điều khiển lực lượng quân sự chiếm đóng cứ điểm.", "Yêu cầu phản xạ nhanh và tư duy chiến thuật nhạy bén để bày binh bố trận, khắc chế hỏa lực địch."],
        "bg_image": "command_center_1779316407166.png"
    },
    {
        "id": "P03",
        "title": "Kiến trúc Tổng quan",
        "subtitle": "Xây dựng từ con số không",
        "content": ["Dự án được xây dựng bằng Pygame thuần (không dùng engine có sẵn).", "Tập trung tự xây dựng vòng lặp game (Game Loop), quản lý trạng thái (State Machine) và hệ thống thực thể (Entities)."],
        "bg_image": "command_center_1779316407166.png"
    },
    {
        "id": "P04",
        "title": "Thuật toán Pathfinding A*",
        "subtitle": "Cốt lõi của AI Di Chuyển",
        "content": ["A* giúp bot tự động tìm đường đi ngắn nhất từ điểm hiện tại đến mục tiêu mà không bị kẹt chướng ngại vật.", "Sử dụng Heuristic khoảng cách Manhattan kết hợp Priority Queue mang lại cảm giác 'bot biết đường'."],
        "bg_image": "ai_radar_pathfinding_1779316379090.png"
    },
    {
        "id": "P05",
        "title": "Hệ thống Fallback (BFS & DFS)",
        "subtitle": "Dự phòng thông minh",
        "content": ["BFS (Breadth-First Search): Giúp bot tìm vị trí gần nhất có thể đi tới khi điểm đích thực sự bị chặn.", "DFS (Depth-First Search): Sử dụng để quét vùng liên thông, đảm bảo spawn không bị kẹt trong góc kín."],
        "bg_image": "ai_radar_pathfinding_1779316379090.png"
    },
    {
        "id": "P06",
        "title": "AI Chiến Thuật - Target Scoring",
        "subtitle": "Đánh giá mục tiêu",
        "content": ["Bot không bắn mục tiêu ngẫu nhiên.", "Hệ thống AI phân tích dựa trên vai trò: xe tăng bot sẽ ưu tiên bắn xe tăng địch vì có hệ số điểm cao hơn lính bộ binh."],
        "bg_image": "heavy_tank_combat_1779316392604.png"
    },
    {
        "id": "P07",
        "title": "AI Chiến Thuật - Dodge Bullet",
        "subtitle": "Kỹ năng né đạn",
        "content": ["Để tăng độ khó và tính thực tế, bot được trang bị khả năng tính toán quỹ đạo đạn đang bay tới.", "Phản xạ nhảy né (Strafe & Dodge) vuông góc với hướng đạn bằng Vector Dot-Product."],
        "bg_image": "heavy_tank_combat_1779316392604.png"
    },
    {
        "id": "P08",
        "title": "Kiến trúc Host/Client",
        "subtitle": "Hệ thống Multiplayer",
        "content": ["Sử dụng mô hình Server Authority: Host quyết định logic game (va chạm, sát thương).", "Giao thức UDP + mã hóa nén Zlib giúp đồng bộ nhanh (low latency) trên kết nối mạng."],
        "bg_image": "command_center_1779316407166.png"
    },
    {
        "id": "P09",
        "title": "Hiệu ứng Chiến đấu (Combat Effects)",
        "subtitle": "Hình ảnh sinh động",
        "content": ["Giao diện trực quan và sinh động là mấu chốt.", "Các lớp hiệu ứng như lửa, khói (tank explosion), tia đạn (muzzle flash) và vết máu được lập trình tối ưu hiệu năng."],
        "bg_image": "heavy_tank_combat_1779316392604.png"
    },
    {
        "id": "P10",
        "title": "Quy trình Kiểm tra Map",
        "subtitle": "Map Validation",
        "content": ["Để đảm bảo chất lượng, dự án có script validation riêng để kiểm tra Map trước khi chạy.", "Đảm bảo vị trí spawn không chồng lấp và xe tăng đi lọt qua cửa."],
        "bg_image": "ai_radar_pathfinding_1779316379090.png"
    },
    {
        "id": "P11",
        "title": "Hệ thống Item của Bot",
        "subtitle": "VIP Item Usage",
        "content": ["Bot có khả năng tự đánh giá tình huống để sử dụng Item chiến thuật.", "Hồi máu khi thấp HP, hoặc ném lựu đạn khi người chơi đang trốn sau vật cản."],
        "bg_image": "heavy_tank_combat_1779316392604.png"
    },
    {
        "id": "P12",
        "title": "Tổng kết & Q&A",
        "subtitle": "Chiến trường chờ đón bạn!",
        "content": ["Khả năng áp dụng thuật toán kinh điển (A*, BFS, DFS) vào trò chơi thực tế mang lại AI chân thực.", "Link GitHub: https://github.com/Chieenslee/Warfront-command", "Nhóm 2 xin cảm ơn!"],
        "bg_image": "victory_scene_1779316423326.png"
    }
]

def wrap_text(text, max_len=70):
    words = text.split(' ')
    lines = []
    current_line = []
    for w in words:
        if len(' '.join(current_line + [w])) > max_len:
            lines.append(' '.join(current_line))
            current_line = [w]
        else:
            current_line.append(w)
    if current_line:
        lines.append(' '.join(current_line))
    return lines

for slide in slides:
    title_escaped = slide["title"].replace("&", "&amp;")
    subtitle_escaped = slide["subtitle"].replace("&", "&amp;")

    # Overlay styling: Dark gradient box to make text readable over the background
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
    <defs>
        <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.8"/>
        </filter>
        <linearGradient id="overlay_grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#000000" stop-opacity="0.9" />
            <stop offset="60%" stop-color="#000000" stop-opacity="0.7" />
            <stop offset="100%" stop-color="#000000" stop-opacity="0.0" />
        </linearGradient>
    </defs>

    <!-- Full-bleed background image -->
    <image href="../images/{slide["bg_image"]}" x="0" y="0" width="1280" height="720" preserveAspectRatio="xMidYMid slice" />

    <!-- Dark gradient overlay for text readability -->
    <rect x="0" y="0" width="900" height="720" fill="url(#overlay_grad)" />

    <!-- Accent Line -->
    <rect x="0" y="0" width="12" height="720" fill="#D32F2F" />
    <rect x="12" y="0" width="4" height="720" fill="#1976D2" />

    <!-- Title Area -->
    <g id="title-group" filter="url(#shadow)">
        <text x="80" y="140" font-family="Impact, &quot;Microsoft YaHei&quot;, sans-serif" font-size="64" font-weight="bold" fill="#FFFFFF">{title_escaped}</text>
        <text x="80" y="200" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="32" fill="#FBC02D">{subtitle_escaped}</text>
    </g>
'''

    content_x = 80
    content_y = 300
    char_limit = 50

    for paragraph in slide["content"]:
        paragraph = paragraph.replace("&", "&amp;")
        lines = wrap_text(paragraph, char_limit)
        for line in lines:
            svg_content += f'''
    <text x="{content_x}" y="{content_y}" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="28" fill="#E0E0E0" filter="url(#shadow)">{line}</text>'''
            content_y += 42
        content_y += 24

    svg_content += '''
    <!-- Footer -->
    <g filter="url(#shadow)">
        <text x="80" y="680" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="18" fill="#FFFFFF" font-weight="bold">WARFRONT COMMAND | NHÓM 2</text>
        <text x="1240" y="680" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="18" fill="#FFFFFF" font-weight="bold" text-anchor="end">https://github.com/Chieenslee/Warfront-command</text>
    </g>
</svg>
'''
    with open(os.path.join(output_dir, f"{slide['id']}.svg"), "w", encoding="utf-8") as f:
        f.write(svg_content)
