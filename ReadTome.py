import gzip
import pickle
import re
import pathlib
from typing import Union
from hashlib import md5

import openpyxl
from openpyxl_image_loader import SheetImageLoader

from Effects import NUMBER_OF_EFFECTS
from Recipes import Recipe, PotionBases
from Recipes import Ingredients, Salts, NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS
from Recipes import Potion, IngredientNumList, SaltGrainList
import Legendary
import SingleEffect

Numerical = Union[int, float]
Correction = {"Stentch": "Stench", "Rejuvination": "Rejuvenation"}


def readTome():
    def toInt(x):
        if isinstance(x, Numerical):
            return int(x)
        if isinstance(x, str) and x.isnumeric():
            return int(x)
        return 0

    tome = openpyxl.open("data/tome.xlsx", data_only=True)
    recipeDump: set[Recipe] = set()

    ## Reading RecipeDump page
    tomeRecipeDump = tome["Recipe Dump"]
    recipeDumpCount = 0
    row = 2  # First meaningful row.
    while True:
        row += 1
        recipeTitle = tomeRecipeDump.cell(row, 1).value
        if recipeTitle is not None:
            recipeTitle = str(recipeTitle)
            legendaryPattern = re.compile(r"^([a-zA-Z]*) ([a-zA-Z]*)-(\d*)('?)$")
            singleEffectPattern = re.compile(r"^([a-zA-z]*) ?((?:[a-zA-z]*)?)('?)$")
            legendaryMatch = re.match(legendaryPattern, recipeTitle)
            if legendaryMatch is not None:
                groups = legendaryMatch.groups()
                key = f"{groups[0]}{groups[1]}_{groups[2]}"
                if key in Correction:
                    key = Correction[key]
                potion: Potion = Legendary.__dict__[key]
                hidden = bool(groups[3])
            else:
                singleEffectMatch = re.match(singleEffectPattern, recipeTitle)
                if singleEffectMatch is not None:
                    groups = singleEffectMatch.groups()
                    key = "".join([groups[0], groups[1]])
                    key = Correction.get(key, key)
                    tier = tomeRecipeDump.cell(row, 2).value
                    if isinstance(tier, Numerical):
                        tier = int(tier)
                        if not (1 <= tier <= 3):
                            print(f"Unexpected tier {tier} for single effects found at row {row}.")
                            continue
                    else:
                        print(f"Tier for single effect potion is not a number at row {row}.")
                        continue
                    key = ["Weak", "", "Strong"][tier - 1] + key
                    potion: Potion = SingleEffect.__dict__[key]
                    hidden = bool(groups[2])
                else:
                    # These recipes are temperarily removed because difficulty to makein real game.
                    print(f"Potion title matched neither legendary potions nor single effect potions at row {row}.")
                    continue
            baseTitle = tomeRecipeDump.cell(row, 3).value
            match baseTitle:
                case "Wa":
                    base = PotionBases.Water
                case "O":
                    base = PotionBases.Oil
                case "Wi":
                    base = PotionBases.Wine
                case _:
                    print(f"Unexpected baseTitle {baseTitle} assigned at row {row}.")
                    continue

            # toInt = lambda x: int(x) if x is not None else 0
            _ingredientNums = IngredientNumList(toInt(tomeRecipeDump.cell(row, col).value) for col in range(20, 78))
            _saltGrains = SaltGrainList(toInt(tomeRecipeDump.cell(row, col).value) for col in range(78, 83))
            plotterLink = str(tomeRecipeDump.cell(row, 84).value)
            discordLink = tomeRecipeDump.cell(row, 17).hyperlink
            discordLink = str(discordLink) if discordLink else ""
            hidden = hidden or not (bool(plotterLink) or bool(discordLink))
            # recipe = Recipe(potion, base, ingredientNums, saltGrains, plotterLink, discordLink)
            if hidden:
                print(f"Info: row {row} is a hidden recipe.")
            recipe = Recipe(base, potion, _ingredientNums, _saltGrains, discord_link=discordLink, plotter_link=plotterLink, hidden=hidden)
            if recipe in recipeDump:
                print(f"row {row} records an identical recipe recorded before.")
            else:
                recipeDump.add(recipe)
                recipeDumpCount += 1

        else:
            # last recipe row.
            break
    print(f"Reading {recipeDumpCount} recipes from recipe dump page.")

    ### Reading SaltySkirt page.
    tomeSaltySkirt = tome["Salty Skirt"]
    colLetters = "ABCDE"
    imageLoader = SheetImageLoader(tomeSaltySkirt)
    saltySkirtCount = 0
    if not pathlib.Path("iconMD5s.pkl.gz").exists():
        effectMD5s = readIconMD5()
        with gzip.open("data/iconMD5s.pkl.gz", "wb") as f:
            pickle.dump(effectMD5s, f)
    else:
        with gzip.open("data/iconMD5s.pkl.gz", "rb") as f:
            effectMD5s = pickle.load(f)

    for row in range(10, 204):  # currently not collecting backups.
        if imageLoader.image_in(f"A{row}"):
            effectTiers = [0] * NUMBER_OF_EFFECTS
            for col in range(5):
                if imageLoader.image_in(f"{colLetters[col]}{row}"):
                    effectIcon = imageLoader.get(f"{colLetters[col]}{row}")
                    effectMD5 = md5(pickle.dumps(effectIcon)).hexdigest()
                    effect = effectMD5s[effectMD5]
                    effectTiers[effect] += 1
            potion = Potion(effectTiers)
            # We can not retrieve the base from the page itself.
            _ingredientNums = [0] * NUMBER_OF_INGREDIENTS
            _ingredientNums[Ingredients.PhantomSkirt] += toInt(tomeSaltySkirt.cell(row, 16).value)
            _ingredientNums[Ingredients.GraveTruffle] += toInt(tomeSaltySkirt.cell(row, 17).value)
            _ingredientNums[Ingredients.Watercap] += toInt(tomeSaltySkirt.cell(row, 18).value)
            _ingredientNums[Ingredients.Goldthorn] += toInt(tomeSaltySkirt.cell(row, 19).value)
            _ingredientNums[Ingredients.Boombloom] += toInt(tomeSaltySkirt.cell(row, 20).value)
            _ingredientNums[Ingredients.RainbowCap] += toInt(tomeSaltySkirt.cell(row, 21).value)
            _ingredientNums[Ingredients.FrostSapphire] += toInt(tomeSaltySkirt.cell(row, 22).value)
            ingredientNumList = IngredientNumList(_ingredientNums)
            _saltGrains = [0] * NUMBER_OF_SALTS
            _saltGrains[Salts.Moon] += toInt(tomeSaltySkirt.cell(row, 13).value)
            _saltGrains[Salts.Sun] += toInt(tomeSaltySkirt.cell(row, 14).value)
            _saltGrains[Salts.Life] += toInt(tomeSaltySkirt.cell(row, 15).value)
            saltGrainsList = SaltGrainList(_saltGrains)
            plotterLink = tomeSaltySkirt.cell(row, 7).hyperlink
            plotterLink = plotterLink.target if plotterLink else ""
            plotterLink = str(plotterLink) if plotterLink else ""
            recipe = Recipe(PotionBases.Unknown, potion, ingredientNumList, saltGrainsList, plotter_link=plotterLink)
            if recipe not in recipeDump:
                recipeDump.add(recipe)
                saltySkirtCount += 1
            # print(potion)
            # print(ingredientNumList)
            # print(saltGrainsList)
            # input()
        else:
            continue
    print(f"Completed reading {saltySkirtCount} additional recipes from salty skirt page.")
    return recipeDump


def readIconMD5():

    tomeSaltySkirt = openpyxl.open("data/tome.xlsx", data_only=True)["Salty Skirt"]
    imageLoader = SheetImageLoader(tomeSaltySkirt)

    exampleIconRows = [
        166,
        140,
        151,
        158,
        141,
        169,
        153,
        156,
        146,
        147,
        142,
        143,
        167,
        159,
        152,
        177,
        186,
        144,
        161,
        187,
        172,
        148,
        168,
        162,
        163,
        176,
        160,
        185,
        154,
        170,
        174,
        171,
        149,
        157,
        188,
        164,
        150,
        190,
        175,
        189,
        173,
    ]
    iconMD5 = {}
    for index, row in enumerate(exampleIconRows):
        image = imageLoader.get(f"A{row}")
        iconMD5[md5(pickle.dumps(image)).hexdigest()] = index
    return iconMD5


if __name__ == "__main__":
    # print(readIconMD5())
    readTome()
