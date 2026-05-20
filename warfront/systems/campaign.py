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
        title="Jungle Outpost",
        briefing="A forward radio post has gone dark beyond the tree line.",
        objective="Clear the riverside camp and capture the command point.",
        reward=125,
    ),
    StoryChapter(
        id="chapter_02",
        map_id="trench_line",
        title="Trench Line",
        briefing="Enemy defenses are dug into a maze of trenches and bunkers.",
        objective="Push through the trench network before taking the bunker.",
        reward=175,
    ),
    StoryChapter(
        id="chapter_03",
        map_id="river_bridge",
        title="River Bridge",
        briefing="The bridge is the last armored crossing into the sector.",
        objective="Cross the bridge, destroy armor, and secure the far side.",
        reward=225,
    ),
    StoryChapter(
        id="chapter_04",
        map_id="armored_front",
        title="Armored Front",
        briefing="An enemy armored column is dug in around the rail depot.",
        objective="Buy armor, field a tank, survive bomber runs, and secure the depot.",
        reward=320,
    ),
)

CHAPTERS_BY_MAP: dict[str, StoryChapter] = {chapter.map_id: chapter for chapter in STORY_CHAPTERS}

SHOP_ITEMS: dict[str, ShopItem] = {
    "ak47": ShopItem(
        id="ak47",
        name="AK-47",
        kind="weapon",
        cost=180,
        description="Reliable assault rifle with strong close-range stopping power.",
        max_purchases=1,
    ),
    "ak74": ShopItem(
        id="ak74",
        name="AK-74",
        kind="weapon",
        cost=230,
        description="Faster rifle with better control for moving firefights.",
        max_purchases=1,
    ),
    "stv_380": ShopItem(
        id="stv_380",
        name="STV-380",
        kind="weapon",
        cost=280,
        description="Modern rifle tuned for accuracy and sustained fire.",
        max_purchases=1,
    ),
    "svd": ShopItem(
        id="svd",
        name="SVD",
        kind="weapon",
        cost=310,
        description="Long-range marksman rifle with heavy armor-piercing damage.",
        max_purchases=1,
    ),
    "mosin": ShopItem(
        id="mosin",
        name="Mosin Sniper",
        kind="weapon",
        cost=260,
        description="Slow bolt-action rifle that hits hard at long range.",
        max_purchases=1,
    ),
    "vss": ShopItem(
        id="vss",
        name="VSS",
        kind="weapon",
        cost=340,
        description="Quiet precision rifle for controlled ambushes.",
        max_purchases=1,
    ),
    "tokarev": ShopItem(
        id="tokarev",
        name="Tokarev TT-33",
        kind="weapon",
        cost=120,
        description="Sidearm with fast handling when the rifle runs dry.",
        max_purchases=1,
    ),
    "makarov": ShopItem(
        id="makarov",
        name="Makarov PM",
        kind="weapon",
        cost=95,
        description="Cheap backup pistol with low recoil.",
        max_purchases=1,
    ),
    "medkit": ShopItem(
        id="medkit",
        name="Medkit",
        kind="consumable",
        cost=50,
        description="Restores health during a mission.",
    ),
    "grenade": ShopItem(
        id="grenade",
        name="Grenade",
        kind="consumable",
        cost=70,
        description="Adds one throwable explosive to the next deployment.",
    ),
    "armor": ShopItem(
        id="armor",
        name="Armor Plating",
        kind="upgrade",
        cost=160,
        description="Improves survivability before entering the field.",
        max_purchases=3,
    ),
    "ammo": ShopItem(
        id="ammo",
        name="Ammo Pack",
        kind="consumable",
        cost=45,
        description="Adds reserve ammunition for extended firefights.",
    ),
    "tank": ShopItem(
        id="tank",
        name="Sherman Tank",
        kind="vehicle",
        cost=220,
        description="Deploys a drivable tank at the safe-zone depot.",
        max_purchases=1,
    ),
    "mortar": ShopItem(
        id="mortar",
        name="Mortar Kit",
        kind="support",
        cost=420,
        description="Unlocks the M key artillery strike using grenade ammo.",
        max_purchases=1,
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


__all__ = [
    "CHAPTERS_BY_MAP",
    "SHOP_ITEMS",
    "STORY_CHAPTERS",
    "CampaignState",
    "ShopItem",
    "StoryChapter",
]
