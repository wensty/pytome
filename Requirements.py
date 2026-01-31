from abc import ABC, abstractmethod

from Recipes import Recipe, PotionBases
from Effects import Effects
from Ingredients import Ingredients


class Requirements(ABC):
    @abstractmethod
    def is_satisfied(self, recipe: Recipe) -> bool:
        pass

    @property
    @abstractmethod
    def mult(self) -> float:
        pass


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
        self.k = k

    def is_satisfied(self, recipe: Recipe) -> bool:
        return sum(1 if ingredient > 0 else 0 for ingredient in recipe.ingredient_num_list) <= self.k

    @property
    def mult(self) -> float:
        return 1.5 if self.k == 1 else 2.0 if self.k == 2 else 3.0


class WeakRecipe(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.is_weak(self.required_effects, self.exact)

    @property
    def mult(self) -> float:
        return 3.0


class StrongRecipe(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.is_strong(self.required_effects, self.exact)

    @property
    def mult(self) -> float:
        return 1.5


class AddOneIngredient(Requirements):
    def __init__(self, required_ingredient: Ingredients) -> None:
        self.required_ingredient = required_ingredient

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.contains_ingredient(self.required_ingredient)

    @property
    def mult(self) -> float:
        return 1.5


class AddHalfIngredient(Requirements):
    def __init__(self, required_ingredient: Ingredients) -> None:
        self.required_ingredient = required_ingredient

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.contains_half_ingredient(self.required_ingredient)

    @property
    def mult(self) -> float:
        return 2.0


class IsCertainBase(Requirements):
    def __init__(self, required_base: PotionBases) -> None:
        self.required_base = required_base

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.is_certain_base(self.required_base)

    @property
    def mult(self) -> float:
        return 2.0


class IsNotCertainBase(Requirements):
    def __init__(self, required_base: PotionBases) -> None:
        self.required_base = required_base

    def is_satisfied(self, recipe: Recipe) -> bool:
        return recipe.is_not_certain_base(self.required_base)

    @property
    def mult(self) -> float:
        return 1.5


class ExtraEffects(Requirements):
    def __init__(self, required_effects: list[Effects], exact: bool = False) -> None:
        self.required_effects = required_effects
        self.exact = exact
        self._mult = 1.0

    def is_satisfied(self, recipe: Recipe) -> bool:
        num = recipe.extra_effects(self.required_effects, self.exact)
        self._mult = [1.0, 1.25, 1.5, 2.5, 5.0][num]
        return num > 0

    @property
    def mult(self) -> float:
        return self._mult
