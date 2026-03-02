from enum import IntEnum
from typing import Optional

from .Recipes import Recipe
from .Effects import Effects
from .Requirements import Requirements


class Difficulty(IntEnum):
    Explorer = 0
    Classic = 1
    Grandmaster = 2
    Suffering = 3


class ProfitStat:
    def __init__(
        self,
        difficulty=Difficulty.Explorer,
        *,
        popularity=0,
        trading=0,
        sell_potions_to_merchant=0,
        potion_promotion=0,
        great_potion_demand=0,
        customers_served=0,
        talented_potion_seller=0,
    ) -> None:
        self.difficulty = difficulty
        assert 0 <= popularity
        self.popularity = popularity
        assert 0 <= trading <= 20
        self.trading = trading
        assert 0 <= sell_potions_to_merchant <= 2
        self.sell_potions_to_merchant = sell_potions_to_merchant
        assert 0 <= potion_promotion <= 5
        self.potion_promotion = potion_promotion
        assert 0 <= great_potion_demand <= 2
        self.great_potion_demand = great_potion_demand
        assert 0 <= customers_served
        self.customers_served = customers_served
        assert 0 <= talented_potion_seller
        self.talented_potion_seller = talented_potion_seller

    @classmethod
    def fully_talented_stat(cls, difficulty=Difficulty.Explorer, *, popularity=0, customers_served=0, talented_potion_seller=0) -> "ProfitStat":
        return cls(
            difficulty=difficulty,
            popularity=popularity,
            trading=20,
            sell_potions_to_merchant=2,
            potion_promotion=5,
            great_potion_demand=2,
            customers_served=customers_served,
            talented_potion_seller=talented_potion_seller,
        )

    @property
    def is_valid(self) -> bool:
        return (
            0 <= self.popularity
            and 0 <= self.trading <= 20
            and 0 <= self.sell_potions_to_merchant <= 2
            and 0 <= self.potion_promotion <= 5
            and 0 <= self.great_potion_demand <= 2
            and 0 <= self.customers_served
            and 0 <= self.talented_potion_seller
        )

    @property
    def _mult_popularity(self) -> float:
        _mult = 1.0
        _popularity_1 = min(self.popularity, 15)
        _popularity_2 = self.popularity - _popularity_1
        _mult *= [1, 1.1, 1.1, 1.1, 1.1, 1.2, 1.2, 1.3, 1.3, 1.3, 1.4, 1.4, 1.4, 1.5, 1.5, 1.6][_popularity_1] + 0.01 * _popularity_2
        return _mult

    @property
    def mult_customers(self) -> float:
        _mult = 0.25
        # difficulty
        _mult *= [2.0, 1.0, 0.4, 0.1][self.difficulty.value]
        # trading
        _mult *= 1 + 0.05 * self.trading
        _added_mult = 1.0
        # added buffs
        _added_mult += 0.01 * self.talented_potion_seller
        _added_mult += 0.01 * self.great_potion_demand * self.customers_served
        # _mult *= self._mult_popularity
        _added_mult += self._mult_popularity - 1
        # _mult *= 1 + 0.05 * self.potion_promotion
        _added_mult += 0.05 * self.potion_promotion
        _mult *= _added_mult
        return _mult

    def mult_merchant(self) -> float:
        _mult = 0.05
        # difficulty
        _mult *= [1.0, 1.0, 0.4, 0.1][self.difficulty.value]
        # trading
        _mult *= 1 + 0.05 * self.trading
        # sell potions to merchant
        _mult *= 1 + 0.25 * self.sell_potions_to_merchant
        return _mult


def calculate_profit(
    recipe: Recipe, profit_stat: ProfitStat, *, required_effects: Optional[list[Effects]] = None, requests: Optional[list[Requirements]] = None
) -> float:
    _base_price = recipe.base_price(required_effects)
    _profit_type = "merchant" if required_effects is None else "customer"
    if _profit_type == "merchant":
        if requests is not None:
            raise ValueError("Merchants do not make extra requests.")
        return _base_price * profit_stat.mult_merchant()
    if _profit_type == "customer":
        _profit = _base_price * profit_stat.mult_customers
        if requests is not None:
            if len(requests) > 4:
                raise ValueError("Customers can only make up to 4 requests.")
            for request in requests:
                _profit *= request.mult if request.is_satisfied(recipe) else 1.0
        return _profit
    raise NotImplementedError(f"calculate_profit is not implemented for {_profit_type} requests.")


if __name__ == "__main__":
    from .Effects import PotionBases
    from .Ingredients import NUMBER_OF_INGREDIENTS
    from .Recipes import EffectTierList, IngredientNumList, SaltGrainList

    _recipe = Recipe(
        base=PotionBases.Water,
        effect_tier_list=EffectTierList.from_name(Curse=2, Rage=3),
        ingredient_num_list=IngredientNumList([0] * NUMBER_OF_INGREDIENTS),
        salt_grain_list=SaltGrainList([0, 0, 0, 0, 0]),
        discord_link="",
        plotter_link="",
        hidden=False,
    )
    _profit_stat = ProfitStat(
        difficulty=Difficulty.Classic,
        popularity=24,
        trading=20,
        sell_potions_to_merchant=2,
        potion_promotion=5,
        great_potion_demand=1,
        customers_served=18,
        talented_potion_seller=84,
    )
    print(ProfitStat)
    print(_recipe.base_price([Effects.Curse, Effects.Rage]))
    print(_recipe.base_price())
    print(_profit_stat.mult_customers)
    print(_profit_stat.mult_merchant())
    print(calculate_profit(_recipe, _profit_stat, required_effects=[Effects.Curse, Effects.Rage]))
    print(calculate_profit(_recipe, _profit_stat))
