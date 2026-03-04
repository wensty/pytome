from abc import ABC, abstractmethod

from .recipes import Compatibility, Recipe, PotionBases
from .effects import Effects
from .ingredients import Ingredients


class Requirements(ABC):
    @abstractmethod
    def is_satisfied(self, recipe: Recipe) -> bool:
        pass

    @property
    @abstractmethod
    def mult(self) -> float:
        pass


class Accepted(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact

    def is_satisfied(self, recipe: Recipe) -> bool:
        if not self.exact:
            return any(recipe.effect_tier_list[effect] > 0 for effect in self.required_effects)
        if not recipe.is_exact_recipe:
            return False
        max_required_tier = 0
        for effect in self.required_effects:
            equivalent_tier = recipe.effect_tier_list[effect]
            for extra_effect in Effects:
                if extra_effect != effect and recipe.effect_tier_list[extra_effect] > 0 and Compatibility[effect.value][extra_effect.value] == 0:
                    equivalent_tier -= recipe.effect_tier_list[extra_effect]
            max_required_tier = max(max_required_tier, equivalent_tier)
        return max_required_tier > 0

    @property
    def mult(self) -> float:
        return 1.0


class DullRecipe(Requirements):
    def __init__(self) -> None:
        return

    def is_satisfied(self, recipe: Recipe) -> bool:
        return all(salt == 0 for salt in recipe.salt_grain_list)

    @property
    def mult(self) -> float:
        return 1.5


class LowlanderRecipe(Requirements):
    def __init__(self, k: int) -> None:
        assert 1 <= k <= 3
        self.k = k

    def is_satisfied(self, recipe: Recipe) -> bool:
        return sum(1 if ingredient > 0 else 0 for ingredient in recipe.ingredient_num_list) <= self.k

    @property
    def mult(self) -> float:
        return [3.0, 2.0, 1.5][self.k - 1]


class WeakRecipe(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact

    def is_satisfied(self, recipe: Recipe) -> bool:
        if not self.required_effects:
            return False
        if self.exact:
            if not recipe.is_exact_recipe:
                return False
            return all(recipe.effect_tier_list[effect] <= 1 for effect in self.required_effects) and any(
                recipe.effect_tier_list[effect] == 1 for effect in self.required_effects
            )
        return any(recipe.effect_tier_list[effect] >= 1 for effect in self.required_effects)

    @property
    def mult(self) -> float:
        return 3.0


class StrongRecipe(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact

    def is_satisfied(self, recipe: Recipe) -> bool:
        if not self.required_effects:
            return False
        if self.exact:
            if not recipe.is_exact_recipe:
                return False
            return any(recipe.effect_tier_list[effect] >= 3 for effect in self.required_effects)
        return any(recipe.effect_tier_list[effect] == 3 for effect in self.required_effects)

    @property
    def mult(self) -> float:
        return 1.5


class AddOneIngredient(Requirements):
    def __init__(self, required_ingredient: Ingredients) -> None:
        self.required_ingredient = required_ingredient

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.ingredient_num_list[self.required_ingredient] > 0

    @property
    def mult(self) -> float:
        return 1.5


class AddHalfIngredient(Requirements):
    def __init__(self, required_ingredient: Ingredients) -> None:
        self.required_ingredient = required_ingredient

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.ingredient_num_list[self.required_ingredient] >= 0.5 * sum(recipe.ingredient_num_list)

    @property
    def mult(self) -> float:
        return 2.0


class ExcludeIngredient(Requirements):
    def __init__(self, required_ingredient: Ingredients) -> None:
        self.required_ingredient = required_ingredient

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.ingredient_num_list[self.required_ingredient] == 0

    @property
    def mult(self) -> float:
        return 1.0


class IsCertainBase(Requirements):
    def __init__(self, required_base: PotionBases) -> None:
        self.required_base = required_base

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.base != PotionBases.Unknown and recipe.base == self.required_base

    @property
    def mult(self) -> float:
        return 2.0


class IsNotCertainBase(Requirements):
    def __init__(self, required_base: PotionBases) -> None:
        self.required_base = required_base

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.base != PotionBases.Unknown and recipe.base != self.required_base

    @property
    def mult(self) -> float:
        return 1.5


def count_extra_effects(recipe: Recipe, required_effects: list[Effects], exact: bool = False) -> int:
    if not required_effects:
        return 0
    max_extra_effects = 0
    if exact and not recipe.is_exact_recipe:
        return -1
    for effect in required_effects:
        extra_effects = 0
        equivalent_tier = recipe.effect_tier_list[effect.value]
        for extra_effect in Effects:
            if extra_effect != effect and recipe.effect_tier_list[extra_effect] > 0:
                if Compatibility[effect.value][extra_effect.value] == 1:
                    extra_effects += 1
                elif exact:
                    equivalent_tier -= recipe.effect_tier_list[extra_effect]
        if equivalent_tier > 0:
            max_extra_effects = max(max_extra_effects, extra_effects)
    return min(max_extra_effects, 4)


class ExtraEffects(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact
        self._mult = 1.0

    def is_satisfied(self, recipe: Recipe) -> bool:
        num = count_extra_effects(recipe, self.required_effects, self.exact)
        if num <= 0:
            self._mult = 1.0
            return False
        self._mult = [1.0, 1.25, 1.5, 2.5, 5.0][num]
        return True

    # need to be called afer the is_satisfied check.
    @property
    def mult(self) -> float:
        return self._mult
