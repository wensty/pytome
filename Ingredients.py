from enum import IntEnum
from collections import namedtuple

NUMBER_OF_INGREDIENTS = 58
NUMBER_OF_SALTS = 5
_ingredientPrices = [
    38.8,
    83.2,
    88.8,
    99.6,
    104.0,
    144.0,
    443.2,
    42.4,
    70.0,
    73.6,
    83.2,
    132.0,
    152.4,
    471.2,
    32.8,
    46.8,
    51.6,
    77.6,
    78.8,
    105.6,
    375.2,
    24.0,
    36.0,
    50.4,
    52.4,
    77.2,
    86.4,
    269.2,
    26.8,
    33.6,
    36.0,
    46.0,
    76.8,
    86.4,
    307.2,
    30.0,
    42.0,
    52.4,
    62.4,
    72.8,
    126.0,
    336.8,
    32.8,
    46.8,
    57.6,
    70.4,
    106.4,
    116.8,
    404.0,
    42.4,
    65.2,
    73.6,
    75.6,
    83.2,
    113.2,
    375.2,
    443.2,
    1438.4,
]

_ingredientNames = [
    "Windbloom",
    "Featherbloom",
    "Foggy Parasol",
    "Fluffbloom",
    "Whirlweed",
    "Phantom Skirt",
    "Cloud Crystal",
    "Witch Mushroom",
    "Thunder Thistle",
    "Dream Beet",
    "Shadow Chanterelle",
    "Spellbloom",
    "Mageberry",
    "Arcane Crystal",
    "Waterbloom",
    "Icefruit",
    "Tangleweed",
    "Coldleaf",
    "Kraken Mushroom",
    "Watercap",
    "Frost Sapphire",
    "Lifeleaf",
    "Goodberry",
    "Druid's Rosemary",
    "Moss Shroom",
    "Healers Heather",
    "Evergreen Fern",
    "Life Crystal",
    "Terraria",
    "Dryad's Saddle",
    "Poopshroom",
    "Weirdshroom",
    "Goldthorn",
    "Mudshroom",
    "Earth Pyrite",
    "Stink Mushroom",
    "Goblin Shroom",
    "Marshroom",
    "Hairy Banana",
    "Thornstick",
    "Grave Truffle",
    "Plague Stibnite",
    "Firebell",
    "Sulphur Shelf",
    "Lavaroot",
    "Flameweed",
    "Magma Morel",
    "Dragon Pepper",
    "Fire Citrine",
    "Mad Mushroom",
    "Bloodthorn",
    "Terror Bud",
    "Grasping Root",
    "Boombloom",
    "Lust Mushroom",
    "Blood Ruby",
    "Rainbow Cap",
    "Fable Bismuth",
]

# TODO: _ingredientGrowPosition


class Ingredients(IntEnum):
    Windbloom = 0
    Featherbloom = 1
    FoggyParasol = 2
    Fluffbloom = 3
    Whirlweed = 4
    PhantomSkirt = 5
    CloudCrystal = 6
    WitchMushroom = 7
    ThunderThistle = 8
    DreamBeet = 9
    ShadowChanterelle = 10
    Spellbloom = 11
    Mageberry = 12
    ArcaneCrystal = 13
    Waterbloom = 14
    Icefruit = 15
    Tangleweed = 16
    Coldleaf = 17
    KrakenMushroom = 18
    Watercap = 19
    FrostSapphire = 20
    Lifeleaf = 21
    Goodberry = 22
    DruidsRosemary = 23
    MossShroom = 24
    HealersHeather = 25
    EvergreenFern = 26
    LifeCrystal = 27
    Terraria = 28
    DryadsSaddle = 29
    Poopshroom = 30
    Weirdshroom = 31
    Goldthorn = 32
    Mudshroom = 33
    EarthPyrite = 34
    StinkMushroom = 35
    GoblinShroom = 36
    Marshroom = 37
    HairyBanana = 38
    Thornstick = 39
    GraveTruffle = 40
    PlagueStibnite = 41
    Firebell = 42
    SulphurShelf = 43
    Lavaroot = 44
    Flameweed = 45
    MagmaMorel = 46
    DragonPepper = 47
    FireCitrine = 48
    MadMushroom = 49
    Bloodthorn = 50
    TerrorBud = 51
    GraspingRoot = 52
    Boombloom = 53
    LustMushroom = 54
    BloodRuby = 55
    RainbowCap = 56
    FableBismuth = 57

    __doc__ = "Enumeration type for ingredients."

    @property
    def price(self) -> float:
        return _ingredientPrices[self]

    @property
    def name(self) -> str:
        return _ingredientNames[self]


class Salts(IntEnum):

    Void = 0
    Moon = 1
    Sun = 2
    Life = 3
    Philosopher = 4

    __doc__ = "Enum for salt names."


IngredientsProperties = namedtuple(
    "IngredientsProperties",
    ["name", "price", "location"],
)

"""
    Grow positions:
    Floor: 0
    CaveFloor: 1
    CaveCeiling: 2
    Trunk: 3
    Pond: 4
    Root: 5
    Grotto: 6
"""

# ingredientProperties = [
#     IngredientsProperties("Windbloom", 38.8, None),
#     IngredientsProperties("Featherbloom", 83.2, None),
#     IngredientsProperties("Foggy Parasol", 88.8, None),
#     IngredientsProperties("Fluffbloom", 99.6, None),
#     IngredientsProperties("Whirlweed", 104, None),
#     IngredientsProperties("Phantom Skirt", 144, None),
#     IngredientsProperties("Cloud Crystal", 443.2, None),
#     IngredientsProperties("Witch Mushroom", 42.4, None),
#     IngredientsProperties("Thunder Thistle", 70, None),
#     IngredientsProperties("Dream Beet", 73.6, None),
#     IngredientsProperties("Shadow Chanterelle", 83.2, None),
#     IngredientsProperties("Spellbloom", 132, None),
#     IngredientsProperties("Mageberry", 152.4, None),
#     IngredientsProperties("Arcane Crystal", 471.2, None),
#     IngredientsProperties("Waterbloom", 32.8, None),
#     IngredientsProperties("Icefruit", 46.8, None),
#     IngredientsProperties("Tangleweed", 51.6, None),
#     IngredientsProperties("Coldleaf", 77.6, None),
#     IngredientsProperties("Kraken Mushroom", 78.8, None),
#     IngredientsProperties("Watercap", 105.6, None),
#     IngredientsProperties("Frost Sapphire", 375.2, None),
#     IngredientsProperties("Lifeleaf", 24, None),
#     IngredientsProperties("Goodberry", 36, None),
#     IngredientsProperties("Druids Rosemary", 50.4, None),
#     IngredientsProperties("Moss Shroom", 52.4, None),
#     IngredientsProperties("Healers Heather", 77.2, None),
#     IngredientsProperties("Evergreen Fern", 86.4, None),
#     IngredientsProperties("Life Crystal", 269.2, None),
#     IngredientsProperties("Terraria", 26.8, None),
#     IngredientsProperties("Dryad's Saddle", 33.6, None),
#     IngredientsProperties("Poopshroom", 36, None),
#     IngredientsProperties("Weirdshroom", 46, None),
#     IngredientsProperties("Goldthorn", 76.8, None),
#     IngredientsProperties("Mudshroom", 86.4, None),
#     IngredientsProperties("Earth Pyrite", 307.2, None),
#     IngredientsProperties("Stink Mushroom", 30, None),
#     IngredientsProperties("Goblin Shroom", 42, None),
#     IngredientsProperties("Marshroom", 52.4, None),
#     IngredientsProperties("Hairy Banana", 62.4, None),
#     IngredientsProperties("Thornstick", 72.8, None),
#     IngredientsProperties("Grave Truffle", 126, None),
#     IngredientsProperties("Plague Stibnite", 336.8, None),
#     IngredientsProperties("Firebell", 32.8, None),
#     IngredientsProperties("Sulphur Shelf", 46.8, None),
#     IngredientsProperties("Lavaroot", 57.6, None),
#     IngredientsProperties("Flameweed", 70.4, None),
#     IngredientsProperties("Magma Morel", 106.4, None),
#     IngredientsProperties("Dragon Pepper", 116.8, None),
#     IngredientsProperties("Fire Citrine", 404, None),
#     IngredientsProperties("Mad Mushroom", 42.4, None),
#     IngredientsProperties("Bloodthorn", 65.2, None),
#     IngredientsProperties("Terror Bud", 73.6, None),
#     IngredientsProperties("Grasping Root", 75.6, None),
#     IngredientsProperties("Boombloom", 83.2, None),
#     IngredientsProperties("Lust Mushroom", 113.2, None),
#     IngredientsProperties("Blood Ruby", 375.2, None),
#     IngredientsProperties("Rainbow Cap", 443.2, None),
#     IngredientsProperties("Fable Bismuth", 1438.4, None),
# ]

# # salt prices cached from tome at 5/6/2025
# PresumedSaltIngredientPrice: list[float] = [
#     1 / 2145.6,
#     1 / 966.6,
#     1 / 1248.2,
#     1 / 189.0,
#     1 / 97.5,
# ]
# PresumedSaltCostPrice: list[float] = [0.09, 0.23, 0.18, 1.24, 2.87]


if __name__ == "__main__":
    # print([1, 2, 3, 4][Ingredients.Windbloom + 2])
    # print(Ingredients.fromIndex(0))
    print(Ingredients(2).name)
    print(Ingredients["Windbloom"].name)
    pass
