from dataclasses import dataclass

from . import single_effect as SingleEffect
from .recipes import Potion

VERSION = 2


@dataclass(frozen=True)
class LegendaryComponent:
    group: str
    potion: Potion


class LegendarySubstance:
    def __init__(self, name: str, *required_potions: Potion, required_substance: "LegendarySubstance | None" = None) -> None:
        self.name = name
        self.required_potions = list(required_potions)
        self.required_substance = required_substance

    def __repr__(self) -> str:
        return f"LegendarySubstance(name={self.name}, required_potions={self.required_potions}, required_substance={self.required_substance})"

    def get_legendary_components(self) -> list[LegendaryComponent]:
        components: list[LegendaryComponent] = []
        if self.required_substance is not None:
            components.extend(self.required_substance.get_legendary_components())
        components.extend(LegendaryComponent(group=self.name, potion=potion) for potion in self.required_potions)
        return components


VoidSalt_1 = Potion.from_name(Poison=1, Fire=1, Explosion=1, Lightning=1, Frost=1)
VoidSalt_2 = Potion.from_name(Swiftness=3, Dexterity=2)
MoonSalt_1 = Potion.from_name(Lightning=3, Frost=2)
MoonSalt_2 = Potion.from_name(MagicalVision=3, Dexterity=2)
MoonSalt_3 = Potion.from_name(Levitation=3, Invisibility=2)
SunSalt_1 = Potion.from_name(Explosion=3, Fire=2)
SunSalt_2 = Potion.from_name(MagicalVision=3, Light=2)
SunSalt_3 = Potion.from_name(Enlargement=3, Rage=2)
LifeSalt_1 = Potion.from_name(
    AntiMagic=1,
    FireProtection=1,
    LightningProtection=1,
    AcidProtection=1,
    FrostProtection=1,
)
LifeSalt_2 = Potion.from_name(AntiMagic=3, StoneSkin=2)
LifeSalt_3 = Potion.from_name(Rejuvenation=3, Healing=2)
LifeSalt_4 = Potion.from_name(Healing=3, Mana=2)
LifeSalt_5 = Potion.from_name(StoneSkin=3, Strength=2)
LifeSalt_6 = Potion.from_name(Libido=3, Charm=2)
LifeSalt_7 = Potion.from_name(Acid=3, Poison=2)
PhiloStone_1 = Potion.from_name(
    FrostProtection=1,
    LightningProtection=1,
    PoisonProtection=1,
    AcidProtection=1,
    FireProtection=1,
)
PhiloStone_2 = Potion.from_name(Strength=1, Swiftness=1, Dexterity=1, MagicalVision=1, StoneSkin=1)
PhiloStone_3 = Potion.from_name(Mana=1, Healing=1, WildGrowth=1, Light=1, Libido=1)
PhiloStone_4 = Potion.from_name(Invisibility=1, Levitation=1, Fear=1, Necromancy=1, Rejuvenation=1)
PhiloStone_5 = Potion.from_name(Enlargement=1, Gluing=1, AntiMagic=1, Slipperiness=1, Shrinking=1)
PhiloSalt_1 = Potion.from_name(Fragrance=1, Luck=1, Inspiration=1, Fear=1, Curse=1)
PhiloSalt_2 = Potion.from_name(Hallucinations=1, Levitation=1, Libido=1, Acid=1, Necromancy=1)
PhiloSalt_3 = Potion.from_name(Mana=1, MagicalVision=1, Charm=1, Rage=1, Slowness=1)
PhiloSalt_4 = Potion.from_name(Strength=1, Frost=1, Sleep=1, Dexterity=1, Swiftness=1)
PhiloSalt_5 = Potion.from_name(Enlargement=1, AntiMagic=1, Shrinking=1, AcidProtection=1, Rejuvenation=1)
PhiloSalt_6 = Potion.from_name(
    FrostProtection=1,
    StoneSkin=1,
    LightningProtection=1,
    PoisonProtection=1,
    FireProtection=1,
)
PhiloSalt_7 = Potion.from_name(Gluing=1, Stench=1, Light=1, Invisibility=1, Slipperiness=1)
PhiloSalt_8 = Potion.from_name(WildGrowth=1, Poison=1, Fire=1, Explosion=1, Lightning=1)
PhiloSalt_9 = Potion.from_name(Strength=1, Healing=1, Dexterity=1, Mana=1, Swiftness=1)
PhiloSalt_10 = Potion.from_name(Mana=1, MagicalVision=1, Hallucinations=1, AntiMagic=1, Luck=1)
PhiloSalt_11 = Potion.from_name(Healing=1, Fragrance=1, Rejuvenation=1, Charm=1, Libido=1)
PhiloSalt_12 = Potion.from_name(Rage=1, Fear=1, Enlargement=1, Curse=1, Necromancy=1)

Nigredo = LegendarySubstance(
    "Nigredo",
    SingleEffect.StrongPoison,
    SingleEffect.StrongStrength,
    SingleEffect.StrongStoneSkin,
    SingleEffect.StrongSleep,
    SingleEffect.StrongSlowness,
)
Albedo = LegendarySubstance(
    "Albedo",
    SingleEffect.StrongDexterity,
    SingleEffect.StrongSwiftness,
    SingleEffect.StrongCharm,
    SingleEffect.StrongInvisibility,
    SingleEffect.StrongLevitation,
    SingleEffect.StrongFrost,
    SingleEffect.StrongLightning,
    SingleEffect.StrongMana,
    SingleEffect.StrongMagicalVision,
    required_substance=Nigredo,
)
Citrinitas = LegendarySubstance(
    "Citrinitas",
    SingleEffect.StrongExplosion,
    SingleEffect.StrongEnlargement,
    SingleEffect.StrongFire,
    SingleEffect.StrongLight,
    SingleEffect.StrongRage,
    SingleEffect.StrongSlipperiness,
    SingleEffect.StrongFrostProtection,
    SingleEffect.StrongFireProtection,
    SingleEffect.StrongShrinking,
    required_substance=Albedo,
)
Rubedo = LegendarySubstance(
    "Rubedo",
    SingleEffect.StrongHealing,
    SingleEffect.StrongPoisonProtection,
    SingleEffect.StrongAcidProtection,
    SingleEffect.StrongWildGrowth,
    SingleEffect.StrongRejuvenation,
    SingleEffect.StrongLibido,
    SingleEffect.StrongAcid,
    SingleEffect.StrongNecromancy,
    SingleEffect.StrongFear,
    SingleEffect.StrongGluing,
    SingleEffect.StrongLightningProtection,
    SingleEffect.StrongAntiMagic,
    required_substance=Citrinitas,
)
PhilosopherStone = LegendarySubstance(
    "Philosopher Stone",
    PhiloStone_4,
    VoidSalt_1,  # same recipe.
    PhiloStone_2,
    PhiloStone_5,
    PhiloStone_3,
    PhiloStone_1,
    SingleEffect.StrongCurse,
    SingleEffect.StrongStench,
    SingleEffect.StrongFragrance,
    SingleEffect.StrongInspiration,
    SingleEffect.StrongLuck,
    SingleEffect.StrongHallucinations,
    required_substance=Rubedo,
)

VoidSalt = LegendarySubstance(
    "Void Salt",
    VoidSalt_2,
    VoidSalt_1,
    SingleEffect.StrongSlowness,
    SingleEffect.StrongSleep,
    SingleEffect.StrongPoison,
    required_substance=Nigredo,
)
MoonSalt = LegendarySubstance(
    "Moon Salt",
    MoonSalt_3,
    MoonSalt_1,
    MoonSalt_2,
    SingleEffect.StrongFrostProtection,
    SingleEffect.StrongFireProtection,
    SingleEffect.StrongDexterity,
    SingleEffect.StrongSwiftness,
    SingleEffect.StrongMana,
    SingleEffect.StrongLight,
    required_substance=Albedo,
)
SunSalt = LegendarySubstance(
    "Sun Salt",
    SunSalt_3,
    SunSalt_1,
    SunSalt_2,
    SingleEffect.StrongLightningProtection,
    SingleEffect.StrongPoisonProtection,
    SingleEffect.StrongLibido,
    SingleEffect.StrongEnlargement,
    SingleEffect.StrongLight,
    SingleEffect.StrongFire,
    required_substance=Citrinitas,
)
LifeSalt = LegendarySubstance(
    "Life Salt",
    SingleEffect.StrongHealing,
    SingleEffect.StrongWildGrowth,
    SingleEffect.StrongLibido,
    SingleEffect.StrongNecromancy,
    SingleEffect.StrongRejuvenation,
    LifeSalt_1,
    LifeSalt_2,
    LifeSalt_3,
    LifeSalt_6,
    LifeSalt_5,
    LifeSalt_4,
    LifeSalt_7,
    required_substance=Rubedo,
)
PhilosopherSalt = LegendarySubstance(
    "Philosopher's Salt",
    PhiloSalt_11,
    PhiloSalt_8,
    PhiloSalt_9,
    PhiloSalt_12,
    PhiloSalt_10,
    PhiloSalt_1,
    PhiloSalt_2,
    PhiloSalt_3,
    PhiloSalt_6,
    PhiloSalt_5,
    PhiloSalt_4,
    PhiloSalt_7,
    required_substance=PhilosopherStone,
)

LEGENDARY_SALT_SUBSTANCES: dict[str, LegendarySubstance] = {
    "Void": VoidSalt,
    "Moon": MoonSalt,
    "Sun": SunSalt,
    "Life": LifeSalt,
    "Philosopher": PhilosopherSalt,
}


def get_legendary_salt_components() -> dict[str, list[LegendaryComponent]]:
    return {salt_key: substance.get_legendary_components() for salt_key, substance in LEGENDARY_SALT_SUBSTANCES.items()}
