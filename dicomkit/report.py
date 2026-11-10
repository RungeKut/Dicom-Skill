"""PDF-отчёт (20-05): каркас ReportLab + финальная сборка с обложкой и вложениями.

Дисклеймер «предварительный автоматизированный разбор, НЕ является
врачебным заключением» обязателен в каждом отчёте. GIF-вложения и
метаданные — последним шагом через pypdf; повторное пересохранение чужими
утилитами вложения теряет (30-02).
"""
import hashlib
import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, HRFlowable, Image, KeepTogether,
                                PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

DISCLAIMER = ("предварительный автоматизированный разбор, НЕ является врачебным "
              "заключением")

PALETTE = dict(card="#efefed", stripe="#f5f4f2", header="#706645",
               border="#d0ccc0", text="#1d1d1a", muted="#807d76")


def _fonts():
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in ("times.ttf", "DejaVuSans.ttf"):
        path = os.path.join(win_fonts, name)
        if not os.path.exists(path):
            continue
        pdfmetrics.registerFont(TTFont("Body", path))
        for variant, suffix in (("timesbd.ttf", "-Bold"), ("DejaVuSans-Bold.ttf", "-Bold")):
            vpath = os.path.join(win_fonts, variant)
            if os.path.exists(vpath):
                pdfmetrics.registerFont(TTFont("Body" + suffix, vpath))
            else:
                pdfmetrics.registerFont(TTFont("Body" + suffix, path))
        italic = os.path.join(win_fonts, "timesi.ttf")
        pdfmetrics.registerFont(TTFont("Body-Italic",
                                       italic if os.path.exists(italic) else path))
        registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic")
        return "Body"
    return "Helvetica"


class Report:
    """Каркас отчёта: авто-оглавление, плейты, callout, таблицы, колонтитулы."""

    def __init__(self, out_path, title, subject="", margin=2.0 * cm, author="Z.ai"):
        font = _fonts()
        self.font = font
        self.S = {
            "body": ParagraphStyle("body", fontName=font, fontSize=10.5, leading=15.5,
                                   alignment=TA_JUSTIFY, spaceAfter=8,
                                   textColor=colors.HexColor(PALETTE["text"])),
            "bullet": ParagraphStyle("bullet", parent=self.S_body(), leftIndent=16,
                                     spaceAfter=4, alignment=TA_LEFT),
            "h1": ParagraphStyle("h1", fontName=font + "-Bold", fontSize=17, leading=21,
                                 spaceBefore=16, spaceAfter=8,
                                 textColor=colors.HexColor(PALETTE["text"])),
            "h2": ParagraphStyle("h2", fontName=font + "-Bold", fontSize=13, leading=17,
                                 spaceBefore=12, spaceAfter=6,
                                 textColor=colors.HexColor(PALETTE["header"])),
            "caption": ParagraphStyle("caption", fontName=font + "-Italic", fontSize=9,
                                      leading=12, alignment=TA_CENTER,
                                      textColor=colors.HexColor(PALETTE["muted"]),
                                      spaceBefore=4, spaceAfter=10),
            "th": ParagraphStyle("th", fontName=font + "-Bold", fontSize=9.5, leading=12.5,
                                 textColor=colors.white, alignment=TA_CENTER),
            "td": ParagraphStyle("td", fontName=font, fontSize=9.5, leading=12.5,
                                 textColor=colors.HexColor(PALETTE["text"]), alignment=TA_LEFT),
            "quote": ParagraphStyle("quote", fontName=font, fontSize=10, leading=15,
                                    leftIndent=20),
            "big": ParagraphStyle("big", fontName=font + "-Bold", fontSize=12, leading=16,
                                  textColor=colors.HexColor(PALETTE["header"])),
            "small": ParagraphStyle("small", fontName=font, fontSize=9.5, leading=13,
                                    textColor=colors.HexColor(PALETTE["muted"])),
        }
        self.out = out_path
        self.doc = _TocDoc(out_path, title=title, subject=subject, margin=margin, author=author)
        self.story = []

    def S_body(self):
        return ParagraphStyle("body0", fontName=self.font, fontSize=10.5, leading=15.5,
                              alignment=TA_JUSTIFY, spaceAfter=8,
                              textColor=colors.HexColor(PALETTE["text"]))

    def toc(self):
        self.story.append(Paragraph("<b>Содержание</b>", ParagraphStyle(
            "toc_title", fontName=self.font + "-Bold", fontSize=16, leading=20,
            spaceAfter=10)))
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle("TOC1", fontName=self.font + "-Bold", fontSize=11.5, leading=16,
                           leftIndent=6),
            ParagraphStyle("TOC2", fontName=self.font, fontSize=10.5, leading=14, leftIndent=22),
        ]
        self.story.append(toc)
        self.story.append(PageBreak())

    def h1(self, text):
        self.story.append(CondPageBreak(self._avail_h() * 0.15))
        self._heading(text, self.S["h1"], 0)
        self.story.append(HRFlowable(width="100%", thickness=1.1,
                                     color=colors.HexColor(PALETTE["header"]),
                                     spaceBefore=0, spaceAfter=8))

    def h2(self, text):
        self.story.append(CondPageBreak(self._avail_h() * 0.1))
        self._heading(text, self.S["h2"], 1)

    def _heading(self, text, style, level):
        key = "h_%s" % hashlib.md5(text.encode()).hexdigest()[:8]
        p = Paragraph('<a name="%s"/><b>%s</b>' % (key, text), style)
        p.bookmark_name, p.bookmark_level, p.bookmark_text, p.bookmark_key = text, level, text, key
        self.story.append(p)

    def body(self, text):
        self.story.append(Paragraph(text, self.S["body"]))

    def bullets(self, items):
        for b in items:
            self.story.append(Paragraph("• " + b, self.S["bullet"]))

    def plate(self, path, caption, max_height=None):
        max_height = max_height or PAGE_H() * 0.35
        pil = PILImage.open(path)
        w, h = pil.size
        ratio = min((PAGE_W() - 2 * self.doc.leftMargin) / w, max_height / h, 1.0)
        img = Image(path, width=w * ratio, height=h * ratio)
        cap = Paragraph(caption, self.S["caption"])
        if img.wrap(PAGE_W() - 2 * self.doc.leftMargin, PAGE_H())[1] + 30 <= PAGE_H() * 0.4:
            self.story.append(KeepTogether([img, cap]))
        else:
            self.story.extend([img, cap])

    def callout(self, big, small):
        t = Table([[Paragraph(big, self.S["big"])], [Paragraph(small, self.S["small"])]],
                  colWidths=[(PAGE_W() - 2 * self.doc.leftMargin) * 0.96])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["card"])),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(PALETTE["header"])),
            ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        self.story.append(KeepTogether(t))
        self.story.append(Spacer(1, 10))

    def table(self, rows, header, ratios, center_cols=()):
        widths = [r * (PAGE_W() - 2 * self.doc.leftMargin) for r in ratios]
        data = [[Paragraph("<b>%s</b>" % h, self.S["th"]) for h in header]]
        for r in rows:
            data.append([Paragraph(str(v), self.S["tdc" if ci in center_cols else "td"])
                         for ci, v in enumerate(r)])
        t = Table(data, colWidths=widths, hAlign="CENTER", repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PALETTE["header"])),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(PALETTE["border"])),
                 ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                 ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i),
                              colors.HexColor(PALETTE["stripe"])))
        t.setStyle(TableStyle(style))
        self.story.append(t)
        self.story.append(Spacer(1, 8))

    def _avail_h(self):
        return PAGE_H() - self.doc.topMargin - self.doc.bottomMargin

    def build(self, header_text=""):
        doc = self.doc
        text = header_text or doc.title
        doc.multiBuild(self.story, onFirstPage=_page_frame(text, self.font),
                       onLaterPages=_page_frame(text, self.font))
        return self.out


def _page_frame(text, font):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor(PALETTE["muted"]))
        canvas.drawString(doc.leftMargin, A4[1] - 1.15 * cm, text)
        canvas.drawRightString(A4[0] - doc.leftMargin, A4[1] - 1.15 * cm,
                               "стр. %d" % doc.page)
        canvas.restoreState()
    return draw


class _TocDoc(SimpleDocTemplate):
    def __init__(self, *a, **kw):
        self._title = kw.pop("title", "")
        self._subject = kw.pop("subject", "")
        self._author = kw.pop("author", "Z.ai")
        kw.setdefault("pagesize", A4)
        SimpleDocTemplate.__init__(self, *a, **kw)

    def afterFlowable(self, flowable):
        if hasattr(flowable, "bookmark_name"):
            self.notify("TOCEntry", (getattr(flowable, "bookmark_level", 0),
                                     getattr(flowable, "bookmark_text", ""),
                                     self.page, getattr(flowable, "bookmark_key", "")))


def PAGE_W():
    return A4[0]


def PAGE_H():
    return A4[1]


def finalize(body_pdf, out_pdf, cover_pdf=None, attachments=None, title="", subject=""):
    """Обложка страницей 1, нормализация к A4, метаданные и GIF-вложения (30-02).

    attachments — {имя: путь}; вызывать последним шагом и файл далее не
    пересохранять — вложения теряются при любом пересохранении.
    """
    from pypdf import PdfReader, PdfWriter, Transformation
    a4 = (595.28, 841.89)

    def norm(page):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        if abs(w - a4[0]) > 2 or abs(h - a4[1]) > 2:
            page.add_transformation(Transformation().scale(sx=a4[0] / w, sy=a4[1] / h))
            page.mediabox.lower_left = (0, 0)
            page.mediabox.upper_right = (a4[0], a4[1])
        return page

    writer = PdfWriter()
    if cover_pdf:
        writer.add_page(norm(PdfReader(cover_pdf).pages[0]))
    for page in PdfReader(body_pdf).pages:
        writer.add_page(norm(page))
    writer.add_metadata({"/Title": title, "/Author": "Z.ai", "/Creator": "Z.ai",
                         "/Producer": "http://z.ai", "/Subject": subject})
    for name, path in (attachments or {}).items():
        with open(path, "rb") as fh:
            writer.add_attachment(name, fh.read())
    with open(out_pdf, "wb") as fh:
        writer.write(fh)
    return out_pdf
