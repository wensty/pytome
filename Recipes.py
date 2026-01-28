import pickle
import gzip
from collections.abc import Sequence, Iterable

from Effects import NUMBER_OF_EFFECTS, Effects, PotionBases
from Ingredients import NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS, Ingredients, Salts

with gzip.open("data/Compatibility.pkl.gz", "rb") as f:
    Compatibility: list[list[int]] = pickle.load(f)


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
        discord_link="",
        plotter_link="",
        hidden=False,
    ) -> None:
        self.base = base
        self.effect_tier_list = effect_tier_list
        self.ingredient_num_list = ingredient_num_list
        self.salt_grain_list = salt_grain_list
        self.discord_link = discord_link
        self.plotter_link = plotter_link
        self.hidden = hidden

    def __repr__(self) -> str:
        return f"Recipe({self.base}, {self.effect_tier_list}, {self.ingredient_num_list}, {self.salt_grain_list})"

    def is_dull(self) -> bool:
        return all(salt == 0 for salt in self.salt_grain_list)

    def is_lowlander(self, k: int) -> bool:
        return sum(1 if ingredient > 0 else 0 for ingredient in self.ingredient_num_list) <= k

    # A customer considers a potion weak, if all required effects exist in the potion is at most tier 1 and is accepted.
    def is_weak(self, required_effects: list[Effects], exact: bool = False) -> bool:
        assert len(required_effects) > 0
        if exact:
            if not self.is_exact:
                return False
            return (
                self.is_exact
                and all(self.effect_tier_list[effect] <= 1 for effect in required_effects)
                and any(self.effect_tier_list[effect] == 1 for effect in required_effects)
            )
        return any(self.effect_tier_list[effect] >= 1 for effect in required_effects)

    # A customer considers a potion strong, if any required effect exists in the potion is at least tier 3 and is accepted.
    def is_strong(self, required_effects: list[Effects], exact: bool = False) -> bool:
        assert len(required_effects) > 0
        if exact:
            if not self.is_exact:
                return False
            return self.is_exact and any(self.effect_tier_list[effect] >= 3 for effect in required_effects)
        return any(self.effect_tier_list[effect] == 3 for effect in required_effects)

    def contains_ingredient(self, required_ingredient: Ingredients) -> bool:
        return self.ingredient_num_list[required_ingredient] > 0

    def contains_half_ingredient(self, required_ingredient: Ingredients) -> bool:
        return self.ingredient_num_list[required_ingredient] >= 0.5 * sum(self.ingredient_num_list)

    def contains_no_ingredient(self, required_ingredient: Ingredients) -> bool:
        return self.ingredient_num_list[required_ingredient] == 0

    def is_certain_base(self, required_base: PotionBases) -> bool:
        return self.base != PotionBases.Unknown and self.base == required_base

    def is_not_certain_base(self, required_base: PotionBases) -> bool:
        return self.base != PotionBases.Unknown and self.base != required_base

    # A customer will accept the potion without additional requests, if any required effect is satisfied with at least 1 equivalent tier.
    def is_accepted(self, required_effects: list[Effects], exact: bool = False) -> bool:
        if not exact:
            return max(self.effect_tier_list[effect] for effect in required_effects) > 0
        assert self.is_exact
        _max_required_tier = 0
        for effect in required_effects:
            _this_equivalent_tier = self.effect_tier_list[effect]
            for extra_effect in Effects:
                if extra_effect != effect and self.effect_tier_list[extra_effect] > 0 and Compatibility[effect.value][extra_effect.value] == 0:
                    _this_equivalent_tier -= self.effect_tier_list[extra_effect]
            _max_required_tier = max(_max_required_tier, _this_equivalent_tier)
        return _max_required_tier > 0

    # A customer will consider extra effect requirement satisfied, if any required effect is satisfied with at least 1 equivalent tier and
    # has at least 1 extra effect.
    def extra_effects(self, required_effects: list[Effects], exact: bool = False) -> int:
        assert len(required_effects) > 0
        _max_extra_effects = 0
        if exact and not self.is_exact:
            return -1

        for effect in required_effects:
            _this_extra_effects = 0
            _this_equivalent_tier = self.effect_tier_list[effect.value]
            for extra_effect in Effects:
                if extra_effect != effect and self.effect_tier_list[extra_effect] > 0:
                    # check Compatibility:
                    if Compatibility[effect.value][extra_effect.value] == 1:
                        _this_extra_effects += 1
                    elif exact:
                        # cancel out _this_equivalent_tier if the recipe is exact:
                        _this_equivalent_tier -= self.effect_tier_list[extra_effect]
            if _this_equivalent_tier > 0:
                _max_extra_effects = max(_max_extra_effects, _this_extra_effects)
        return min(_max_extra_effects, 4)

    # If the recipe contains effects with legal levels.
    @property
    def is_valid(self) -> bool:
        return all(0 <= tier <= 3 for tier in self.effect_tier_list)

    # If the recipe contains exact effect levels to acquire.
    @property
    def is_exact(self) -> bool:
        return (sum(self.effect_tier_list) <= 5) and all(0 <= tier <= 3 for tier in self.effect_tier_list)

    # TODO: price calculation


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
    print(recipe.extra_effects([Effects.Lightning], exact=False))


if __name__ == "__main__":
    test()
