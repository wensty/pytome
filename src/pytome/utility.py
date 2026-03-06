import string
from io import BytesIO
from typing import Callable

from PIL import Image


def convert_to_column_letter(column_number: int) -> str:
    """
    Convert column number to column letter
    """
    assert column_number > 0
    result = ""
    while column_number > 0:
        column_number -= 1
        result = string.ascii_uppercase[column_number % 26] + result
        column_number = column_number // 26
    return result


def convert_to_column_number(column_letter: str) -> int:
    """
    Convert column letter to column number
    """
    result = 0
    for char in column_letter:
        assert "A" <= char <= "Z"
        result = result * 26 + (ord(char) - 64)
    return result


class SheetImageLoader:
    """
    Loads images from an openpyxl worksheet by cell address.
    """

    def __init__(self, sheet) -> None:
        self._images: dict[str, Callable[[], bytes]] = {}
        for image in sheet._images:
            row = image.anchor._from.row + 1
            col = convert_to_column_letter(image.anchor._from.col + 1)
            self._images[f"{col}{row}"] = image._data

    def image_in(self, cell: str) -> bool:
        return cell in self._images

    def get(self, cell: str) -> Image.Image:
        if cell not in self._images:
            raise ValueError(f"Cell {cell} doesn't contain an image")
        image_data = self._images[cell]
        image = BytesIO(image_data())
        return Image.open(image)


if __name__ == "__main__":
    print(convert_to_column_letter(1))
    print(convert_to_column_letter(26))
    print(convert_to_column_number("A"))
    print(convert_to_column_number("ZZ"))
