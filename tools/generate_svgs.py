import os
import json

output_dir = r"d:\My\Games\warfront-command\projects\warfront_ppt_ppt169_20260521\svg_output"
os.makedirs(output_dir, exist_ok=True)

slides = [
    {
        "id": "P01",
        "title": "WARFRONT COMMAND",
        "subtitle": "Trải nghiệm Chiến Thuật Thời Gian Thực &amp; AI Pathfinding Đỉnh Cao",
        "content": ["Nhóm thực hiện: Nhóm 2", "Mã nguồn: https://github.com/Chieenslee/Warfront-command"],
        "image": None
    },
    {
        "id": "P02",
        "title": "Cốt truyện & Bối cảnh",
        "subtitle": "Chiến trường rực lửa",
        "content": ["Người chơi hóa thân thành một vị chỉ huy chiến trường, điều khiển các lực lượng quân sự (lính bộ binh, xe tăng) để chiếm đóng cứ điểm và tiêu diệt thế lực thù địch.", "Yêu cầu không chỉ là phản xạ nhanh, mà còn là tư duy chiến thuật để bày binh bố trận và khắc chế hỏa lực địch."],
        "image": None
    },
    {
        "id": "P03",
        "title": "Kiến trúc Tổng quan (Tech Stack)",
        "subtitle": "Xây dựng từ con số không",
        "content": ["Dự án được xây dựng bằng Pygame thuần (không dùng engine có sẵn), tập trung vào việc tự xây dựng vòng lặp game (Game Loop), quản lý trạng thái (State Machine) và hệ thống thực thể (Entities).", "Toàn bộ logic di chuyển, chiến đấu và hiệu ứng được tính toán thủ công từng frame, giúp dễ dàng mở rộng map và logic AI."],
        "image": None
    },
    {
        "id": "P04",
        "title": "Thuật toán Pathfinding A* (Cốt lõi AI)",
        "subtitle": "Sự thông minh của AI",
        "content": ["Ứng dụng: A* giúp bot tự động tìm đường đi ngắn nhất từ điểm hiện tại đến mục tiêu mà không bị kẹt vào chướng ngại vật (cây cối, hào chiến đấu, tường).", "Sử dụng Heuristic khoảng cách Manhattan để tính toán tối ưu, kết hợp hàng đợi ưu tiên (Priority Queue). Điều này mang lại cảm giác 'bot biết đường'."],
        "image": "AStar_Pathfinding.png"
    },
    {
        "id": "P05",
        "title": "Hệ thống Fallback - Thuật toán BFS &amp; DFS",
        "subtitle": "Dự phòng thông minh",
        "content": ["BFS (Breadth-First Search): Khi bot cần tìm vị trí mục tiêu gần nhất có thể đi tới được (ví dụ khi điểm đích thực sự đã bị chặn).", "DFS (Depth-First Search): Sử dụng để quét vùng liên thông, đảm bảo các điểm spawn (khởi điểm) của bot hoặc người chơi luôn nằm trong khu vực hợp lệ (không bị kẹt trong phòng kín)."],
        "image": "BFS_DFS_Fallback.png"
    },
    {
        "id": "P06",
        "title": "AI Chiến thuật - Đánh giá Mục tiêu",
        "subtitle": "Target Scoring",
        "content": ["Bot không chỉ 'bắn mục tiêu gần nhất' một cách ngốc nghếch.", "Hệ thống AI sẽ phân tích dựa trên vai trò: Ví dụ xe tăng bot sẽ ưu tiên bỏ qua lính bộ binh để tập trung hỏa lực vào xe tăng của người chơi (hệ số điểm multiplier cao hơn)."],
        "image": "AI_Target_Scoring.png"
    },
    {
        "id": "P07",
        "title": "AI Chiến thuật - Kỹ năng Né đạn",
        "subtitle": "Dodge Bullet",
        "content": ["Để tăng độ khó và tính thực tế, bot được trang bị khả năng tính toán quỹ đạo đạn đang bay tới (sử dụng vector dot-product) và phản xạ nhảy né vuông góc với hướng đạn (Strafe & Dodge)."],
        "image": "AI_Dodge_Bullets.png"
    },
    {
        "id": "P08",
        "title": "Hệ thống Multiplayer - Kiến trúc Host/Client",
        "subtitle": "Network Sync",
        "content": ["Sử dụng mô hình Server Authority: Host quyết định toàn bộ logic game (va chạm, sát thương), Client gửi Input (phím bấm) và nhận lại State để hiển thị.", "Giao thức UDP + mã hóa nén Zlib giúp đồng bộ nhanh (low latency) trên kết nối mạng internet."],
        "image": "Network_Sync.png"
    },
    {
        "id": "P09",
        "title": "Hiệu ứng Chiến đấu (Combat Effects)",
        "subtitle": "Hình ảnh sinh động",
        "content": ["Giao diện trực quan và sinh động là mấu chốt: Các lớp hiệu ứng như lửa, khói (tank explosion), tia đạn (muzzle flash) và vết máu được lập trình độc lập, tối ưu hiệu năng hiển thị trên màn hình."],
        "image": None
    },
    {
        "id": "P10",
        "title": "Quy trình Kiểm tra Map (Map Validation)",
        "subtitle": "Kiểm soát Chất lượng",
        "content": ["Để đảm bảo chất lượng, dự án có script validation riêng để kiểm tra Map trước khi chạy.", "Đảm bảo kích thước chuẩn, các vị trí spawn không chồng lấp, và xe tăng đi qua được cửa."],
        "image": "Map_Validation.png"
    },
    {
        "id": "P11",
        "title": "Hệ thống Item của Bot",
        "subtitle": "VIP Item Usage",
        "content": ["Bot có khả năng tự đánh giá tình huống để sử dụng Item: hồi máu khi thấp HP, ném lựu đạn khi người chơi trốn sau vật cản."],
        "image": "VIP_Item_Usage.png"
    },
    {
        "id": "P12",
        "title": "Tổng kết & Q&A",
        "subtitle": "Cảm ơn các bạn đã lắng nghe!",
        "content": ["Dự án chứng minh khả năng áp dụng thuật toán kinh điển (A*, BFS, DFS) vào thiết kế trò chơi thực tế, mang lại AI chân thực và thách thức.", "Link GitHub: https://github.com/Chieenslee/Warfront-command", "Nhóm 2 xin cảm ơn!"],
        "image": None
    }
]

def wrap_text(text, max_len=60):
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
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
    <defs>
        <clipPath id="img_clip">
            <rect x="640" y="160" width="600" height="480" rx="16" ry="16"/>
        </clipPath>
        <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000000" flood-opacity="0.4"/>
        </filter>
    </defs>
    <!-- Background -->
    <rect width="1280" height="720" fill="#121212" />

    <!-- Accent Bar -->
    <rect x="0" y="0" width="1280" height="12" fill="#D32F2F" />
    <rect x="0" y="12" width="1280" height="4" fill="#1976D2" />

'''

    title_escaped = slide["title"].replace("&", "&amp;")
    subtitle_escaped = slide["subtitle"].replace("&", "&amp;")

    svg_content += f'''
    <!-- Title Area -->
    <g id="title-group">
        <text x="60" y="100" font-family="Impact, &quot;Microsoft YaHei&quot;, sans-serif" font-size="48" font-weight="bold" fill="#E0E0E0">{title_escaped}</text>
        <text x="60" y="140" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="28" fill="#FBC02D">{subtitle_escaped}</text>
    </g>
'''

    content_x = 60
    content_y = 220
    content_width = 1100 if not slide["image"] else 550
    char_limit = 100 if not slide["image"] else 50

    for paragraph in slide["content"]:
        paragraph = paragraph.replace("&", "&amp;")
        lines = wrap_text(paragraph, char_limit)
        for line in lines:
            svg_content += f'''
    <text x="{content_x}" y="{content_y}" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="24" fill="#9E9E9E">{line}</text>'''
            content_y += 36
        content_y += 20

    if slide["image"]:
        svg_content += f'''
    <g id="image-group" filter="url(#shadow)">
        <rect x="640" y="160" width="600" height="480" rx="16" ry="16" fill="#1E1E1E"/>
        <image x="640" y="160" width="600" height="480" preserveAspectRatio="xMidYMid meet" href="../images/{slide["image"]}" clip-path="url(#img_clip)"/>
    </g>'''

    svg_content += '''
    <!-- Footer -->
    <text x="60" y="680" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="16" fill="#9E9E9E">Warfront Command - Nhóm 2</text>
    <text x="1220" y="680" font-family="&quot;Microsoft YaHei&quot;, Arial, sans-serif" font-size="16" fill="#9E9E9E" text-anchor="end">https://github.com/Chieenslee/Warfront-command</text>
</svg>
'''
    with open(os.path.join(output_dir, f"{slide['id']}.svg"), "w", encoding="utf-8") as f:
        f.write(svg_content)
