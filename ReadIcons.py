from collections import deque
from pathlib import Path
from typing import cast

from PIL import Image
import openpyxl
from openpyxl_image_loader import SheetImageLoader

from Common import EXAMPLE_INGREDIENT_ICON_COLS, EXAMPLE_EFFECT_ICON_ROWS, EXAMPLE_SALT_ICON_COLS

from Ingredients import Ingredients, Salts
from Effects import Effects

IMAGE_DIR = Path("data/icons")
BACKGROUND_TOLERANCE = 150
OUTLINE_LUMA_THRESHOLD = 60
TARGET_MARGIN_RATIO = 0.08
SPECIAL_CASES = {
    "Foggy Parasol": {"tolerance": 80, "outline_luma_threshold": 80},
    "Firebell": {"tolerance": 80, "outline_luma_threshold": 80},
    "Witch Mushroom": {"tolerance": 80, "outline_luma_threshold": 80},
}


def save_ingredient_icons():
    (IMAGE_DIR / "ingredients").mkdir(parents=True, exist_ok=True)
    ingredient_sheet = openpyxl.open("data/tome.xlsx", data_only=True)["Dull Lowlander"]
    image_loader = SheetImageLoader(ingredient_sheet)
    for idx, col in enumerate(EXAMPLE_INGREDIENT_ICON_COLS):
        image = image_loader.get(f"{col}2")
        if image:
            ingredient_name = Ingredients(idx).ingredient_name
            settings = SPECIAL_CASES.get(
                ingredient_name,
                {"tolerance": BACKGROUND_TOLERANCE, "outline_luma_threshold": OUTLINE_LUMA_THRESHOLD},
            )
            image = _normalize_icon_image(
                image,
                remove_background=True,
                tolerance=settings["tolerance"],
                outline_luma_threshold=settings["outline_luma_threshold"],
            )
            image.save(f"{IMAGE_DIR}/ingredients/{ingredient_name}.png")


def save_effect_icons():
    (IMAGE_DIR / "effects").mkdir(parents=True, exist_ok=True)
    effect_sheet = openpyxl.open("data/tome.xlsx", data_only=True)["Salty Skirt"]
    image_loader = SheetImageLoader(effect_sheet)
    for index, row in enumerate(EXAMPLE_EFFECT_ICON_ROWS):
        image = image_loader.get(f"A{row}")
        if image:
            effect_name = Effects(index).effect_name
            image = _normalize_icon_image(
                image,
                remove_background=False,
                tolerance=BACKGROUND_TOLERANCE,
                outline_luma_threshold=OUTLINE_LUMA_THRESHOLD,
            )
            image.save(f"{IMAGE_DIR}/effects/{effect_name}.png")


def save_salt_icons():
    (IMAGE_DIR / "salts").mkdir(parents=True, exist_ok=True)
    salt_sheet = openpyxl.open("data/tome.xlsx", data_only=True)["Main Page"]
    image_loader = SheetImageLoader(salt_sheet)
    for index, col in enumerate(EXAMPLE_SALT_ICON_COLS):
        image = image_loader.get(f"{col}12")
        if image:
            salt_name = Salts(index).salt_name
            image = _normalize_icon_image(
                image,
                remove_background=False,
                tolerance=BACKGROUND_TOLERANCE,
                outline_luma_threshold=OUTLINE_LUMA_THRESHOLD,
            )
            image.save(f"{IMAGE_DIR}/salts/{salt_name}.png")


def _normalize_icon_image(
    image: Image.Image,
    remove_background: bool,
    tolerance: int,
    outline_luma_threshold: int,
) -> Image.Image:
    image = image.convert("RGBA")
    if remove_background:
        image = _remove_background(
            image,
            tolerance=tolerance,
            outline_luma_threshold=outline_luma_threshold,
        )
    image = _pad_to_square(image)
    image = _adjust_margin(image, TARGET_MARGIN_RATIO)
    return image.resize((256, 256), Image.Resampling.LANCZOS)


def _pad_to_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width == height:
        return image
    size = max(width, height)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    left = (size - width) // 2
    top = (size - height) // 2
    canvas.paste(image, (left, top))
    return canvas


def _adjust_margin(image: Image.Image, target_margin_ratio: float) -> Image.Image:
    size = image.size[0]
    image = _recenter_by_margins(image)
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    bbox_width = right - left
    bbox_height = bottom - top
    if bbox_width <= 0 or bbox_height <= 0:
        return image
    desired_margin = max(4, int(size * target_margin_ratio))
    avg_margin = (left + (size - right) + top + (size - bottom)) / 4
    max_bbox = max(bbox_width, bbox_height)
    max_bbox_target = max(1, size - 2 * desired_margin)
    if max_bbox_target <= 0 or max_bbox <= 0:
        return image
    scale_factor = max_bbox_target / max_bbox
    if abs(avg_margin - desired_margin) <= 1:
        return image
    new_size = max(1, int(size * scale_factor))
    resized = image.resize((new_size, new_size), Image.Resampling.LANCZOS)
    if scale_factor < 1.0:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        left = (size - new_size) // 2
        top = (size - new_size) // 2
        canvas.paste(resized, (left, top))
        return _recenter_by_margins(canvas)
    return _recenter_by_margins(_center_crop(resized, size))


def _center_crop(image: Image.Image, size: int) -> Image.Image:
    width, height = image.size
    if width == size and height == size:
        return image
    left = max(0, (width - size) // 2)
    top = max(0, (height - size) // 2)
    right = left + size
    bottom = top + size
    return image.crop((left, top, right, bottom))


def _recenter_by_margins(image: Image.Image) -> Image.Image:
    size = image.size[0]
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    margin_left = left
    margin_right = size - right
    margin_top = top
    margin_bottom = size - bottom
    shift_x = (margin_right - margin_left) // 2
    shift_y = (margin_bottom - margin_top) // 2
    if shift_x == 0 and shift_y == 0:
        return image
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(image, (shift_x, shift_y))
    return canvas


def _remove_background(image: Image.Image, tolerance: int, outline_luma_threshold: int) -> Image.Image:
    width, height = image.size
    tolerance_sq = tolerance * tolerance
    background = _estimate_background_color(image)

    def is_outline(pixel) -> bool:
        r, g, b, a = pixel
        if a <= 10:
            return False
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return luma <= outline_luma_threshold

    def is_background(pixel) -> bool:
        r, g, b, a = pixel
        if a <= 10:
            return True
        dr = r - background[0]
        dg = g - background[1]
        db = b - background[2]
        return (dr * dr + dg * dg + db * db) <= tolerance_sq

    queue = deque()
    visited = set()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        pixel = cast(tuple[int, int, int, int], image.getpixel((x, y)))
        if is_outline(pixel):
            continue
        if not is_background(pixel):
            continue
        image.putpixel((x, y), (0, 0, 0, 0))
        if x > 0:
            queue.append((x - 1, y))
        if x < width - 1:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y < height - 1:
            queue.append((x, y + 1))

    return image


def _estimate_background_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    sample_size = max(2, min(10, width // 10, height // 10))
    samples = []
    corners = [
        (0, 0),
        (width - sample_size, 0),
        (0, height - sample_size),
        (width - sample_size, height - sample_size),
    ]
    for start_x, start_y in corners:
        for x in range(start_x, min(start_x + sample_size, width)):
            for y in range(start_y, min(start_y + sample_size, height)):
                r, g, b, a = cast(tuple[int, int, int, int], image.getpixel((x, y)))
                if a > 10:
                    samples.append((r, g, b))
    if not samples:
        return (0, 0, 0)
    avg_r = sum(color[0] for color in samples) // len(samples)
    avg_g = sum(color[1] for color in samples) // len(samples)
    avg_b = sum(color[2] for color in samples) // len(samples)
    return (avg_r, avg_g, avg_b)


if __name__ == "__main__":
    # save_ingredient_icons()
    # save_effect_icons()
    save_salt_icons()
