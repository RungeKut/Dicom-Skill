"""GIF-динамика из фазовых серий (20-04).

Ключ группировки — (описание серии, AcquisitionNumber, сторона): фазовые
повторы с пустым описанием (позиции открывания) собираются в одну семью,
cine-серии с собственным описанием остаются отдельными. Пошаговые позиции
имеют совпадающие центры срезов — сравнение в одной плоскости корректно.
Кадры только реальные, без интерполяции; в отчёте указывать дискретность
шагов.
"""
from collections import defaultdict

import pydicom
from PIL import Image, ImageDraw

from .montage import to_rgb, _font


def _side(center_x):
    return "L" if center_x > 0 else "R"


def _meta_of(slice_obj):
    return pydicom.dcmread(slice_obj.path, stop_before_pixels=True, force=True)


def _as_slices(src):
    """Строка-путь к папке → load_series; список Slice → как есть."""
    if isinstance(src, str):
        from .io import load_series
        return load_series(src)
    return list(src)


def phase_slices(src):
    """→ {(описание, фаза, сторона): центральный Slice}.

    Фаза = AcquisitionNumber. Внутри (описание, фаза, сторона) берётся
    средний срез по проекции IPP. Позиции одного шаблона с пустым
    описанием объединяются автоматически; cine-серии с собственным
    описанием образуют отдельные ключи.
    """
    by = defaultdict(list)
    for sl in _as_slices(src):
        ds = _meta_of(sl)
        desc = str(getattr(ds, "SeriesDescription", "")).strip()
        acq = int(str(getattr(ds, "AcquisitionNumber", 0) or 0))
        by[(desc, acq, _side(sl.center[0]))].append(sl)
    picked = {}
    for key, group in by.items():
        group.sort(key=lambda s: abs(s.pos))
        picked[key] = group[len(group) // 2]
    return dict(sorted(picked.items()))


def cine_slices(src, min_frames=2):
    """→ {(описание, сторона, позиция): [Slice, ...] в порядке AcquisitionTime}.

    cine = несколько кадров на одном и том же срезе (совпадающая проекция
    IPP с точностью 0,5 мм). Обычные многосрезовые серии (у каждого среза
    своя позиция и своё время) в результат не попадают.
    """
    groups = defaultdict(list)
    for sl in _as_slices(src):
        ds = _meta_of(sl)
        desc = str(getattr(ds, "SeriesDescription", "")).strip()
        if not desc:
            continue
        key = (desc, _side(sl.center[0]), round(sl.pos * 2) / 2)
        groups[key].append((str(getattr(ds, "AcquisitionTime", "")), sl))
    out = {}
    for key, timed in groups.items():
        if len(timed) < min_frames:
            continue
        timed.sort(key=lambda t: t[0])
        out[key] = [sl for _t, sl in timed]
    return dict(sorted(out.items()))


def build_gif(slices, out, pingpong=True, tail_ms=900, frame_ms=300,
              crop=None, zoom=1, title=""):
    """Собирает GIF из списка Slice; pingpong проигрывает назад до нуля,
    концевые кадры держатся дольше (tail_ms)."""
    frames = []
    for sl in slices:
        im = to_rgb(sl.pixel)
        if crop:
            im = im.crop(crop)
        if zoom != 1:
            im = im.resize((im.width * zoom, im.height * zoom), Image.LANCZOS)
        if title:
            _label(im, title)
        frames.append(im)
    order = list(range(len(frames)))
    if pingpong:
        order += list(range(len(frames) - 2, 0, -1))
    seq = [frames[i] for i in order]
    durations = [tail_ms if i in (0, order[-1]) else frame_ms for i in order]
    seq[0].save(out, save_all=True, append_images=seq[1:], duration=durations, loop=0)
    return out, order


def _label(im, text):
    dr = ImageDraw.Draw(im)
    f = _font()
    box = dr.textbbox((0, 0), text, font=f)
    dr.rectangle([2, 2, box[2] + 12, box[3] + 8], fill=(0, 0, 0))
    dr.text((6, 4), text, fill=(255, 255, 0), font=f)
