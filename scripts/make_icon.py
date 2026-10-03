from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


INSET = 40
RADIUS = 228


def _squircle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (INSET, INSET, size - INSET, size - INSET),
        radius=RADIUS,
        fill=255,
    )
    return mask


def _vertical_gradient(
    size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> Image.Image:
    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    for y in range(size):
        ratio = y / (size - 1)
        color = tuple(
            round(top[channel] + (bottom[channel] - top[channel]) * ratio)
            for channel in range(3)
        )
        draw.line((0, y, size, y), fill=(*color, 255))
    return gradient


def _rounded_background(size: int) -> Image.Image:
    mask = _squircle_mask(size)
    image = _vertical_gradient(size, (30, 176, 158), (11, 88, 84))
    image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-320, -380, 880, 540), fill=(160, 244, 228, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    glow.putalpha(ImageChops.multiply(glow.getchannel("A"), mask))
    image = Image.alpha_composite(image, glow)

    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        (INSET + 5, INSET + 5, size - INSET - 5, size - INSET - 5),
        radius=RADIUS - 5,
        outline=(180, 245, 232, 90),
        width=6,
    )
    return Image.alpha_composite(image, rim)


def _shadow(size: int, box: tuple[int, int, int, int], radius: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=(3, 42, 40, 120))
    return layer.filter(ImageFilter.GaussianBlur(34))


def _draw_mark(image: Image.Image) -> None:
    image.alpha_composite(_shadow(image.width, (262, 292, 762, 812), 96))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (246, 246, 778, 778),
        radius=96,
        fill=(248, 253, 252, 255),
    )
    draw.rounded_rectangle(
        (246, 246, 778, 778),
        radius=96,
        outline=(206, 236, 230, 255),
        width=5,
    )

    bars = (
        (340, 552, 420, 646, (20, 158, 143, 255)),
        (472, 470, 552, 646, (15, 118, 110, 255)),
        (604, 372, 684, 646, (245, 158, 11, 255)),
    )
    for left, top, right, bottom, color in bars:
        draw.rounded_rectangle((left, top, right, bottom), radius=22, fill=color)

    draw.rounded_rectangle(
        (322, 660, 702, 672),
        radius=6,
        fill=(214, 238, 233, 255),
    )

    draw.ellipse(
        (672, 672, 900, 900),
        fill=(255, 255, 255, 255),
        outline=(255, 255, 255, 255),
    )
    draw.ellipse(
        (690, 690, 882, 882),
        fill=(245, 158, 11, 255),
    )
    draw.ellipse(
        (759, 759, 813, 813),
        fill=(255, 255, 255, 255),
    )


def main() -> int:
    output = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "assets" / "AgentTokenLedger.ico"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    size = 1024
    image = _rounded_background(size)
    _draw_mark(image)
    image.putalpha(
        ImageChops.multiply(image.getchannel("A"), _squircle_mask(size))
    )

    image.save(
        output,
        format="ICO",
        sizes=[
            (16, 16),
            (20, 20),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
