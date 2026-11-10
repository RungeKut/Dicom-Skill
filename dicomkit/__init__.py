"""dicomkit — разбор медицинских снимков: МРТ/КТ DICOM и изображения УЗИ.

Модули: io (чтение и сортировка серий), montage (обзорные листы),
asymmetry (зеркальные карты право/лево), measure (мм-сетки),
gifstack (динамика из фазовых серий), pano (панорамы КЛКТ по дуге),
report (PDF-отчёт).
Закон базы — knowledge/00_ПРАВИЛА.md; грабли — 30_*.
"""
import os
import sys


def utf8_console():
    """Форсирует UTF-8 вывод на Windows-консоли; без него print с кириллицей падает."""
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


from .io import load_series, load_study, inventory, patient_meta
from .montage import montage, save_slices
from .asymmetry import midline_col, diff_map, top_blobs, asymmetry_report
from .measure import grid_panel, hstack, vstack
from .gifstack import phase_slices, cine_slices, build_gif
from .pano import panorama

__version__ = "0.2.0"
