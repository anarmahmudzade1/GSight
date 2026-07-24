"""Generates the GSight logo (assets/icon.png, assets/icon.ico).

Two 'G' glyphs facing each other — the right one vertically reflected —
joined by a horizontal bar across their midsection. Gemini Electric Blue
palette (#1A73E8 / #4285F4).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ASSETS_DIR = Path(__file__).resolve().parent
CANVAS_SIZE = 512
BLUE_DARK = (26, 115, 232, 255)   # #1A73E8
BLUE_LIGHT = (66, 133, 244, 255)  # #4285F4


def _draw_g(size: int, stroke: int, color: tuple) -> Image.Image:
    """Draw a single simplified 'G' glyph (ring with an inward flag) on a transparent tile."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = stroke // 2 + 4
    bbox = (margin, margin, size - margin, size - margin)

    # Ring with a gap facing right (0 degrees = 3 o'clock), like a 'C'.
    draw.arc(bbox, start=20, end=340, fill=color, width=stroke)

    # Short inward flag stopping well short of the ring, so the gap stays visible.
    cx, cy = size // 2, size // 2
    radius = size // 2 - margin
    flag_end = cx + int(radius * 0.55)
    draw.rectangle((cx, cy - stroke // 2, flag_end, cy + stroke // 2), fill=color)

    return img


def generate_icon() -> Path:
    stroke = CANVAS_SIZE // 9
    glyph_size = int(CANVAS_SIZE * 0.42)

    left_g = _draw_g(glyph_size, stroke, BLUE_DARK)
    right_g = ImageOps.flip(_draw_g(glyph_size, stroke, BLUE_LIGHT))  # vertical reflection

    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    gap = int(CANVAS_SIZE * 0.06)
    total_width = glyph_size * 2 + gap
    start_x = (CANVAS_SIZE - total_width) // 2
    y = (CANVAS_SIZE - glyph_size) // 2

    canvas.alpha_composite(left_g, (start_x, y))
    canvas.alpha_composite(right_g, (start_x + glyph_size + gap, y))

    # Connecting bar across the midsection, linking both G's.
    draw = ImageDraw.Draw(canvas)
    mid_y = CANVAS_SIZE // 2
    bar_half_h = stroke // 4
    draw.rectangle(
        (
            start_x + glyph_size - stroke,
            mid_y - bar_half_h,
            start_x + glyph_size + gap + stroke,
            mid_y + bar_half_h,
        ),
        fill=BLUE_LIGHT,
    )

    png_path = ASSETS_DIR / "icon.png"
    canvas.save(png_path)

    ico_path = ASSETS_DIR / "icon.ico"
    canvas.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    return png_path


if __name__ == "__main__":
    path = generate_icon()
    print(f"Generated {path} and {path.with_suffix('.ico')}")
