from collections.abc import Sequence, Iterable
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

from .effects import NUMBER_OF_EFFECTS, Effects, PotionBases, Compatibility
from .ingredients import NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS, Ingredients, Salts


class EffectTierList(Sequence[int]):
    def __init__(self, effect_tiers: Iterable[int]) -> None:
        self._effect_tiers = tuple(effect_tiers)
        assert len(self._effect_tiers) == NUMBER_OF_EFFECTS

    def __getitem__(self, index):
        return self._effect_tiers[index]

    def __len__(self):
        return len(self._effect_tiers)

    def __repr__(self) -> str:
        return repr(self._effect_tiers)

    @classmethod
    def from_name(cls, **kwargs):
        effect_tiers = [0] * NUMBER_OF_EFFECTS
        for k, v in kwargs.items():
            if k in Effects.__members__:
                effect_tiers[(Effects[k]).value] = v
        return cls(effect_tiers)


# Type alias.
class Potion(EffectTierList):
    pass


class IngredientNumList(Sequence[int]):
    def __init__(self, ingredient_nums: Iterable[int]) -> None:
        self._ingredient_nums = tuple(ingredient_nums)
        assert len(self._ingredient_nums) == NUMBER_OF_INGREDIENTS

    def __getitem__(self, index):
        return self._ingredient_nums[index]

    def __len__(self):
        return len(self._ingredient_nums)

    def __repr__(self) -> str:
        return repr(self._ingredient_nums)

    @classmethod
    def from_name(cls, **kwargs):
        ingredient_nums = [0] * NUMBER_OF_INGREDIENTS
        for k, v in kwargs.items():
            if k in Ingredients.__members__:
                ingredient_nums[(Ingredients[k]).value] = v
        return cls(ingredient_nums)


class SaltGrainList(Sequence[int]):
    def __init__(self, salt_grains: Iterable[int]) -> None:
        self._salt_grains: tuple[int, ...] = tuple(salt_grains)
        assert len(self._salt_grains) == NUMBER_OF_SALTS

    def __getitem__(self, index):
        return self._salt_grains[index]

    def __len__(self):
        return len(self._salt_grains)

    def __repr__(self) -> str:
        return repr(self._salt_grains)

    @classmethod
    def from_name(cls, **kwargs):
        salt_grains = [0] * NUMBER_OF_SALTS
        for k, v in kwargs.items():
            if k in Salts.__members__:
                salt_grains[(Salts[k]).value] = v
        return cls(salt_grains)


class Recipe:
    def __init__(
        self,
        base: PotionBases,
        effect_tier_list: EffectTierList,
        ingredient_num_list: IngredientNumList,
        salt_grain_list: SaltGrainList,
        hidden=False,
    ) -> None:
        self.base = base
        self.effect_tier_list = effect_tier_list
        self.ingredient_num_list = ingredient_num_list
        self.salt_grain_list = salt_grain_list
        self.hidden = hidden

    def __repr__(self) -> str:
        return f"Recipe({self.base}, {self.effect_tier_list}, {self.ingredient_num_list}, {self.salt_grain_list})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Recipe):
            return False
        return (
            self.base == other.base
            and tuple(self.effect_tier_list) == tuple(other.effect_tier_list)
            and tuple(self.ingredient_num_list) == tuple(other.ingredient_num_list)
            and tuple(self.salt_grain_list) == tuple(other.salt_grain_list)
            and bool(self.hidden) == bool(other.hidden)
        )

    def __hash__(self) -> int:
        return hash(
            (
                int(self.base),
                tuple(self.effect_tier_list),
                tuple(self.ingredient_num_list),
                tuple(self.salt_grain_list),
                int(bool(self.hidden)),
            )
        )

    # If the recipe contains effects with legal levels.
    @property
    def is_valid(self) -> bool:
        return all(0 <= tier <= 3 for tier in self.effect_tier_list)

    # If the recipe contains exact effect levels to acquire.
    @property
    def is_exact_recipe(self) -> bool:
        return (sum(self.effect_tier_list) <= 5) and all(0 <= tier <= 3 for tier in self.effect_tier_list)

    # calculate the base price of a recipe.
    def base_price(self, required_effects: Optional[list[Effects]] = None) -> float:

        # Provide none to calculate merchant base price (requesting all effects.)
        _tier_mult = [0, 0.4, 0.7, 1.0]
        _required_effects = required_effects if required_effects is not None else list(Effects)
        _base_price = 0.0
        for effect in _required_effects:
            _this_effect_tier = self.effect_tier_list[effect]
            for extra_effect in Effects:
                if Compatibility[effect][extra_effect] == 0:
                    _this_effect_tier -= self.effect_tier_list[extra_effect]
                    if _this_effect_tier <= 0:
                        break
            if _this_effect_tier > 0:
                _base_price += _tier_mult[_this_effect_tier] * effect.base_price
        return _base_price


class CommentType(IntEnum):
    Other = 0
    Plotter = 1
    Note = 2
    NoteComment = 3
    NoteLink = 4
    VoidSalt = 11
    MoonSalt = 12
    SunSalt = 13
    LifeSalt = 14
    PhiloSalt = 15
    Ingredient = 16


class LinkType(IntEnum):
    Plotter = 1
    Discord = 2


@dataclass
class Comment:
    target: Recipe
    type: CommentType = CommentType.Other
    author: str = "Anonymous"
    text: str = ""


@dataclass
class DullLowlanderComment:
    target_effect: Effects
    ingredient: Ingredients


@dataclass
class RecipeLink:
    target: Recipe
    type: LinkType
    url: str


def test():
    effect_tier_list = EffectTierList.from_name(Lightning=1, Fire=1, Poison=1, Healing=1, Dexterity=1)
    ingredient_num_list = IngredientNumList.from_name(
        Windbloom=1,
        Featherbloom=1,
        FoggyParasol=1,
        Fluffbloom=1,
        Whirlweed=1,
        PhantomSkirt=1,
        CloudCrystal=1,
        WitchMushroom=1,
        ThunderThistle=1,
        DreamBeet=1,
        ShadowChanterelle=1,
        Spellbloom=1,
        Mageberry=1,
        ArcaneCrystal=1,
        Waterbloom=1,
        Icefruit=1,
        Tangleweed=1,
        Coldleaf=1,
        KrakenMushroom=1,
        Watercap=1,
        FrostSapphire=1,
        Lifeleaf=1,
        Goodberry=1,
        DruidsRosemary=1,
        MossShroom=1,
        HealersHeather=1,
        EvergreenFern=1,
        LifeCrystal=1,
        Terraria=1,
        DryadsSaddle=1,
        Poopshroom=1,
        Weirdshroom=1,
        Goldthorn=1,
        Mudshroom=1,
        EarthPyrite=1,
        StinkMushroom=1,
        GoblinShroom=1,
        Marshroom=1,
        HairyBanana=1,
        Thornstick=1,
        GraveTruffle=1,
        PlagueStibnite=1,
        Firebell=1,
        SulphurShelf=1,
        Lavaroot=1,
        Flameweed=1,
        MagmaMorel=1,
        DragonPepper=1,
        FireCitrine=1,
        MadMushroom=1,
        Bloodthorn=1,
        TerrorBud=1,
        GraspingRoot=1,
        Boombloodthorn=1,
        Boombloom=1,
        LustMushroom=1,
        BloodRuby=1,
        RainbowCap=1,
        FableBismuth=1,
    )
    salt_grain_list = SaltGrainList.from_name(Sun=100)
    recipe = Recipe(PotionBases.Water, effect_tier_list, ingredient_num_list, salt_grain_list)
    print(recipe.is_valid, recipe.is_exact_recipe)


if __name__ == "__main__":
    test()
