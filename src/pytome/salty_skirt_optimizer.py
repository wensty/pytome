from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil
from pathlib import Path
from typing import Any, Iterable
import gzip
import pickle

from .common import BATCH_PRODUCTION_COST_RATE, BATCH_PRODUCTION_RATE, SALT_BATCH_SIZES, SALT_MASTERY_MULT
from .ingredients import NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS, Salts
from .legendary import LegendaryComponent, get_legendary_salt_requirements
from .recipe_database import load_recipes
from .recipes import Potion, Recipe


@dataclass(frozen=True)
class OrderRecipeChoice:
    component_group: str
    potion_signature: tuple[int, ...]
    recipe: Recipe


@dataclass(frozen=True)
class SaltOrderVector:
    target_salt: Salts
    produced_units: int
    ingredient_cost: int
    ingredient_consumption: tuple[int, ...]
    salt_consumption: tuple[int, ...]
    choices: tuple[OrderRecipeChoice, ...]


@dataclass(frozen=True)
class SaltOptimizationResult:
    target_salt: Salts
    ingredient_cost: int
    ingredient_cost_per_unit: float


@dataclass(frozen=True)
class SaltySkirtReport:
    order_vectors: dict[Salts, SaltOrderVector]
    per_salt_optima: dict[Salts, SaltOptimizationResult]
    iteration_count: int = 0
    from_cache: bool = False


def _potion_signature(potion: Potion) -> tuple[int, ...]:
    return tuple(int(v) for v in potion)


def _recipe_signature(recipe: Recipe) -> tuple[int, ...]:
    return tuple(int(v) for v in recipe.effect_tier_list)


def _sum_ingredients(recipe: Recipe) -> int:
    return sum(int(v) for v in recipe.ingredient_num_list)


def _sum_salts(recipe: Recipe) -> int:
    return sum(int(v) for v in recipe.salt_grain_list)


def _build_requirement_pool() -> dict[Salts, list[LegendaryComponent]]:
    grouped = get_legendary_salt_requirements()
    return {
        Salts.Void: list(grouped["Void"]),
        Salts.Moon: list(grouped["Moon"]),
        Salts.Sun: list(grouped["Sun"]),
        Salts.Life: list(grouped["Life"]),
        Salts.Philosopher: list(grouped["Philosopher"]),
    }


def _recipe_satisfies_requirement(recipe: Recipe, potion_signature: tuple[int, ...]) -> bool:
    recipe_tiers = _recipe_signature(recipe)
    for idx, required_tier in enumerate(potion_signature):
        if required_tier > 0 and recipe_tiers[idx] < required_tier:
            return False
    return True


def _ceil_batch_cost(total_cost: int) -> int:
    return int(ceil(float(total_cost) * BATCH_PRODUCTION_RATE * BATCH_PRODUCTION_COST_RATE))


def _produced_units(salt: Salts) -> int:
    return int(SALT_BATCH_SIZES[int(salt)] * SALT_MASTERY_MULT * BATCH_PRODUCTION_RATE)


def _is_dominated(lhs: Recipe, rhs: Recipe) -> bool:
    # lhs dominated by rhs if rhs is componentwise <= lhs
    # on both ingredient and salt vectors, with at least one strict.
    lhs_ing = tuple(int(v) for v in lhs.ingredient_num_list)
    rhs_ing = tuple(int(v) for v in rhs.ingredient_num_list)
    lhs_salt = tuple(int(v) for v in lhs.salt_grain_list)
    rhs_salt = tuple(int(v) for v in rhs.salt_grain_list)
    leq_ing = all(rhs_value <= lhs_value for lhs_value, rhs_value in zip(lhs_ing, rhs_ing))
    leq_salt = all(rhs_value <= lhs_value for lhs_value, rhs_value in zip(lhs_salt, rhs_salt))
    if not (leq_ing and leq_salt):
        return False
    strict_ing = any(rhs_value < lhs_value for lhs_value, rhs_value in zip(lhs_ing, rhs_ing))
    strict_salt = any(rhs_value < lhs_value for lhs_value, rhs_value in zip(lhs_salt, rhs_salt))
    return strict_ing or strict_salt


def _prune_dominated(candidates: list[Recipe]) -> list[Recipe]:
    kept: list[Recipe] = []
    for idx, candidate in enumerate(candidates):
        dominated = False
        for jdx, other in enumerate(candidates):
            if idx == jdx:
                continue
            if _is_dominated(candidate, other):
                dominated = True
                break
        if not dominated:
            kept.append(candidate)
    return kept or candidates


def _build_candidate_pool(
    recipes: Iterable[Recipe],
    requirement_pool: dict[Salts, list[LegendaryComponent]],
) -> dict[tuple[Salts, int], tuple[tuple[int, ...], list[Recipe]]]:
    pool: dict[tuple[Salts, int], tuple[tuple[int, ...], list[Recipe]]] = {}
    all_recipes = list(recipes)
    for salt, requirements in requirement_pool.items():
        for potion_idx, requirement in enumerate(requirements):
            sig = _potion_signature(requirement.potion)
            candidates = [recipe for recipe in all_recipes if _recipe_satisfies_requirement(recipe, sig)]
            if not candidates:
                raise ValueError(f"No recipe found for required potion signature in {salt.salt_name}.")
            pool[(salt, potion_idx)] = (sig, _prune_dominated(candidates))
    return pool


def _build_order_vector(
    salt: Salts,
    choices: list[OrderRecipeChoice],
) -> SaltOrderVector:
    ingredient_consumption = [0] * NUMBER_OF_INGREDIENTS
    salt_consumption = [0] * NUMBER_OF_SALTS
    for choice in choices:
        recipe = choice.recipe
        for idx, amount in enumerate(recipe.ingredient_num_list):
            ingredient_consumption[idx] += int(amount)
        for idx, amount in enumerate(recipe.salt_grain_list):
            salt_consumption[idx] += int(amount)
    rounded_ingredients = tuple(_ceil_batch_cost(value) for value in ingredient_consumption)
    rounded_salts = tuple(_ceil_batch_cost(value) for value in salt_consumption)
    return SaltOrderVector(
        target_salt=salt,
        produced_units=_produced_units(salt),
        ingredient_cost=sum(rounded_ingredients),
        ingredient_consumption=rounded_ingredients,
        salt_consumption=rounded_salts,
        choices=tuple(choices),
    )


def _solve_single_salt_milp(
    salt: Salts,
    candidate_pool: dict[tuple[Salts, int], tuple[tuple[int, ...], list[Recipe]]],
    requirement_pool: dict[Salts, list[LegendaryComponent]],
    salt_prices: dict[Salts, float],
) -> SaltOrderVector:
    try:
        from pyscipopt import Model, quicksum
    except Exception as exc:
        raise RuntimeError("PySCIPOpt is required for Salty Skirt optimization.") from exc

    requirements = requirement_pool[salt]
    model = Model(f"salty_skirt_milp_{salt.name}")
    model.hideOutput()
    batch_scale = float(BATCH_PRODUCTION_RATE * BATCH_PRODUCTION_COST_RATE)

    x_vars: dict[tuple[int, int], Any] = {}
    for potion_idx in range(len(requirements)):
        _sig, candidates = candidate_pool[(salt, potion_idx)]
        for recipe_idx in range(len(candidates)):
            x_vars[(potion_idx, recipe_idx)] = model.addVar(
                name=f"x_{potion_idx}_{recipe_idx}",
                vtype="BINARY",
            )
        model.addCons(quicksum(x_vars[(potion_idx, recipe_idx)] for recipe_idx in range(len(candidates))) == 1)

    y_vars: dict[int, Any] = {}
    z_vars: dict[int, Any] = {}
    for ing_idx in range(NUMBER_OF_INGREDIENTS):
        y_var = model.addVar(name=f"y_{ing_idx}", vtype="INTEGER", lb=0)
        y_vars[ing_idx] = y_var
        terms: list[Any] = []
        for potion_idx in range(len(requirements)):
            _sig, candidates = candidate_pool[(salt, potion_idx)]
            for recipe_idx, recipe in enumerate(candidates):
                terms.append(float(recipe.ingredient_num_list[ing_idx]) * x_vars[(potion_idx, recipe_idx)])
        model.addCons(y_var >= batch_scale * quicksum(terms))

    for salt_idx in range(NUMBER_OF_SALTS):
        z_var = model.addVar(name=f"z_{salt_idx}", vtype="INTEGER", lb=0)
        z_vars[salt_idx] = z_var
        terms = []
        for potion_idx in range(len(requirements)):
            _sig, candidates = candidate_pool[(salt, potion_idx)]
            for recipe_idx, recipe in enumerate(candidates):
                terms.append(float(recipe.salt_grain_list[salt_idx]) * x_vars[(potion_idx, recipe_idx)])
        model.addCons(z_var >= batch_scale * quicksum(terms))

    objective = quicksum(y_vars[idx] for idx in range(NUMBER_OF_INGREDIENTS)) + quicksum(
        float(salt_prices[Salts(idx)]) * z_vars[idx] for idx in range(NUMBER_OF_SALTS)
    )
    model.setObjective(objective, "minimize")
    model.optimize()
    if str(model.getStatus()).lower() != "optimal":
        raise RuntimeError(f"SCIP did not find an optimal MILP reaction plan for {salt.salt_name}.")

    choices: list[OrderRecipeChoice] = []
    for potion_idx, requirement in enumerate(requirements):
        sig, candidates = candidate_pool[(salt, potion_idx)]
        selected_recipe_idx = max(
            range(len(candidates)),
            key=lambda recipe_idx: float(model.getVal(x_vars[(potion_idx, recipe_idx)])),
        )
        choices.append(OrderRecipeChoice(component_group=requirement.group, potion_signature=sig, recipe=candidates[selected_recipe_idx]))
    return _build_order_vector(salt, choices)


def _solve_salt_price_lp(order_vectors: dict[Salts, SaltOrderVector]) -> dict[Salts, float]:
    try:
        from pyscipopt import Model, quicksum
    except Exception as exc:
        raise RuntimeError("PySCIPOpt is required for Salty Skirt optimization.") from exc

    model = Model("salty_skirt_price_lp")
    model.hideOutput()
    price_vars = {salt: model.addVar(name=f"p_{salt.name}", vtype="CONTINUOUS", lb=0.0) for salt in Salts}

    for salt in Salts:
        vector = order_vectors[salt]
        lhs = float(vector.produced_units) * price_vars[salt]
        rhs = float(vector.ingredient_cost) + quicksum(float(vector.salt_consumption[idx]) * price_vars[Salts(idx)] for idx in range(NUMBER_OF_SALTS))
        model.addCons(lhs >= rhs)

    model.setObjective(quicksum(price_vars[salt] for salt in Salts), "minimize")
    model.optimize()
    if str(model.getStatus()).lower() != "optimal":
        raise RuntimeError("SCIP did not find an optimal salt-price LP solution.")

    return {salt: float(model.getVal(price_vars[salt])) for salt in Salts}


def _initial_salt_prices(order_vectors: dict[Salts, SaltOrderVector]) -> dict[Salts, float]:
    prices: dict[Salts, float] = {}
    for salt in Salts:
        vector = order_vectors[salt]
        prices[salt] = float(vector.ingredient_cost) / max(1.0, float(vector.produced_units))
    return prices


def _requirements_signature(
    requirement_pool: dict[Salts, list[LegendaryComponent]],
) -> tuple[tuple[int, tuple[tuple[str, tuple[int, ...]], ...]], ...]:
    return tuple(
        (
            int(salt),
            tuple((item.group, tuple(int(v) for v in item.potion)) for item in requirements),
        )
        for salt, requirements in requirement_pool.items()
    )


def _cache_path(db_path: Path) -> Path:
    return db_path.parent / "salty_skirt_cache.pkl.gz"


def _load_cached_report(
    db_path: Path,
    requirement_sig: tuple[tuple[int, tuple[tuple[str, tuple[int, ...]], ...]], ...],
    max_iterations: int | None,
) -> SaltySkirtReport | None:
    path = _cache_path(db_path)
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rb") as f:
            payload = pickle.load(f)
        if not isinstance(payload, dict):
            return None
        if payload.get("schema") != 2:
            return None
        if payload.get("db_mtime_ns") != db_path.stat().st_mtime_ns:
            return None
        if payload.get("db_size") != db_path.stat().st_size:
            return None
        if payload.get("requirement_sig") != requirement_sig:
            return None
        if payload.get("max_iterations") != max_iterations:
            return None
        report = payload.get("report")
        if not isinstance(report, SaltySkirtReport):
            return None
        return replace(report, from_cache=True)
    except Exception:
        return None


def _save_cached_report(
    db_path: Path,
    requirement_sig: tuple[tuple[int, tuple[tuple[str, tuple[int, ...]], ...]], ...],
    max_iterations: int | None,
    report: SaltySkirtReport,
) -> None:
    path = _cache_path(db_path)
    payload = {
        "schema": 2,
        "db_mtime_ns": db_path.stat().st_mtime_ns,
        "db_size": db_path.stat().st_size,
        "requirement_sig": requirement_sig,
        "max_iterations": max_iterations,
        "report": replace(report, from_cache=False),
    }
    with gzip.open(path, "wb") as f:
        pickle.dump(payload, f)


def _iterative_joint_vectors(
    candidate_pool: dict[tuple[Salts, int], tuple[tuple[int, ...], list[Recipe]]],
    requirement_pool: dict[Salts, list[LegendaryComponent]],
    initial_prices: dict[Salts, float],
    max_iter: int | None = None,
    tol: float = 1e-4,
) -> tuple[dict[Salts, SaltOrderVector], dict[Salts, float], int]:
    prices = dict(initial_prices)
    vectors: dict[Salts, SaltOrderVector] = {}
    iterations = 0
    while True:
        vectors = {
            salt: _solve_single_salt_milp(
                salt=salt,
                candidate_pool=candidate_pool,
                requirement_pool=requirement_pool,
                salt_prices=prices,
            )
            for salt in Salts
        }
        new_prices = _solve_salt_price_lp(vectors)
        diff = max(abs(float(new_prices[s]) - float(prices[s])) for s in Salts)
        prices = new_prices
        iterations += 1
        if diff <= tol:
            break
        if max_iter is not None and iterations >= max_iter:
            break
    return vectors, prices, iterations


def build_salt_order_vectors(db_path: Path) -> dict[Salts, SaltOrderVector]:
    recipes = [recipe for recipe in load_recipes(db_path=db_path) if not bool(recipe.hidden)]
    requirement_pool = _build_requirement_pool()
    candidate_pool = _build_candidate_pool(recipes, requirement_pool)

    vectors: dict[Salts, SaltOrderVector] = {}
    for salt, requirements in requirement_pool.items():
        choices: list[OrderRecipeChoice] = []
        for potion_idx, requirement in enumerate(requirements):
            sig, candidates = candidate_pool[(salt, potion_idx)]
            best = min(
                candidates,
                key=lambda recipe: (
                    _sum_ingredients(recipe),
                    _sum_salts(recipe),
                    sum(int(v) for v in recipe.effect_tier_list),
                ),
            )
            choices.append(OrderRecipeChoice(component_group=requirement.group, potion_signature=sig, recipe=best))
        vectors[salt] = _build_order_vector(salt, choices)
    return vectors


def solve_for_target_salt(
    order_vectors: dict[Salts, SaltOrderVector] | None,
    target_salt: Salts,
    target_units: int | None = None,
) -> SaltOptimizationResult:
    if order_vectors is None:
        raise ValueError("order_vectors is required for LP solve.")
    if target_units is None:
        target_units = int(order_vectors[target_salt].produced_units)
    if target_units <= 0:
        raise ValueError("Target units must be > 0.")

    try:
        from pyscipopt import Model, quicksum
    except Exception as exc:
        raise RuntimeError("PySCIPOpt is required for Salty Skirt optimization.") from exc

    model = Model(f"salty_skirt_lp_{target_salt.name}")
    model.hideOutput()
    t_vars = {salt: model.addVar(name=f"t_{salt.name}", vtype="CONTINUOUS", lb=0.0) for salt in Salts}

    for balance_salt in Salts:
        lhs = quicksum(
            (float(order_vectors[s].produced_units if s == balance_salt else 0) - float(order_vectors[s].salt_consumption[int(balance_salt)])) * t_vars[s]
            for s in Salts
        )
        if balance_salt == target_salt:
            model.addCons(lhs >= float(target_units))
        else:
            model.addCons(lhs >= 0.0)

    objective = quicksum(float(order_vectors[salt].ingredient_cost) * t_vars[salt] for salt in Salts)
    model.setObjective(objective, "minimize")

    model.optimize()
    if str(model.getStatus()).lower() != "optimal":
        raise RuntimeError(f"SCIP did not find an optimal LP mixing solution for {target_salt.salt_name}.")

    order_counts: list[float] = [0.0] * NUMBER_OF_SALTS
    ingredient_cost = 0.0
    for salt in Salts:
        value = float(model.getVal(t_vars[salt]))
        count = max(0.0, value)
        normalized = float(round(count)) if abs(count - round(count)) <= 1e-9 else count
        order_counts[int(salt)] = normalized
        ingredient_cost += float(order_vectors[salt].ingredient_cost) * float(count)

    return SaltOptimizationResult(
        target_salt=target_salt,
        ingredient_cost=int(round(ingredient_cost)),
        ingredient_cost_per_unit=float(ingredient_cost) / float(target_units),
    )


def build_salty_skirt_report(
    db_path: Path,
    max_iterations: int | None = None,
    force_refresh: bool = False,
) -> SaltySkirtReport:
    recipes = [recipe for recipe in load_recipes(db_path=db_path) if not bool(recipe.hidden)]
    requirement_pool = _build_requirement_pool()
    requirement_sig = _requirements_signature(requirement_pool)
    if not force_refresh:
        cached = _load_cached_report(db_path=db_path, requirement_sig=requirement_sig, max_iterations=max_iterations)
        if cached is not None:
            return cached
    candidate_pool = _build_candidate_pool(recipes, requirement_pool)
    initial_vectors = build_salt_order_vectors(db_path=db_path)
    initial_prices = _initial_salt_prices(initial_vectors)
    vectors, _prices, iteration_count = _iterative_joint_vectors(
        candidate_pool,
        requirement_pool,
        initial_prices=initial_prices,
        max_iter=max_iterations,
    )
    per_salt_optima = {salt: solve_for_target_salt(vectors, salt) for salt in Salts}
    report = SaltySkirtReport(
        order_vectors=vectors,
        per_salt_optima=per_salt_optima,
        iteration_count=iteration_count,
        from_cache=False,
    )
    _save_cached_report(db_path=db_path, requirement_sig=requirement_sig, max_iterations=max_iterations, report=report)
    return report
