import SingleEffect
from Recipes import Potion

VERSION = 3

VoidSalt_1 = Potion.fromName(Swiftness=3, Dexterity=2)
VoidSalt_2 = Potion.fromName(Poison=1, Fire=1, Explosion=1, Lightning=1, Frost=1)
MoonSalt_1 = Potion.fromName(MagicVision=3, Dexterity=2)
MoonSalt_2 = Potion.fromName(Levitation=3, Invisibility=2)
MoonSalt_3 = Potion.fromName(Lightning=3, Frost=2)
SunSalt_1 = Potion.fromName(MagicVision=3, Light=2)
SunSalt_2 = Potion.fromName(Enlargement=3, Rage=2)
SunSalt_3 = Potion.fromName(Explosion=3, Fire=2)
LifeSalt_1 = Potion.fromName(
    AntiMagic=1,
    FireProtection=1,
    LightningProtection=1,
    AcidProtection=1,
    FrostProtection=1,
)
LifeSalt_2 = Potion.fromName(AntiMagic=3, StoneSkin=2)
LifeSalt_3 = Potion.fromName(Rejuvenation=3, Healing=2)
LifeSalt_4 = Potion.fromName(Libido=3, Charm=2)
LifeSalt_5 = Potion.fromName(Acid=3, Poison=2)
LifeSalt_6 = Potion.fromName(Healing=3, Mana=2)
LifeSalt_7 = Potion.fromName(Stoneskin=3, Strength=2)
PhiloStone_1 = Potion.fromName(Enlargement=1, Gluing=1, Antimagic=1, Slipperiness=1, Shrinking=1)
PhiloStone_2 = Potion.fromName(Strength=1, Swiftness=1, Dexterity=1, MagicVision=1, StoneSkin=1)
PhiloStone_3 = Potion.fromName(Invisibility=1, Levitation=1, Fear=1, Necromancy=1, Rejuvenation=1)
PhiloStone_4 = Potion.fromName(
    FrostProtection=1,
    LightningProtection=1,
    PoisonProtection=1,
    AcidProtection=1,
    FireProtection=1,
)
PhiloStone_5 = Potion.fromName(Mana=1, Healing=1, WildGrowth=1, Light=1, Libido=1)
PhiloSalt_1 = Potion.fromName(
    FrostProtection=1,
    StoneSkin=1,
    LightningProtection=1,
    PoisonProtection=1,
    FireProtection=1,
)
PhiloSalt_2 = Potion.fromName(Gluing=1, Stench=1, Light=1, Invisibility=1, Slipperiness=1)
PhiloSalt_3 = Potion.fromName(Growth=1, Poison=1, Fire=1, Explosion=1, Lightning=1)
PhiloSalt_4 = Potion.fromName(Healing=1, Fragrance=1, Rejuvenation=1, Charm=1, Libido=1)
PhiloSalt_5 = Potion.fromName(Rage=1, Fear=1, Enlargement=1, Curse=1, Necromancy=1)
PhiloSalt_6 = Potion.fromName(Strength=1, Healing=1, Dexterity=1, Mana=1, Swiftness=1)
PhiloSalt_7 = Potion.fromName(Mana=1, MagicVision=1, Hallucination=1, AntiMagic=1, Luck=1)
PhiloSalt_8 = Potion.fromName(Hallucination=1, Levitation=1, Libido=1, Acid=1, Necromancy=1)
PhiloSalt_9 = Potion.fromName(Mana=1, MagicVision=1, Charm=1, Rage=1, Slowness=1)
PhiloSalt_10 = Potion.fromName(Enlargment=1, AntiMagic=1, Shrinking=1, AcidProtection=1, Rejuvenation=1)
PhiloSalt_11 = Potion.fromName(Fragrance=1, Luck=1, Inspiration=1, Fear=1, Curse=1)
PhiloSalt_12 = Potion.fromName(Strength=1, Frost=1, Sleep=1, Dexterity=1, Swiftness=1)

VoidSalt = [
    SingleEffect.Poison,
    SingleEffect.Strength,
    SingleEffect.StoneSkin,
    SingleEffect.Sleep,
    SingleEffect.Slowness,
    VoidSalt_2,
    VoidSalt_1,
    SingleEffect.Slowness,
    SingleEffect.Sleep,
    SingleEffect.Poison,
]
MoonSalt = [
    SingleEffect.Poison,
    SingleEffect.Strength,
    SingleEffect.StoneSkin,
    SingleEffect.Sleep,
    SingleEffect.Slowness,
    SingleEffect.Dexterity,
    SingleEffect.Swiftness,
    SingleEffect.Charm,
    SingleEffect.Invisibility,
    SingleEffect.Levitation,
    SingleEffect.Frost,
    SingleEffect.Lightning,
    SingleEffect.Mana,
    SingleEffect.MagicalVision,
    MoonSalt_3,
    MoonSalt_1,
    MoonSalt_2,
    SingleEffect.FrostProtection,
    SingleEffect.FireProtection,
    SingleEffect.Dexterity,
    SingleEffect.Swiftness,
    SingleEffect.Mana,
    SingleEffect.Light,
]
SunSalt = [
    SingleEffect.Poison,
    SingleEffect.Strength,
    SingleEffect.StoneSkin,
    SingleEffect.Sleep,
    SingleEffect.Slowness,
    SingleEffect.Dexterity,
    SingleEffect.Swiftness,
    SingleEffect.Charm,
    SingleEffect.Invisibility,
    SingleEffect.Levitation,
    SingleEffect.Frost,
    SingleEffect.Lightning,
    SingleEffect.Mana,
    SingleEffect.MagicalVision,
    SingleEffect.Explosion,
    SingleEffect.Enlargement,
    SingleEffect.Fire,
    SingleEffect.Light,
    SingleEffect.Rage,
    SingleEffect.Slipperiness,
    SingleEffect.FrostProtection,
    SingleEffect.FireProtection,
    SingleEffect.Shrinking,
    SunSalt_3,
    SunSalt_1,
    SunSalt_2,
    SingleEffect.LightningProtection,
    SingleEffect.PoisonProtection,
    SingleEffect.Libido,
    SingleEffect.Enlargement,
    SingleEffect.Light,
    SingleEffect.Fire,
]
LifeSalt = [
    SingleEffect.Poison,
    SingleEffect.Strength,
    SingleEffect.StoneSkin,
    SingleEffect.Sleep,
    SingleEffect.Slowness,
    SingleEffect.Dexterity,
    SingleEffect.Swiftness,
    SingleEffect.Charm,
    SingleEffect.Invisibility,
    SingleEffect.Levitation,
    SingleEffect.Frost,
    SingleEffect.Lightning,
    SingleEffect.Mana,
    SingleEffect.MagicalVision,
    SingleEffect.Explosion,
    SingleEffect.Enlargement,
    SingleEffect.Fire,
    SingleEffect.Light,
    SingleEffect.Rage,
    SingleEffect.Slipperiness,
    SingleEffect.FrostProtection,
    SingleEffect.FireProtection,
    SingleEffect.Shrinking,
    SingleEffect.Healing,
    SingleEffect.PoisonProtection,
    SingleEffect.AcidProtection,
    SingleEffect.WildGrowth,
    SingleEffect.Rejuvenation,
    SingleEffect.Libido,
    SingleEffect.Acid,
    SingleEffect.Necromancy,
    SingleEffect.Fear,
    SingleEffect.Healing,
    SingleEffect.WildGrowth,
    SingleEffect.Libido,
    SingleEffect.Necromancy,
    SingleEffect.Rejuvenation,
    LifeSalt_1,
    LifeSalt_2,
    LifeSalt_3,
    LifeSalt_6,
    LifeSalt_5,
    LifeSalt_4,
    LifeSalt_7,
]
PhiloSalt = [
    SingleEffect.Poison,
    SingleEffect.Strength,
    SingleEffect.StoneSkin,
    SingleEffect.Sleep,
    SingleEffect.Slowness,
    SingleEffect.Dexterity,
    SingleEffect.Swiftness,
    SingleEffect.Charm,
    SingleEffect.Invisibility,
    SingleEffect.Levitation,
    SingleEffect.Frost,
    SingleEffect.Lightning,
    SingleEffect.Mana,
    SingleEffect.MagicalVision,
    SingleEffect.Explosion,
    SingleEffect.Enlargement,
    SingleEffect.Fire,
    SingleEffect.Light,
    SingleEffect.Rage,
    SingleEffect.Slipperiness,
    SingleEffect.FrostProtection,
    SingleEffect.FireProtection,
    SingleEffect.Shrinking,
    SingleEffect.Healing,
    SingleEffect.PoisonProtection,
    SingleEffect.AcidProtection,
    SingleEffect.WildGrowth,
    SingleEffect.Rejuvenation,
    SingleEffect.Libido,
    SingleEffect.Acid,
    SingleEffect.Necromancy,
    SingleEffect.Fear,
    PhiloStone_4,
    VoidSalt_2,  # same recipe.
    PhiloStone_2,
    PhiloSalt_5,
    PhiloStone_3,
    PhiloStone_1,
    SingleEffect.Curse,
    SingleEffect.Stench,
    SingleEffect.Fragrance,
    SingleEffect.Inspiration,
    SingleEffect.Luck,
    SingleEffect.Hallucinations,
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
]
