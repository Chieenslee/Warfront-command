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
)

CHAPTERS_BY_MAP: dict[str, StoryChapter] = {chapter.map_id: chapter for chapter in STORY_CHAPTERS}

SHOP_ITEMS: dict[str, ShopItem] = {
    "ak47": ShopItem(
        id="ak47",
        name="AK-47",
        kind="weapon",
        cost=180,
        description="Súng trường tấn công đáng tin cậy với sức sát thương lớn ở tầm gần.",
        max_purchases=1,
    ),
    "ak74": ShopItem(
        id="ak74",
        name="AK-74",
        kind="weapon",
        cost=230,
        description="Súng trường tốc độ cao, dễ kiểm soát khi vừa di chuyển vừa bắn.",
        max_purchases=1,
    ),
    "stv_380": ShopItem(
        id="stv_380",
        name="STV-380",
        kind="weapon",
        cost=280,
        description="Súng trường hiện đại tối ưu cho độ chính xác và duy trì hỏa lực.",
        max_purchases=1,
    ),
    "svd": ShopItem(
        id="svd",
        name="SVD",
        kind="weapon",
        cost=310,
        description="Súng bắn tỉa tầm xa có khả năng xuyên giáp cực mạnh.",
        max_purchases=1,
    ),
    "mosin": ShopItem(
        id="mosin",
        name="Mosin Sniper",
        kind="weapon",
        cost=260,
        description="Súng trường lên đạn thủ công, sát thương rất cao ở cự ly xa.",
        max_purchases=1,
    ),
    "vss": ShopItem(
        id="vss",
        name="VSS",
        kind="weapon",
        cost=340,
        description="Súng trường bắn tỉa giảm thanh dùng cho các cuộc phục kích.",
        max_purchases=1,
    ),
    "tokarev": ShopItem(
        id="tokarev",
        name="Tokarev TT-33",
        kind="weapon",
        cost=120,
        description="Súng lục dự phòng, xử lý nhanh khi súng chính hết đạn.",
        max_purchases=1,
    ),
    "makarov": ShopItem(
        id="makarov",
        name="Makarov PM",
        kind="weapon",
        cost=95,
        description="Súng lục dự phòng giá rẻ với độ giật thấp.",
        max_purchases=1,
    ),
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
        description="Triển khai một xe tăng có thể điều khiển tại cứ điểm an toàn.",
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
        name="Huấn Luyện Xạ Thủ",
        kind="upgrade",
        cost=260,
        description="Tăng mạnh sát thương cơ bản cho mọi loại vũ khí.",
        max_purchases=5,
    ),
    "reload_drill": ShopItem(
        id="reload_drill",
        name="Luyện Tập Nạp Đạn",
        kind="upgrade",
        cost=240,
        description="Cải thiện nhịp độ bắn bằng cách giảm độ trễ vũ khí.",
        max_purchases=4,
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
    credits: int = 0
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
            credits=int(data.get("credits", 99999)),
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
