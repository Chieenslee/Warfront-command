from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StoryChapter:
    id: str
    map_id: str
    title: str
    briefing: str
    objective: str
    reward: int
    dialogues: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ShopItem:
    id: str
    name: str
    kind: str
    cost: int
    description: str
    max_purchases: int | None = None


STORY_CHAPTERS: tuple[StoryChapter, ...] = (
    StoryChapter(
        id="chapter_01",
        map_id="jungle_outpost",
        title="Tiền Đồn Rừng Rậm",
        briefing="Một trạm vô tuyến tiền phương đã mất liên lạc bên kia bìa rừng.",
        objective="Quét sạch doanh trại ven sông và chiếm lấy điểm chỉ huy.",
        reward=125,
        dialogues=(
            ("CHỈ HUY", "Đội Tiên Phong nghe rõ trả lời. Chúng ta đã mất liên lạc với trạm vô tuyến tiền phương cách đây 3 giờ."),
            ("TIÊN PHONG", "Rõ, thưa Chỉ huy. Chúng tôi đang tiếp cận bìa rừng. Tầm nhìn rất hạn chế."),
            ("CHỈ HUY", "Hãy cẩn thận. Trinh sát phát hiện có biến động dọc bờ sông. Nhiệm vụ: quét sạch trại địch và chiếm lại trạm."),
            ("TIÊN PHONG", "Đã rõ. Sẵn sàng nổ súng. Chúng tôi đang tiến vào."),
        ),
    ),
    StoryChapter(
        id="chapter_02",
        map_id="trench_line",
        title="Chiến Hào Tử Thần",
        briefing="Tuyến phòng thủ của địch được đào sâu thành một mê cung chiến hào và lô cốt.",
        objective="Vượt qua mạng lưới chiến hào và đánh chiếm lô cốt chỉ huy.",
        reward=175,
        dialogues=(
            ("TIÊN PHONG", "Chỉ huy, khu vực bờ sông đã dọn dẹp xong, nhưng phía trước chúng đào hầm hào rất sâu. Một mạng lưới chiến hào khổng lồ."),
            ("CHỈ HUY", "Đó là tuyến phòng thủ bảo vệ cây cầu chính của khu vực. Các cậu phải chọc thủng nó, Tiên Phong."),
            ("TIÊN PHONG", "Chúng có cả xe tăng hỗ trợ và súng máy hạng nặng bao phủ toàn bộ bãi lầy."),
            ("CHỈ HUY", "Lợi dụng chiến hào làm nơi ẩn nấp. Cố gắng tiến lên và dập tắt hỏa lực của cái lô cốt đó. Đừng dừng lại."),
        ),
    ),
    StoryChapter(
        id="chapter_03",
        map_id="river_bridge",
        title="Cây Cầu Máu",
        briefing="Cây cầu là con đường duy nhất để xe tăng của chúng ta tiến vào trung tâm.",
        objective="Vượt cầu, tiêu diệt xe bọc thép địch và kiểm soát bờ bên kia.",
        reward=225,
        dialogues=(
            ("CHỈ HUY", "Làm tốt lắm. Bây giờ mới là thử thách thực sự. Phía trước là Cây Cầu Huyết Mạch."),
            ("TIÊN PHONG", "Chúng tôi thấy rồi. Chúng đã gia cố bờ bên kia. Có vẻ như nhiều sư đoàn xe tăng đang trấn giữ cầu."),
            ("CHỈ HUY", "Nếu không chiếm được cây cầu đó nguyên vẹn, lực lượng tăng thiết giáp của ta sẽ không thể tiến lên."),
            ("TIÊN PHONG", "Sẽ là một cỗ máy xay thịt đấy, Chỉ huy. Nhưng chúng tôi sẽ xuyên thủng phòng tuyến của chúng."),
        ),
    ),
    StoryChapter(
        id="chapter_04",
        map_id="armored_front",
        title="Tuyến Đầu Bọc Thép",
        briefing="Lực lượng xe tăng hùng hậu của địch đang cố thủ quanh ga tàu.",
        objective="Trang bị xe tăng, sống sót qua các đợt thả bom và chiếm lấy ga tàu.",
        reward=320,
        dialogues=(
            ("CHỈ HUY", "Tiên Phong, các cậu đã đến được ga tàu cuối cùng. Đây là trái tim của hệ thống hậu cần thiết giáp địch."),
            ("TIÊN PHONG", "Hoạt động của địch rất dày đặc. Máy bay ném bom trên trời, xe tăng đang lăn bánh. Chúng đã biết chúng tôi ở đây."),
            ("CHỈ HUY", "Bộ chỉ huy đã cấp cho đội của cậu một chiếc xe tăng Sherman. Các cậu sẽ cần vũ khí hạng nặng cho trận chiến sinh tử này."),
            ("TIÊN PHONG", "Đã nhận lệnh. Chúng tôi sẽ đánh một trận khô máu. Kết thúc chuyện này thôi!"),
        ),
    ),
    StoryChapter(
        id="chapter_05",
        map_id="jungle_outpost_mega",
        title="MEGA: Tiền Đồn Rừng Sâu",
        briefing="Bản đồ được mở rộng gấp 16 lần. Rừng rậm hơn, nhiều con đường nhỏ tuần tra hơn. Tăng số lượng kẻ địch và xe tăng, bổ sung nhiều trạm đạn/máu rải rác.",
        objective="Sống sót trong tiền đồn khổng lồ.",
        reward=500,
        dialogues=(
            ("CHỈ HUY", "Tien Phong, tin hieu cu o khu rung da bien mat. Ban do cu khong con dung nua."),
            ("TRINH SAT", "Chung toi thay nhieu cum trai moi, duong tuan tra dan cheo nhau va dau vet xe boc thep trong rung."),
            ("CHỈ HUY", "Muc tieu la mo cong an toan, giu doi hinh bot dong minh gan nhau va danh sap tram chi huy sau cung."),
            ("TIEN PHONG", "Da ro. Chung toi se tien cham, lay tiep te tren duong va khong de rung nuot mat doi hinh."),
        ),
    ),
    StoryChapter(
        id="chapter_06",
        map_id="trench_line_mega",
        title="MEGA: Trận Địa Chiến Hào",
        briefing="Bản đồ mở rộng khổng lồ với các chiến hào chằng chịt.",
        objective="Xuyên thủng phòng tuyến khổng lồ.",
        reward=500,
        dialogues=(
            ("CHỈ HUY", "Phia truoc la toan bo mang chien hao cua dich. Khong con la mot tuyen phong thu don le nua."),
            ("TRINH SAT", "May bay dich quay vong tren dau, xe tang nang nam sau cac lop hao."),
            ("CHỈ HUY", "Dung nuoc, hao va vat can de cat doi hoa luc. Neu lao thang vao giua, doi hinh se bi xoa sach."),
            ("TIEN PHONG", "Da nhan lenh. Chung toi se chiem tung nut giao thong va mo loi cho luc luong chinh."),
        ),
    ),
    StoryChapter(
        id="chapter_07",
        map_id="river_bridge_mega",
        title="MEGA: Cầu Huyết Mạch",
        briefing="Một vùng đồng bằng rộng lớn với nhiều cây cầu.",
        objective="Kiểm soát toàn bộ mạng lưới cầu.",
        reward=500,
        dialogues=(
            ("CHỈ HUY", "Tat ca duong tiep van dang do ve cau Huyet Mach. Neu mat cau, chien dich ket thuc."),
            ("TRINH SAT", "Song chia nhanh thanh nhieu cum. Dan co the ban qua nuoc, nhung nguoi va xe van bi chan lai."),
            ("CHỈ HUY", "Tan dung tam ban AK va phao kich. Uu tien ha may bay truoc khi tien vao diem chiem."),
            ("TIEN PHONG", "Ro. Chung toi se khoa tung dau cau va khong de xe tang dich vuot qua."),
        ),
    ),
    StoryChapter(
        id="chapter_08",
        map_id="armored_front_mega",
        title="MEGA: Tuyến Đầu Bọc Thép",
        briefing="Siêu chiến trường dành cho xe tăng.",
        objective="Chiến đấu trong siêu chiến trường xe tăng.",
        reward=800,
        dialogues=(
            ("CHỈ HUY", "Day la tuyen cuoi. Dich dua toan bo thiet giap nang va may bay nem bom vao khu nha ga."),
            ("TRINH SAT", "Nhieu kho tiep te nam trong cac khoang cong su. Tat ca da duoc danh dau tren ban do."),
            ("CHỈ HUY", "Bot dong minh va xe tang cua ta phai duoc nang cap truoc khi vao. Boss tank se khong nga nhanh dau."),
            ("TIEN PHONG", "Da ro. Neu chung muon giu tuyen dau nay, chung se phai tra bang tung chiec xe tang."),
        ),
    ),
)

CHAPTERS_BY_MAP: dict[str, StoryChapter] = {chapter.map_id: chapter for chapter in STORY_CHAPTERS}

SHOP_ITEMS: dict[str, ShopItem] = {
    "medkit": ShopItem(
        id="medkit",
        name="Túi Cứu Thương",
        kind="consumable",
        cost=50,
        description="Hồi phục một lượng lớn máu cho người chơi trong trận.",
    ),
    "grenade": ShopItem(
        id="grenade",
        name="Lựu Đạn Nổ",
        kind="consumable",
        cost=70,
        description="Thêm một lựu đạn gây sát thương diện rộng vào kho đồ khi triển khai.",
    ),
    "armor": ShopItem(
        id="armor",
        name="Giáp Chống Đạn",
        kind="upgrade",
        cost=160,
        description="Tăng cường sức chịu đựng và máu tối đa một cách vĩnh viễn.",
        max_purchases=5,
    ),
    "ammo": ShopItem(
        id="ammo",
        name="Hộp Tiếp Đạn",
        kind="consumable",
        cost=45,
        description="Bổ sung cơ số đạn lớn cho các cuộc đọ súng kéo dài.",
    ),
    "tank": ShopItem(
        id="tank",
        name="Xe Tăng Sherman",
        kind="vehicle",
        cost=220,
        description="Bật/tắt xe tăng hỗ trợ. Tắt sẽ hoàn lại đúng số credits đã mua.",
        max_purchases=1,
    ),
    "mortar": ShopItem(
        id="mortar",
        name="Pháo Kích Hỗ Trợ",
        kind="support",
        cost=420,
        description="Mở khóa phím M để gọi pháo kích (tiêu tốn lựu đạn).",
        max_purchases=1,
    ),
    "weapon_training": ShopItem(
        id="weapon_training",
        name="Nâng Cấp AK",
        kind="upgrade",
        cost=260,
        description="9 cấp sát thương cho AK. Cấp 9 đạt 200 damage.",
        max_purchases=9,
    ),
    "ally_training": ShopItem(
        id="ally_training",
        name="Nâng Cấp Bot Đồng Minh",
        kind="upgrade",
        cost=260,
        description="9 cấp sát thương cho bot đồng minh. Cấp 9 đạt 200 damage.",
        max_purchases=9,
    ),
    "field_pouches": ShopItem(
        id="field_pouches",
        name="Túi Đựng Đạn Dã Chiến",
        kind="upgrade",
        cost=190,
        description="Tăng số lượng đạn, túi cứu thương và lựu đạn tối đa khi triển khai.",
        max_purchases=3,
    ),
}


@dataclass
class CampaignState:
    credits: int = 500
    unlocked_maps: set[str] = field(default_factory=lambda: {"jungle_outpost"})
    purchases: dict[str, int] = field(default_factory=dict)

    def can_buy(self, item_id: str) -> bool:
        item = SHOP_ITEMS.get(item_id)
        if item is None or self.credits < item.cost:
            return False

        if item.max_purchases is None:
            return True

        return self.purchases.get(item_id, 0) < item.max_purchases

    def buy(self, item_id: str) -> bool:
        if not self.can_buy(item_id):
            return False

        item = SHOP_ITEMS[item_id]
        self.credits -= item.cost
        self.purchases[item_id] = self.purchases.get(item_id, 0) + 1
        return True

    def to_dict(self) -> dict:
        return {
            "credits": self.credits,
            "unlocked_maps": sorted(self.unlocked_maps),
            "purchases": dict(self.purchases),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CampaignState":
        state = cls(
            credits=int(data.get("credits", 500)),
            unlocked_maps=set(data.get("unlocked_maps", ["jungle_outpost"])),
            purchases={str(key): int(value) for key, value in data.get("purchases", {}).items()},
        )
        state.unlocked_maps.add("jungle_outpost")
        return state

    def unlock_next_after(self, map_id: str) -> str | None:
        order = [chapter.map_id for chapter in STORY_CHAPTERS]
        if map_id not in order:
            return None
        index = order.index(map_id)
        if index + 1 >= len(order):
            return None
        next_map = order[index + 1]
        self.unlocked_maps.add(next_map)
        return next_map


__all__ = [
    "CHAPTERS_BY_MAP",
    "SHOP_ITEMS",
    "STORY_CHAPTERS",
    "CampaignState",
    "ShopItem",
    "StoryChapter",
]
