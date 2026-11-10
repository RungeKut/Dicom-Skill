"""Зеркальные карты асимметрии право/лево (20-02).

Средняя линия ищется автоматически минимизацией расхождения с зеркалом;
блобы-зеркальные пары — симметрия (норма), односторонние — находка или
артефакт: каждый проверять на поштучных срезах. Карта скрининговая.
"""
import os

import numpy as np
from PIL import Image, ImageDraw

try:
    from scipy import ndimage as ndi
except ImportError:
    ndi = None


def _smooth(img, sigma=2):
    return ndi.gaussian_filter(img, sigma) if ndi is not None else img


def midline_col(img, search=60):
    """Колонка, минимизирующая расхождение с зеркалом (в пределах ±search)."""
    f = _smooth(img, 2)
    f = f / max(f.max(), 1e-6)
    tissue = f > 0.25
    c0 = int(np.argmax(np.convolve(tissue.sum(axis=0), np.ones(9) / 9, mode="same")))
    best, mid = None, c0
    for c in range(max(0, c0 - search), min(img.shape[1], c0 + search)):
        w = min(c, img.shape[1] - c)
        if w < 40:
            continue
        d = float(np.abs(f[:, c - w:c][:, ::-1] - f[:, c:c + w]).mean())
        if best is None or d < best:
            best, mid = d, c
    return mid


def diff_map(img, mid, sigma=2):
    """Карта |лево − право|, развёрнутая в обе стороны от средней линии."""
    f = _smooth(img, sigma)
    w = min(mid, img.shape[1] - mid)
    diff = np.abs(f[:, mid - w:mid][:, ::-1] - f[:, mid:mid + w])
    out = np.zeros_like(f)
    out[:, mid - w:mid] = diff[:, ::-1]
    out[:, mid:mid + w] = diff
    return out


def tissue_mask(img, pct=25):
    m = img > np.percentile(img, pct)
    if ndi is not None:
        m = ndi.binary_opening(m, iterations=2)
        m = ndi.binary_erosion(m, iterations=2)
    return m


def top_blobs(diff, mask, spacing, n=5, min_mm2=9.0, pct=99.0):
    """Топ-N блобов асимметрии: (площадь_пкс, cx, cy, mean, x0, x1, y0, y1)."""
    thr = max(np.percentile(diff[mask], pct), 12.0)
    cand = (diff > thr) & mask
    if ndi is None:
        return [], thr
    labels, count = ndi.label(cand)
    blobs = []
    for i in range(1, count + 1):
        ys, xs = np.where(labels == i)
        if len(xs) * spacing * spacing < min_mm2:
            continue
        blobs.append((len(xs), float(xs.mean()), float(ys.mean()),
                      float(diff[ys, xs].mean()),
                      int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))
    blobs.sort(reverse=True)
    return blobs[:n], thr


def overlay(pixel, mid, blobs, spacing, title="", out=None):
    """Срез с линией средней линии и рамками блобов."""
    lo, hi = np.percentile(pixel, [1, 99.5])
    g = np.clip((pixel - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
    rgb = np.stack([g] * 3, -1)
    im = Image.fromarray(rgb)
    dr = ImageDraw.Draw(im)
    dr.line([(mid, 0), (mid, pixel.shape[0])], fill=(80, 160, 255), width=1)
    for k, blob in enumerate(blobs):
        area, _cx, cy, _mean, x0, x1, y0, y1 = blob
        color = (255, 60, 60) if blob[1] < mid else (255, 160, 30)
        dr.rectangle([x0, y0, x1, y1], outline=color, width=2)
        dr.text((x0, max(0, y0 - 14)), "#%d %dmm2" % (k + 1, area * spacing * spacing),
                fill=color)
    if title:
        dr.text((6, 6), title, fill=(255, 255, 0))
    if out:
        im.save(out)
    return im


def asymmetry_report(slices, out_dir, first=None, last=None, step=1, n_blobs=4):
    """Карты асимметрии для диапазона срезов; возвращает список находок по срезам.

    slices — результат dk.load_series; находка = (срез, сторона, площадь_мм2, x, y).
    Каждый блоб из отчёта проверяется на поштучных срезах (20-02).
    """
    os.makedirs(out_dir, exist_ok=True)
    found = []
    first = 1 if first is None else first
    last = len(slices) if last is None else last
    for sl in slices[first - 1:last:step]:
        mid = midline_col(sl.pixel)
        mask = tissue_mask(sl.pixel)
        diff = diff_map(sl.pixel, mid)
        blobs, _thr = top_blobs(diff, mask, sl.spacing, n=n_blobs)
        if not blobs:
            continue
        name = "asym_%s%02d.png" % ("L" if sl.center[0] > 0 else "R", sl.index)
        overlay(sl.pixel, mid, blobs, sl.spacing,
                "sl%d/%d — карта асимметрии (синяя линия = средняя)" % (sl.index, len(slices)),
                os.path.join(out_dir, name))
        for blob in blobs:
            found.append({"slice": sl.index, "side": "R" if blob[1] < mid else "L",
                          "area_mm2": round(blob[0] * sl.spacing * sl.spacing),
                          "x": round(blob[1]), "y": round(blob[2]),
                          "image": name})
    return found
