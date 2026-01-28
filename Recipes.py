import pickle
import gzip
from collections.abc import Sequence, Iterable

from Effects import NUMBER_OF_EFFECTS, Effects, PotionBases
from Ingredients import NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS, Ingredients, Salts

with gzip.open("data/Compatibility.pkl.gz", "rb") as f:
    Compatibility: list[list[int]] = pickle.load(f)


class EffectTierList(Sequence[int]):
    def __init__(self, effectTiers: Iterable[int]) -> None:
        self._effectTiers = tuple(effectTiers)
        assert len(self._effectTiers) == NUMBER_OF_EFFECTS

    def __getitem__(self, index):
        return self._effectTiers[index]

    def __len__(self):
        return len(self._effectTiers)

    def __repr__(self) -> str:
        return repr(self._effectTiers)

    @classmethod
    def fromName(cls, **kwargs):
        effectTiers = [0] * NUMBER_OF_EFFECTS
        for k, v in kwargs.items():
            if k in Effects.__members__:
                effectTiers[(Effects[k]).value] = v
        return cls(effectTiers)


# Type alias.
class Potion(EffectTierList):
    pass


class IngredientNumList(Sequence[int]):
    def __init__(self, ingredientNums: Iterable[int]) -> None:
        self._ingredientNums = tuple(ingredientNums)
        assert len(self._ingredientNums) == NUMBER_OF_INGREDIENTS

    def __getitem__(self, index):
        return self._ingredientNums[index]

    def __len__(self):
        return len(self._ingredientNums)

    def __repr__(self) -> str:
        return repr(self._ingredientNums)

    @classmethod
    def fromName(cls, **kwargs):
        ingredientNums = [0] * NUMBER_OF_INGREDIENTS
        for k, v in kwargs.items():
            if k in Ingredients.__members__:
                ingredientNums[(Ingredients[k]).value] = v
        return cls(ingredientNums)


class SaltGrainList(Sequence[int]):
    def __init__(self, saltGrains: Iterable[int]) -> None:
        self._saltGrains: tuple[int, ...] = tuple(saltGrains)
        assert len(self._saltGrains) == NUMBER_OF_SALTS

    def __getitem__(self, index):
        return self._saltGrains[index]

    def __len__(self):
        return len(self._saltGrains)

    def __repr__(self) -> str:
        return repr(self._saltGrains)

    @classmethod
    def fromName(cls, **kwargs):
        saltGrains = [0] * NUMBER_OF_SALTS
        for k, v in kwargs.items():
            if k in Salts.__members__:
                saltGrains[(Salts[k]).value] = v
        return cls(saltGrains)


class Recipe:
    def __init__(
        self,
        base: PotionBases,
        effectTierList: EffectTierList,
        ingredientNumList: IngredientNumList,
        saltGrainList: SaltGrainList,
        discord_link="",
        plotter_link="",
        hidden=False,
    ) -> None:
        self.base = base
        self.effectTierList = effectTierList
        self.ingredientNumList = ingredientNumList
        self.saltGrainList = saltGrainList
        self.discord_link = discord_link
        self.plotter_link = plotter_link
        self.hidden = hidden

    def __repr__(self) -> str:
        return f"Recipe({self.base}, {self.effectTierList}, {self.ingredientNumList}, {self.saltGrainList})"

    def isDull(self) -> bool:
        return all(salt == 0 for salt in self.saltGrainList)

    def isLowlander(self, k: int) -> bool:
        return sum(1 if ingredient > 0 else 0 for ingredient in self.ingredientNumList) <= k

    # A customer considers a potion weak, if all required effects exist in the potion is at most tier 1 and is accepted.
    def isWeak(self, requiredEffects: list[Effects], exact: bool = False) -> bool:
        assert len(requiredEffects) > 0
        if exact:
            if not self.isExact:
                return False
            return (
                self.isExact
                and all(self.effectTierList[effect] <= 1 for effect in requiredEffects)
                and any(self.effectTierList[effect] == 1 for effect in requiredEffects)
            )
        return any(self.effectTierList[effect] >= 1 for effect in requiredEffects)

    # A customer considers a potion strong, if any required effect exists in the potion is at least tier 3 and is accepted.
    def isStrong(self, requiredEffects: list[Effects], exact: bool = False) -> bool:
        assert len(requiredEffects) > 0
        if exact:
            if not self.isExact:
                return False
            return self.isExact and any(self.effectTierList[effect] >= 3 for effect in requiredEffects)
        return any(self.effectTierList[effect] == 3 for effect in requiredEffects)

    def containOneCertainIngredient(self, requiredIngredient: Ingredients) -> bool:
        return self.ingredientNumList[requiredIngredient] > 0

    def containHalfCertainIngredient(self, requiredIngredient: Ingredients) -> bool:
        return self.ingredientNumList[requiredIngredient] >= 0.5 * sum(self.ingredientNumList)

    def containNoCertainIngredient(self, requiredIngredient: Ingredients) -> bool:
        return self.ingredientNumList[requiredIngredient] == 0

    def isCertainBase(self, requiredBase: PotionBases) -> bool:
        return self.base != PotionBases.Unknown and self.base == requiredBase

    def isNotCertainBase(self, requiredBase: PotionBases) -> bool:
        return self.base != PotionBases.Unknown and self.base != requiredBase

    # A customer will accept the potion without additional requests, if any required effect is satisfied with at least 1 equivalent tier.
    def isAccepted(self, requiredEffects: list[Effects], exact: bool = False) -> bool:
        if not exact:
            return max(self.effectTierList[effect] for effect in requiredEffects) > 0
        assert self.isExact
        _max_required_tier = 0
        for effect in requiredEffects:
            _this_equivalent_tier = self.effectTierList[effect]
            for extra_effect in Effects:
                if extra_effect != effect and self.effectTierList[extra_effect] > 0 and Compatibility[effect.value][extra_effect.value] == 0:
                    _this_equivalent_tier -= self.effectTierList[extra_effect]
            _max_required_tier = max(_max_required_tier, _this_equivalent_tier)
        return _max_required_tier > 0

    # A customer will consider extra effect requirement satisfied, if any required effect is satisfied with at least 1 equivalent tier and
    # has at least 1 extra effect.
    def extraEffects(self, requiredEffects: list[Effects], exact: bool = False) -> int:
        assert len(requiredEffects) > 0
        _max_extra_effects = 0
        if exact and not self.isExact:
            return -1

        for effect in requiredEffects:
            _this_extra_effects = 0
            _this_equivalent_tier = self.effectTierList[effect.value]
            for extra_effect in Effects:
                if extra_effect != effect and self.effectTierList[extra_effect] > 0:
                    # check Compatibility:
                    if Compatibility[effect.value][extra_effect.value] == 1:
                        _this_extra_effects += 1
                    elif exact:
                        # cancel out _this_equivalent_tier if the recipe is exact:
                        _this_equivalent_tier -= self.effectTierList[extra_effect]
            if _this_equivalent_tier > 0:
                _max_extra_effects = max(_max_extra_effects, _this_extra_effects)
        return min(_max_extra_effects, 4)

    # If the recipe contains effects with legal levels.
    @property
    def isValid(self) -> bool:
        return all(0 <= tier <= 3 for tier in self.effectTierList)

    # If the recipe contains exact effect levels to acquire.
    @property
    def isExact(self) -> bool:
        return (sum(self.effectTierList) <= 5) and all(0 <= tier <= 3 for tier in self.effectTierList)

    # TODO: price calculation


def test():
    effectTierList = EffectTierList.fromName(Lightning=1, Fire=1, Poison=1, Healing=1, Dexterity=1)
    ingredientNumList = IngredientNumList.fromName(
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
    saltGrainList = SaltGrainList.fromName(Sun=100)
    recipe = Recipe(PotionBases.Water, effectTierList, ingredientNumList, saltGrainList)
    print(recipe.extraEffects([Effects.Lightning], exact=False))


if __name__ == "__main__":
    test()
