from enum import IntEnum

NUMBER_OF_INGREDIENTS = 58
NUMBER_OF_SALTS = 5
_ingredient_prices = [
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

_ingredient_names = [
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

_salt_names = [
    "Void Salt",
    "Moon Salt",
    "Sun Salt",
    "Life Salt",
    "Philosopher's Salt",
]

# TODO: _ingredientGrowPosition


class IngredientElement(IntEnum):
    Air = 0
    Magic = 1
    Water = 2
    Life = 3
    Earth = 4
    Death = 5
    Fire = 6
    Explosion = 7
    Universal = 8


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
        return _ingredient_prices[self]

    @property
    def ingredient_name(self) -> str:
        return _ingredient_names[self]

    @property
    def ingredient_element(self) -> IngredientElement:
        return IngredientElement(self // 7)


class Salts(IntEnum):

    Void = 0
    Moon = 1
    Sun = 2
    Life = 3
    Philosopher = 4

    __doc__ = "Enum for salt names."

    @property
    def salt_name(self) -> str:
        return _salt_names[self]


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


if __name__ == "__main__":
    # print([1, 2, 3, 4][Ingredients.Windbloom + 2])
    # print(Ingredients.fromIndex(0))
    print(Ingredients(2).ingredient_name)
    print(Ingredients["Windbloom"].ingredient_element.name)
