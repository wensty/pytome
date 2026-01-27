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
        self._saltGrains = tuple(saltGrains)
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
        discordLink="",
        plotterLink="",
        hidden=False,
    ) -> None:
        self.base = base
        self.effectTierList = effectTierList
        self.ingredientNumList = ingredientNumList
        self.saltGrainList = saltGrainList
        self.discordLink = discordLink
        self.plotterlink = plotterLink
        self.hidden = hidden

    def __repr__(self) -> str:
        return f"Recipe({self.base}, {self.effectTierList}, {self.ingredientNumList}, {self.saltGrainList})"

    def isDull(self) -> bool:
        return all(salt == 0 for salt in self.saltGrainList)

    def isLowlander(self, k: int) -> bool:
        return sum(1 if ingredient > 0 else 0 for ingredient in self.ingredientNumList) <= k

    def isWeak(self, requiredEffects: list[Effects]) -> bool:
        return all(self.effectTierList[effect] <= 1 for effect in requiredEffects) if len(requiredEffects) > 0 else True

    def isStrong(self, requiredEffects: list[Effects]) -> bool:
        return any(self.effectTierList[effect] == 3 for effect in requiredEffects) if len(requiredEffects) > 0 else True

    def containOneCertainIngredient(self, requiredIngredient: Ingredients) -> bool:
        return self.ingredientNumList[requiredIngredient] > 0

    def containHalfCertainIngredient(self, requiredIngredient: Ingredients) -> bool:
        return self.ingredientNumList[requiredIngredient] >= 0.5 * sum(self.ingredientNumList)

    @property
    def isValid(self) -> bool:
        return sum(self.effectTierList) <= 5 and all(0 <= ingredientNum <= 3 for ingredientNum in self.ingredientNumList)

    # TODO: price calculation


def test():
    pass


if __name__ == "__main__":
    # for i in range(NUMBER_OF_EFFECTS):
    #     for j in range(NUMBER_OF_EFFECTS):
    #         if Compatibility[i][j] + Compatibility[j][i] == 1:
    #             ratio = Effects(i).basePrice / Effects(j).basePrice
    #             if min(ratio, 1 / ratio) >= 0.75:
    #                 print(f"{Effects(i).name} + {Effects(j).name}")
    print(True)
    print(EffectTierList.fromName(Lightning=3))
