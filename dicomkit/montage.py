"""Обзорные листы серий и поштучные кадры.

Окно контраста — перцентили [1; 99.5] по серии (10-01); подпись кадра
обязательна: серия, срез, сторона.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT = None


def _font(size=15):
    global _FONT
    if _FONT is None:
        for name in ("arialbd.ttf", "arial.ttf"):
            path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
            if os.path.exists(path):
                _FONT = ImageFont.truetype(path, size)
                break
        else:
            _FONT = ImageFont.load_default()
    return _FONT


def to_rgb(pixel, window=None):
    """Пиксели → RGB-кадр; окно — пара перцентилей, по умолчанию [1; 99.5]."""
    if window is None:
        window = (1.0, 99.5)
    lo, hi = np.percentile(pixel, window)
    g = np.clip((pixel - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(g).convert("RGB")


def _label(im, text, color=(255, 255, 0)):
    dr = ImageDraw.Draw(im)
    f = _font()
    box = dr.textbbox((0, 0), text, font=f)
    dr.rectangle([2, 2, box[2] + 12, box[3] + 8], fill=(0, 0, 0))
    dr.text((6, 4), text, fill=color, font=f)


def montage(slices, out, cols=6, tile=300, prefix=""):
    """Обзорный лист серии; slices — список dicomkit.io.Slice или массивов."""
    frames = []
    for i, sl in enumerate(slices):
        pixel = getattr(sl, "pixel", sl)
        im = to_rgb(pixel)
        im.thumbnail((tile, tile))
        label = "%s%s sl%s" % (prefix, getattr(sl, "series", ""), getattr(sl, "index", i + 1))
        _label(im, label)
        frames.append(im)
    w = max(im.width for im in frames)
    h = max(im.height for im in frames)
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * 4, rows * h + (rows + 1) * 4), (25, 25, 25))
    for i, im in enumerate(frames):
        r, c = divmod(i, cols)
        sheet.paste(im, (4 + c * (w + 4), 4 + r * (h + 4)))
    sheet.save(out)
    return out


def save_slices(slices, out_dir, prefix="sl"):
    """Поштучные PNG серии для прицельной работы; имена <prefix>_<номер>.png."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for sl in slices:
        pixel = getattr(sl, "pixel", sl)
        idx = getattr(sl, "index", None)
        name = "%s_%s.png" % (prefix, "%02d" % idx if idx else "%02d" % (len(paths) + 1))
        path = os.path.join(out_dir, name)
        to_rgb(pixel).save(path)
        paths.append(path)
    return paths
