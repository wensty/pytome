from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


@dataclass
class NormalizeConfig:
    canvas_size: int = 256
    # Target bounds for the non-transparent content inside the canvas.
    target_left: int = 20
    target_top: int = 20
    target_right: int = 236
    target_bottom: int = 236
    # Extra scale factor for Wine to match height.
    wine_scale: float = 1.0


def _content_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.split()[-1]
    bbox = alpha.getbbox()
    return bbox


def _normalize_icon(image: Image.Image, *, scale: float, cfg: NormalizeConfig) -> Image.Image:
    image = image.convert("RGBA")
    bbox = _content_bbox(image)
    if not bbox:
        return Image.new("RGBA", (cfg.canvas_size, cfg.canvas_size), (0, 0, 0, 0))

    cropped = image.crop(bbox)
    content_w = cropped.width
    content_h = cropped.height
    target_w = cfg.target_right - cfg.target_left
    target_h = cfg.target_bottom - cfg.target_top
    fit_scale_w = target_w / content_w
    fit_scale_h = scale * target_h / content_h
    # fit_scale = min(target_w / content_w, target_h / (content_h * scale))
    new_w = max(1, int(content_w * fit_scale_w))
    new_h = max(1, int(content_h * fit_scale_h))
    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (cfg.canvas_size, cfg.canvas_size), (0, 0, 0, 0))
    offset_x = cfg.target_left + (target_w - new_w) // 2
    offset_y = cfg.target_top + (target_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas


def _compose_unknown(
    water: Image.Image,
    oil: Image.Image,
    wine: Image.Image,
    *,
    cfg: NormalizeConfig,
) -> Image.Image:
    size = cfg.canvas_size
    unknown = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 3 equal sectors: start at -90 degrees (top).
    sectors = [
        (water, -90, 30),
        (oil, 30, 150),
        (wine, 150, 270),
    ]
    for icon, start, end in sectors:
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.pieslice((0, 0, size - 1, size - 1), start=start, end=end, fill=255)
        unknown = Image.composite(icon, unknown, mask)
    return unknown


def build_bases(
    base_dir: Path,
    *,
    cfg: NormalizeConfig | None = None,
    image_path_water: Path | None = None,
    image_path_oil: Path | None = None,
    image_path_wine: Path | None = None,
) -> None:
    cfg = cfg or NormalizeConfig()
    water = Image.open(image_path_water or base_dir / "Water.png")
    oil = Image.open(image_path_oil or base_dir / "Oil.png")
    wine = Image.open(image_path_wine or base_dir / "Wine.png")

    water_n = _normalize_icon(water, scale=1.0, cfg=cfg)
    oil_n = _normalize_icon(oil, scale=1.0, cfg=cfg)
    wine_n = _normalize_icon(wine, scale=cfg.wine_scale, cfg=cfg)

    water_n.save(base_dir / "Water_n.png")
    oil_n.save(base_dir / "Oil_n.png")
    wine_n.save(base_dir / "Wine_n.png")

    unknown = _compose_unknown(water_n, oil_n, wine_n, cfg=cfg)
    unknown.save(base_dir / "Unknown.png")


# from PIL import Image, ImageStat


def get_average_brightness(image_path):
    # Open the image
    im = Image.open(image_path)

    # Convert the image to grayscale (mode 'L' for luminance/brightness)
    # The library uses the ITU-R 601-2 luma transform for this conversion
    # which provides a good approximation of perceived brightness.
    gs_im = im.convert("L")

    # Get statistics for the grayscale image
    stat = ImageStat.Stat(gs_im)

    # The mean is an array, we need the first element for the single channel 'L' image
    average_brightness = stat.mean[0]

    return average_brightness


# Example usage:
# image_file = "your_image.jpg"  # Replace with your image path
# brightness_value = get_average_brightness(image_file)
# print(f"Average brightness: {brightness_value}")

if __name__ == "__main__":
    # Adjust NormalizeConfig values if you want to fine-tune alignment.
    # water_brightness = get_average_brightness(Path("data/icons/bases/Water.png"))
    # oil_brightness = get_average_brightness(Path("data/icons/bases/Oil.png"))
    # wine_brightness = get_average_brightness(Path("data/icons/bases/Wine.png"))

    # print(f"Water brightness: {water_brightness}")
    # print(f"Oil brightness: {oil_brightness}")
    # print(f"Wine brightness: {wine_brightness}")

    # oil = Image.open(Path("data/icons/bases/Oil.png"))
    # wine = Image.open(Path("data/icons/bases/Wine.png"))
    # enhancer_oil = ImageEnhance.Brightness(oil)
    # enhancer_wine = ImageEnhance.Brightness(wine)
    # wine = enhancer_wine.enhance(water_brightness / wine_brightness)
    # oil = enhancer_oil.enhance(water_brightness / oil_brightness)
    # wine.save(Path("data/icons/bases/Wine_normalized.png"))
    # oil.save(Path("data/icons/bases/Oil_normalized.png"))
    # wine.show()
    # oil.show()

    build_bases(
        Path("data/icons/bases"),
        # image_path_water=Path("data/icons/bases/Water_normalized.png"),
        # image_path_oil=Path("data/icons/bases/Oil_normalized.png"),
        # image_path_wine=Path("data/icons/bases/Wine_normalized.png"),
    )
    # _image = _normalize_icon(Image.open(Path("data/icons/bases/Wine.png")), scale=1.0, cfg=NormalizeConfig())
    # image.save(Path("data/icons/bases/Wine_normalized.png"))
