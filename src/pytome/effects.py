from enum import IntEnum
from typing import Union

NUMBER_OF_EFFECTS = 41

_effect_base_prices = [
    100,
    130,
    200,
    245,
    290,
    330,
    365,
    435,
    460,
    480,
    495,
    495,
    515,
    545,
    615,
    640,
    645,
    660,
    685,
    700,
    720,
    755,
    760,
    770,
    790,
    830,
    870,
    900,
    920,
    980,
    1100,
    1120,
    1150,
    1180,
    1200,
    1215,
    1320,
    1400,
    1540,
    1700,
    2370,
]

_base_names = [
    "Water",
    "Oil",
    "Wine",
    "Unknown",
]

_effect_names = [
    "Healing",
    "Poison",
    "Frost",
    "Fire",
    "Strength",
    "Wild Growth",
    "Mana",
    "Explosion",
    "Dexterity",
    "Swiftness",
    "Stone Skin",
    "Sleep",
    "Poison Protection",
    "Light",
    "Lightning",
    "Gluing",
    "Stench",
    "Slowness",
    "Slipperiness",
    "Fragrance",
    "Acid",
    "Charm",
    "Acid Protection",
    "Frost Protection",
    "Fire Protection",
    "Lightning Protection",
    "Rage",
    "Curse",
    "Magical Vision",
    "Rejuvenation",
    "Fear",
    "Libido",
    "Invisibility",
    "Enlargement",
    "Hallucinations",
    "Shrinking",
    "Levitation",
    "Inspiration",
    "Anti Magic",
    "Luck",
    "Necromancy",
]

_effect_types = [
    "Buff",
    "Harmful",
    "Harmful",
    "Harmful",
    "Buff",
    "Pheromone",
    "Buff",
    "Harmful",
    "Buff",
    "Buff",
    "Buff",
    "Pheromone",
    "Buff",
    "Universal",
    "Harmful",
    "Swamp",
    "Swamp",
    "Harmful",
    "Universal",
    "Pheromone",
    "Harmful",
    "Pheromone",
    "Buff",
    "Buff",
    "Buff",
    "Buff",
    "Pheromone",
    "Harmful",
    "Buff",
    "Buff",
    "Harmful",
    "Pheromone",
    "Buff",
    "Universal",
    "Pheromone",
    "Universal",
    "Buff",
    "Buff",
    "Universal",
    "Buff",
    "Necro",
]


class EffectTypes(IntEnum):
    Harmful = 0
    Swamp = 1
    Universal = 2
    Pheromone = 3
    Buff = 4
    Necro = 5


class PotionBases(IntEnum):
    Water = 0
    Oil = 1
    Wine = 2
    Unknown = 3

    __doc__ = "Enumeration class for potion bases."

    @property
    def base_name(self) -> str:
        return _base_names[self]


class Effects(IntEnum):
    Healing = 0
    Poison = 1
    Frost = 2
    Fire = 3
    Strength = 4
    WildGrowth = 5
    Mana = 6
    Explosion = 7
    Dexterity = 8
    Swiftness = 9
    StoneSkin = 10
    Sleep = 11
    PoisonProtection = 12
    Light = 13
    Lightning = 14
    Gluing = 15
    Stench = 16
    Slowness = 17
    Slipperiness = 18
    Fragrance = 19
    Acid = 20
    Charm = 21
    AcidProtection = 22
    FrostProtection = 23
    FireProtection = 24
    LightningProtection = 25
    Rage = 26
    Curse = 27
    MagicalVision = 28
    Rejuvenation = 29
    Fear = 30
    Libido = 31
    Invisibility = 32
    Enlargement = 33
    Hallucinations = 34
    Shrinking = 35
    Levitation = 36
    Inspiration = 37
    AntiMagic = 38
    Luck = 39
    Necromancy = 40

    __doc__ = "Enumeration class for effects."

    @property
    def base_price(self) -> int:
        return _effect_base_prices[self]

    @property
    def effect_name(self) -> str:
        return _effect_names[self]

    @property
    def effect_type(self) -> EffectTypes:
        return EffectTypes[_effect_types[self]]

    def exists_in_base(self, base: Union[int, PotionBases]) -> bool:
        if isinstance(base, int):
            base = PotionBases(base)
        return self in base_effects[base].keys()

    def dull_reachable_tier(self, base: Union[int, PotionBases]) -> int:
        if isinstance(base, int):
            base = PotionBases(base)
        return 0 if not self.exists_in_base(base) else 1 if abs(base_effects[base][self].angle) >= 72 else 2 if abs(base_effects[base][self].angle) >= 12 else 3


class EffectPosition:
    def __init__(self, x: float, y: float, angle: int):
        self.x = x
        self.y = y
        self.angle = angle


# exist effects and their positions in potion base maps.
base_effects: dict[PotionBases, dict[Effects, EffectPosition]] = {
    PotionBases.Water: {
        Effects.Healing: EffectPosition(5.3, -5.84, 0),
        Effects.Poison: EffectPosition(-5.65, -5.889, 0),
        Effects.Frost: EffectPosition(11.54, -0.24, 0),
        Effects.Fire: EffectPosition(-14, 1.12, 0),
        Effects.Strength: EffectPosition(0.74, -16.28, 0),
        Effects.WildGrowth: EffectPosition(16.84, -11.97, 0),
        Effects.Mana: EffectPosition(11.69, 11.69, 0),
        Effects.Explosion: EffectPosition(-13.08, 12.72, 0),
        Effects.Dexterity: EffectPosition(20.86, 3.19, 0),
        Effects.Swiftness: EffectPosition(-0.89, 18.6, 0),
        Effects.StoneSkin: EffectPosition(-0.72, -23, 0),
        Effects.Sleep: EffectPosition(21.85, -5.98, 0),
        Effects.PoisonProtection: EffectPosition(23.62, -29.02, 45),
        Effects.Light: EffectPosition(-24.9, 0, 0),
        Effects.Lightning: EffectPosition(10.37, 19.6, 0),
        Effects.Gluing: EffectPosition(17.86, -59.08, 90),
        Effects.Stench: EffectPosition(-51.12, -48.1, -135),
        Effects.Slowness: EffectPosition(8.41, -29.56, 0),
        Effects.Slipperiness: EffectPosition(56.1, -7.75, 90),
        Effects.Fragrance: EffectPosition(58.04, -23.72, -135),
        Effects.Acid: EffectPosition(-31.49, -18.27, 0),
        Effects.Charm: EffectPosition(-11.1, 27.12, 0),
        Effects.AcidProtection: EffectPosition(33.39, 47.03, 135),
        Effects.FrostProtection: EffectPosition(-51.1, 0, 45),
        Effects.FireProtection: EffectPosition(39.87, 0.52, -45),
        Effects.LightningProtection: EffectPosition(-5.28, -48.98, 45),
        Effects.Rage: EffectPosition(-20.34, 22.58, 0),
        Effects.Curse: EffectPosition(-60.56, -21.61, -135),
        Effects.MagicalVision: EffectPosition(21.27, 10.44, 0),
        Effects.Rejuvenation: EffectPosition(38.96, -55.19, 180),
        Effects.Fear: EffectPosition(-32.36, 52.87, -150),
        Effects.Libido: EffectPosition(-30.38, 14.2, 0),
        Effects.Invisibility: EffectPosition(10.46, 35.57, 0),
        Effects.Enlargement: EffectPosition(-58.06, 12.09, 135),
        Effects.Hallucinations: EffectPosition(35.55, 38.98, 180),
        Effects.Shrinking: EffectPosition(59.66, 7.63, -135),
        Effects.Levitation: EffectPosition(-4.22, 36.37, 0),
        Effects.Inspiration: EffectPosition(7.64, 61.12, 105),
        Effects.AntiMagic: EffectPosition(47.59, 48.6, 180),
        Effects.Luck: EffectPosition(59.77, 31.3, 135),
        Effects.Necromancy: EffectPosition(-27.41, 30.4, 0),
    },
    PotionBases.Oil: {
        Effects.Healing: EffectPosition(3.8, -3.96, 15),
        Effects.Poison: EffectPosition(-3.85, -3.74, -15),
        Effects.Fire: EffectPosition(-11.65, -0.98, 60),
        Effects.WildGrowth: EffectPosition(17.25, -12.41, 90),
        Effects.Explosion: EffectPosition(-8.96, 9.3, 90),
        Effects.StoneSkin: EffectPosition(0, -14.19, 180),
        Effects.PoisonProtection: EffectPosition(16.22, -20.38, 0),
        Effects.Light: EffectPosition(-20.89, 1.48, 135),
        Effects.Lightning: EffectPosition(7.84, 16.46, -90),
        Effects.Gluing: EffectPosition(-3.95, -23.57, 0),
        Effects.Stench: EffectPosition(-16.83, -19.91, 0),
        Effects.Slipperiness: EffectPosition(24.7, -4.11, 0),
        Effects.AcidProtection: EffectPosition(23.57, -30.32, 0),
        Effects.FrostProtection: EffectPosition(-27.97, -4.09, 0),
        Effects.FireProtection: EffectPosition(28.91, 1.7, 0),
        Effects.LightningProtection: EffectPosition(3.66, -30.72, 0),
        Effects.Rejuvenation: EffectPosition(37.18, -32.56, 0),
        Effects.Invisibility: EffectPosition(-2.55, 27.94, -135),
        Effects.Enlargement: EffectPosition(-43.1, 3.73, 0),
        Effects.Shrinking: EffectPosition(44.43, -3.63, 0),
        Effects.AntiMagic: EffectPosition(32.77, 29.94, 0),
    },
    PotionBases.Wine: {
        Effects.Healing: EffectPosition(3, -3, -25),
        Effects.Frost: EffectPosition(7.87, 0.34, -70),
        Effects.Strength: EffectPosition(0.66, -9, 60),
        Effects.Mana: EffectPosition(7.38, 6.79, 45),
        Effects.Dexterity: EffectPosition(14.21, 3.53, 30),
        Effects.Swiftness: EffectPosition(1, 9, -45),
        Effects.Sleep: EffectPosition(15.65, -2.25, -60),
        Effects.Slowness: EffectPosition(0.48, -16, 50),
        Effects.Fragrance: EffectPosition(22.82, -7.41, 0),
        Effects.Acid: EffectPosition(-13.14, -9.02, -115),
        Effects.Charm: EffectPosition(-6.25, 11.79, 120),
        Effects.Rage: EffectPosition(-13.04, 10.59, -40),
        Effects.Curse: EffectPosition(-21.93, -9.02, 0),
        Effects.MagicalVision: EffectPosition(18.63, 9.79, 90),
        Effects.Fear: EffectPosition(-19.45, 14.64, 0),
        Effects.Libido: EffectPosition(-17.67, 3.61, -20),
        Effects.Hallucinations: EffectPosition(19.25, 16.3, 0),
        Effects.Levitation: EffectPosition(-1.12, 18.65, -150),
        Effects.Inspiration: EffectPosition(2.52, 25.77, 0),
        Effects.Luck: EffectPosition(26.56, 10.66, 0),
        Effects.Necromancy: EffectPosition(-12.28, -17.33, 180),
    },
    PotionBases.Unknown: {},  # Unknown base so cannot determine potion effect existence.
}

if __name__ == "__main__":
    print(Effects.AcidProtection.base_price)
    print(Effects.Rage.base_price)
    print(Effects.AntiMagic.effect_type.name)
    print(Effects.Healing.dull_reachable_tier(PotionBases.Oil))
