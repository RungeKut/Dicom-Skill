"""Чтение DICOM: серии, ориентация, сортировка, «битые» диски.

Сортировка — только по проекции IPP на нормаль среза (30-01); порядок
каталога и InstanceNumber не совпадают с анатомическим. «Битые» диски
Siemens с JPEG-Lossless без терминатора (FFFE,E0DD) pydicom читает только
по метаданным (30-03), пиксели извлекаются вручную и декодируются
pylibjpeg (10-01). Ориентация — флип по доминантной оси столбцового
вектора (10-03, 30-04); итог проверять глазами.
"""
import os
import struct
from dataclasses import dataclass, field

import numpy as np
import pydicom

_MANUAL_DECODER = None


def _manual_decoder():
    global _MANUAL_DECODER
    if _MANUAL_DECODER is None:
        from pylibjpeg import decode as jdec
        _MANUAL_DECODER = jdec
    return _MANUAL_DECODER


def _manual_jpeg(raw):
    """Извлекает encapsulated JPEG из 7FE0,0010 без терминатора (30-03)."""
    idx = raw.find(b"\xe0\x7f\x10\x00")
    if idx < 0:
        return None
    p = idx + 12
    frags, first = [], True
    while p + 8 <= len(raw):
        group, elem, ilen = struct.unpack("<HHI", raw[p:p + 8])
        if group != 0xFFFE or elem != 0xE000:
            break
        if not (first and ilen == 0):
            frags.append(raw[p + 8:p + 8 + ilen])
        first = False
        p += 8 + ilen
    return b"".join(frags) or None


def _read_pixels(path, ds):
    try:
        full = pydicom.dcmread(path, force=True)
        if "PixelData" in full and getattr(full, "Rows", 0):
            arr = full.pixel_array.astype(np.float32)
            return arr * float(getattr(full, "RescaleSlope", 1)) + float(getattr(full, "RescaleIntercept", 0))
    except Exception:
        pass
    jpeg = _manual_jpeg(open(path, "rb").read())
    if not jpeg:
        return None
    arr = np.asarray(_manual_decoder()(jpeg), dtype=np.float32)
    return arr * float(getattr(ds, "RescaleSlope", 1)) + float(getattr(ds, "RescaleIntercept", 0))


def apply_orientation(arr, col):
    """Флип по вертикали по доминантной оси столбцового вектора (10-03, 30-04).

    Горизонталь (право/лево на экране) не трогается: после загрузки сверять
    анатомию глазами — глазницы/лоб сверху на аксиальных.
    """
    axis = int(np.argmax(np.abs(col)))
    sign = col[axis]
    if (axis == 2 and sign > 0) or (axis == 1 and sign < 0) or (axis == 0 and sign > 0):
        return arr[::-1, :].copy()
    return arr


@dataclass
class Slice:
    path: str
    series: int
    index: int
    pixel: np.ndarray
    spacing: float
    ipp: np.ndarray
    row_vec: np.ndarray
    col_vec: np.ndarray
    pos: float
    center: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.pixel.shape

    def to_patient(self, u_mm, v_mm):
        """Экранные координаты (мм от верхнего левого угла) → координаты пациента."""
        ci = u_mm / self.spacing
        ri = v_mm / self.spacing
        return self.ipp + ci * self.spacing * self.row_vec + ri * self.spacing * self.col_vec


def _meta(ds):
    out = {}
    for tag in ("PatientName", "PatientBirthDate", "PatientSex", "PatientAge", "PatientID",
                "StudyDate", "StudyTime", "StudyDescription", "Manufacturer",
                "ManufacturerModelName", "InstitutionName", "MagneticFieldStrength",
                "BodyPartExamined", "SeriesDescription", "ProtocolName"):
        val = getattr(ds, tag, None)
        if val not in (None, ""):
            out[tag] = str(val)
    return out


def load_series(folder, side_axis=0):
    """Читает серию из папки: срезы отсортированы по проекции IPP на нормаль (30-01).

    side_axis — ось координат для метки стороны (0 при HFS: x>0 — левая сторона).
    Горизонтальную ориентацию экрана после загрузки сверять глазами (10-03).
    """
    slices = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        if getattr(ds, "ImageOrientationPatient", None) is None:
            continue
        pixel = _read_pixels(path, ds)
        if pixel is None:
            continue
        row = np.array(ds.ImageOrientationPatient[:3], float)
        col = np.array(ds.ImageOrientationPatient[3:], float)
        ps = float(ds.PixelSpacing[0])
        ipp = np.array([float(v) for v in ds.ImagePositionPatient])
        normal = np.cross(row, col)
        pixel = apply_orientation(pixel, col)
        slices.append(Slice(
            path=path, series=int(str(getattr(ds, "SeriesNumber", 0))), index=0,
            pixel=pixel, spacing=ps, ipp=ipp, row_vec=row, col_vec=col,
            pos=float(np.dot(ipp, normal)), center=np.zeros(3), meta=_meta(ds),
        ))
    slices.sort(key=lambda s: s.pos)
    for i, sl in enumerate(slices):
        sl.index = i + 1
        sl.center = sl.ipp + sl.row_vec * (sl.pixel.shape[1] * sl.spacing / 2) \
            + sl.col_vec * (sl.pixel.shape[0] * sl.spacing / 2)
    return slices


def load_study(root):
    """Обходит дерево DICOM; папка с изображениями = серия. {номер серии: [Slice, ...]}.

    Фазовые повторы в одной папке имеют общий SeriesNumber — внутри серии
    их различают по AcquisitionNumber (см. gifstack.phase_slices).
    """
    study = {}
    for dp, _dn, fn in os.walk(root):
        if not fn:
            continue
        got = load_series(dp)
        if got:
            study[str(got[0].series)] = got
    return study


def inventory(root):
    """Таблица серий исследования + bounding box центров (10-02). Возвращает строки таблицы."""
    study = load_study(root)
    lines = ["#  серия  описание                          срезы  матрица    толщ  TR/TE         покрытие x/y/z, мм"]
    for key, slices in sorted(study.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        sl0 = slices[0]
        ds0 = pydicom.dcmread(sl0.path, stop_before_pixels=True, force=True)
        centers = np.array([sl.center for sl in slices])
        bbox = " ".join("[%+.0f;%+.0f]" % (centers[:, i].min(), centers[:, i].max())
                        for i in range(3))
        desc = str(getattr(ds0, "SeriesDescription", "?"))[:32]
        lines.append("%-3s %-6s %-32s %-6d %dx%d      %-5s %s/%s  %s" % (
            key, key, desc, len(slices), sl0.pixel.shape[1], sl0.pixel.shape[0],
            getattr(ds0, "SliceThickness", "?"), getattr(ds0, "RepetitionTime", "?"),
            getattr(ds0, "EchoTime", "?"), bbox))
    return "\n".join(lines)


def patient_meta(root_or_folder):
    """Шапка пациента/исследования из первого файла (для паспорта отчёта)."""
    for dp, _dn, fn in os.walk(root_or_folder):
        for name in sorted(fn):
            try:
                ds = pydicom.dcmread(os.path.join(dp, name), stop_before_pixels=True, force=True)
            except Exception:
                continue
            meta = _meta(ds)
            if meta:
                return meta
    return {}
