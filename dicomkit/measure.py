"""Панели с мм-сетками для измерений (20-03) и компоновка панелей.

Координаты снимаются глазами по сетке; точность ±1–2 мм. Масштаб всегда
сверять с матрицей DICOM (30-05): сохранённые PNG бывают уменьшены.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .montage import to_rgb, _font


def grid_panel(pixel, crop, spacing, zoom=4, title="", grid_mm=2, window=(1, 99.5)):
    """Кадр crop=(x0,y0,x1,y1) в пикселях с сеткой grid_mm; координаты сетки — мм от угла."""
    x0, y0, x1, y1 = crop
    c = np.asarray(pixel[y0:y1, x0:x1], float)
    lo, hi = np.percentile(c, window)
    g = np.clip((c - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
    im = Image.fromarray(g).convert("RGB")
    im = im.resize((im.width * zoom, im.height * zoom), Image.LANCZOS)
    dr = ImageDraw.Draw(im)
    f = _font()
    step = grid_mm / spacing * zoom
    k = 0
    xx = 0.0
    while xx < im.width:
        major = k % 5 == 0
        dr.line([(xx, 0), (xx, im.height)], fill=(255, 70, 70) if major else (255, 150, 150),
                width=2 if major else 1)
        if major:
            dr.text((xx + 2, 2), str(k * grid_mm), fill=(255, 150, 150), font=f)
        xx += step
        k += 1
    k = 0
    yy = 0.0
    while yy < im.height:
        major = k % 5 == 0
        dr.line([(0, yy), (im.width, yy)], fill=(255, 70, 70) if major else (255, 150, 150),
                width=2 if major else 1)
        if major:
            dr.text((2, yy + 2), str(k * grid_mm), fill=(255, 150, 150), font=f)
        yy += step
        k += 1
    if title:
        box = dr.textbbox((6, im.height - 22), title, font=f)
        dr.rectangle([box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3], fill=(0, 0, 0))
        dr.text((6, im.height - 22), title, fill=(255, 255, 0), font=f)
    return im


def hstack(images, pad=6, bg=(25, 25, 25)):
    w = sum(im.width for im in images) + pad * (len(images) + 1)
    h = max(im.height for im in images) + 2 * pad
    out = Image.new("RGB", (w, h), bg)
    x = pad
    for im in images:
        out.paste(im, (x, pad))
        x += im.width + pad
    return out


def vstack(images, pad=6, bg=(25, 25, 25)):
    w = max(im.width for im in images) + 2 * pad
    h = sum(im.height for im in images) + pad * (len(images) + 1)
    out = Image.new("RGB", (w, h), bg)
    y = pad
    for im in images:
        out.paste(im, (pad, y))
        y += im.height + pad
    return out
