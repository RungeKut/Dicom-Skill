"""Панорамная реконструкция по кривой дуги (КЛКТ) — приём 20-06.

Дуга задана контрольными точками в мм пациента (по окклюзионному срезу),
Catmull-Rom, вдоль дуги — вертикальные плоскости, тонкая пластина ±slab мм
(СРЕДНЕЕ, не MIP — MIP по широкой полосе пересвечивается). Первая точка
дуги = правый конец пациента, остаётся слева на панораме. Верх = больший z.
"""
import numpy as np
from scipy.ndimage import map_coordinates


def catmull(points, step_mm=0.8):
    """Сглаженная дуга по контрольным точкам [[x,y], ...], шаг ~step_mm."""
    pts = np.asarray(points, float)
    P = np.vstack([pts[0], pts, pts[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int(np.hypot(*(p2 - p1)) / step_mm))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t
                              + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return np.array(out)


def panorama(vol, points, z0, z1, sp_xy, sp_z, slab=2.0, half=30.0, step_mm=0.8):
    """Панорама из объёма vol[z, y, x].

    points — мм пациента по дуге; z0..z1 — вертикальный диапазон, мм;
    sp_xy/sp_z — шаги по осям (30-06: раздельно); slab — толщина пластины,
    мм; half — полуширина сэмплирования по нормали, мм.
    Возвращает массив (z, вдоль дуги) — верх = больший z, левый край =
    первая точка дуги; значения HU (float32).
    """
    curve = catmull(points, step_mm)
    zs = np.arange(z0, z1, sp_z)
    offs = np.arange(-half, half, sp_xy)
    lo_i, hi_i = int(len(offs) / 2 - slab / sp_xy / 2), int(len(offs) / 2 + slab / sp_xy / 2)
    Zg = np.broadcast_to(zs[:, None] / sp_z, (len(zs), len(offs)))
    Sg = np.broadcast_to(offs[None, :] / sp_xy, (len(zs), len(offs)))
    cols = []
    for i in range(len(curve)):
        T = curve[min(i + 1, len(curve) - 1)] - curve[max(i - 1, 0)]
        N = np.array([-T[1], T[0]], float)
        if N[1] > 0:  # нормаль к центру дуги
            N = -N
        X = (curve[i][0] + Sg * N[0]) / sp_xy
        Y = (curve[i][1] + Sg * N[1]) / sp_xy
        coords = np.stack([Zg.ravel(), Y.ravel(), X.ravel()])
        vals = map_coordinates(vol, coords, order=1, mode="constant", cval=-1000)
        cols.append(vals.reshape(len(zs), len(offs)))   # (z, поперёк)
    img = np.stack(cols, axis=1)                        # (z, вдоль дуги, поперёк)
    slab_img = img[:, :, lo_i:hi_i + 1].mean(axis=2)    # тонкая пластина: среднее
    return slab_img[::-1].astype(np.float32)            # верх = больший z
