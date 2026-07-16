"""
pdf_generator.py — Replica digitale del modulo cartaceo VERDEIMPIANTI S.R.L.
============================================================================
Genera con ReportLab un PDF A4 orizzontale identico alla scheda ore
aziendale: intestazione "ORE DAL ... AL ...", COGNOME, tabella
L→S con le 14 colonne del modulo e spazi firma in calce.

API:
    generate_week_pdf(year, week, employee, days)  -> bytes
    generate_admin_report(year, week, all_data)    -> bytes  (una pagina per dipendente)
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

import data_manager as dm

# Colori brand
BLU_TEKNO = colors.HexColor("#0b3c5d")
BLU_CHIARO = colors.HexColor("#328cc1")
GRIGIO_RIGA = colors.HexColor("#f2f6f9")

PAGE_W, PAGE_H = landscape(A4)  # 842 x 595 pt
MARGIN = 12 * mm

GIORNI_SIGLA = ["L", "M", "M", "G", "V", "S"]
GIORNI_NOME = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]

# (intestazione, larghezza relativa) — turno unico: una sola coppia di orari
COLONNE = [
    ("N.", 3.0),
    ("GG", 3.0),
    ("DALLE ORE", 8.5),
    ("ALLE ORE", 8.5),
    ("TOTALE\nORE", 6.0),
    ("ORE\nSTRA.", 5.5),
    ("ORE\nVIAGGIO", 6.5),
    ("MEZZO", 10.0),
    ("PRANZO\nSI/NO", 6.0),
    ("TRASF.\nSI/NO", 6.0),
    ("CLIENTE", 19.0),
    ("COLLEGA", 14.0),
]


def _col_x_positions(x0: float, total_w: float) -> list[float]:
    """Bordi X delle colonne (len = n. colonne + 1)."""
    rel_total = sum(w for _, w in COLONNE)
    xs = [x0]
    for _, w in COLONNE:
        xs.append(xs[-1] + total_w * (w / rel_total))
    return xs


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return ""
    return str(value)


def _fmt_num(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v == 0:
        return ""
    return f"{v:g}".replace(".", ",")


def _draw_header(c: rl_canvas.Canvas, year: int, week: int, employee: str) -> float:
    """Intestazione brand + campi del modulo. Ritorna la Y sotto l'header."""
    dal, al = dm.week_bounds_label(year, week)

    # Banda blu con il nome azienda
    band_h = 16 * mm
    c.setFillColor(BLU_TEKNO)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, PAGE_H - band_h + 5 * mm, "VERDEIMPIANTI S.R.L.")
    c.setFont("Helvetica", 8.5)
    c.drawRightString(
        PAGE_W - MARGIN,
        PAGE_H - band_h + 5.5 * mm,
        "IMPIANTI CIVILI ED INDUSTRIALI  •  QUADRI DI DISTRIBUZIONE E DI CONTROLLO  •  AUTOMAZIONE  —  TORINO (TO)",
    )

    y = PAGE_H - band_h - 10 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, y, "ORE DAL")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN + 20 * mm, y, dal)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN + 55 * mm, y, "AL")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN + 63 * mm, y, al)

    c.setFont("Helvetica", 10)
    c.drawRightString(PAGE_W - MARGIN - 60 * mm, y, "SETTIMANA N.")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(PAGE_W - MARGIN - 48 * mm, y, str(week))

    y -= 9 * mm
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, y, "COGNOME:")
    c.setFont("Helvetica-Bold", 12)
    name_x = MARGIN + 26 * mm
    c.drawString(name_x, y, employee.upper())
    w = c.stringWidth(employee.upper(), "Helvetica-Bold", 12)
    c.setLineWidth(0.8)
    c.line(name_x, y - 1.6 * mm, name_x + max(w, 35 * mm), y - 1.6 * mm)

    return y - 7 * mm


def _draw_table(
    c: rl_canvas.Canvas, top_y: float, year: int, week: int, days: Dict[str, Dict[str, Any]]
) -> float:
    """Disegna la tabella del modulo. Ritorna la Y sotto la tabella."""
    x0 = MARGIN
    table_w = PAGE_W - 2 * MARGIN
    xs = _col_x_positions(x0, table_w)

    header_h = 10 * mm
    row_h = 13 * mm
    dates = dm.week_days(year, week)
    n_rows = len(dates)
    table_h = header_h + n_rows * row_h
    bottom_y = top_y - table_h

    # --- Intestazione colonne ---
    c.setFillColor(BLU_TEKNO)
    c.rect(x0, top_y - header_h, table_w, header_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    for i, (title, _) in enumerate(COLONNE):
        cx = (xs[i] + xs[i + 1]) / 2
        lines = title.split("\n")
        size = 7.2
        c.setFont("Helvetica-Bold", size)
        if len(lines) == 1:
            c.drawCentredString(cx, top_y - header_h / 2 - size * 0.36, lines[0])
        else:
            c.drawCentredString(cx, top_y - header_h / 2 + 1.0 * mm, lines[0])
            c.drawCentredString(cx, top_y - header_h / 2 - 2.6 * mm, lines[1])

    # --- Righe giorni ---
    weekly_minutes = 0
    for r, d in enumerate(dates):
        ry_top = top_y - header_h - r * row_h
        ry_mid = ry_top - row_h / 2

        if r % 2 == 1:
            c.setFillColor(GRIGIO_RIGA)
            c.rect(x0, ry_top - row_h, table_w, row_h, stroke=0, fill=1)

        rec = days.get(d.isoformat(), dict(dm.EMPTY_DAY))
        tot_min = dm.day_total_minutes(rec)
        weekly_minutes += tot_min

        cells = [
            str(d.day),
            GIORNI_SIGLA[r],
            _fmt(rec.get("turno1_inizio")),
            _fmt(rec.get("turno1_fine")),
            dm.fmt_hhmm(tot_min) if tot_min else "",
            _fmt_num(rec.get("ore_stra")),
            _fmt_num(rec.get("ore_viaggio")),
            _fmt(rec.get("mezzo")),
            "SI" if rec.get("pranzo") else "NO",
            "SI" if rec.get("trasferta") else "NO",
            _fmt(rec.get("cliente")),
            _fmt(rec.get("collega")),
        ]

        c.setFillColor(colors.black)
        for i, text in enumerate(cells):
            bold = i in (0, 1, 4)
            font = "Helvetica-Bold" if bold else "Helvetica"
            size = 8.5
            # Riduci il font se il testo non entra nella cella
            max_w = (xs[i + 1] - xs[i]) - 2 * mm
            while size > 5.5 and c.stringWidth(text, font, size) > max_w:
                size -= 0.5
            if c.stringWidth(text, font, size) > max_w and len(text) > 3:
                while text and c.stringWidth(text + "…", font, size) > max_w:
                    text = text[:-1]
                text += "…"
            c.setFont(font, size)
            c.drawCentredString((xs[i] + xs[i + 1]) / 2, ry_mid - size * 0.36, text)

    # --- Griglia ---
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.9)
    c.rect(x0, bottom_y, table_w, table_h, stroke=1, fill=0)
    c.setLineWidth(0.5)
    for x in xs[1:-1]:
        c.line(x, bottom_y, x, top_y)
    for r in range(n_rows + 1):
        yy = top_y - header_h - r * row_h
        c.line(x0, yy, x0 + table_w, yy)

    # --- Totale settimana ---
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(BLU_TEKNO)
    stra_tot = sum(float(days[k].get("ore_stra") or 0) for k in days)
    viaggio_tot = sum(float(days[k].get("ore_viaggio") or 0) for k in days)
    c.drawString(
        x0,
        bottom_y - 7 * mm,
        f"TOTALE SETTIMANA: {dm.fmt_hhmm(weekly_minutes)}   •   "
        f"STRAORDINARI: {f'{stra_tot:g}'.replace('.', ',')} h   •   "
        f"VIAGGIO: {f'{viaggio_tot:g}'.replace('.', ',')} h",
    )

    return bottom_y - 12 * mm


def _draw_signatures(c: rl_canvas.Canvas, y: float) -> None:
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)

    sig_w = 70 * mm
    y_line = max(y - 10 * mm, 18 * mm)

    x1 = MARGIN + 10 * mm
    c.line(x1, y_line, x1 + sig_w, y_line)
    c.drawCentredString(x1 + sig_w / 2, y_line - 4.5 * mm, "Firma Dipendente")

    x2 = PAGE_W - MARGIN - 10 * mm - sig_w
    c.line(x2, y_line, x2 + sig_w, y_line)
    c.drawCentredString(x2 + sig_w / 2, y_line - 4.5 * mm, "Firma Responsabile")


def _draw_page(c: rl_canvas.Canvas, year: int, week: int, employee: str,
               days: Dict[str, Dict[str, Any]]) -> None:
    y = _draw_header(c, year, week, employee)
    y = _draw_table(c, y, year, week, days)
    _draw_signatures(c, y)
    # piè di pagina
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.grey)
    c.drawCentredString(
        PAGE_W / 2, 8 * mm,
        f"Foglio ore generato dall'app VERDEIMPIANTI S.R.L. — {date.today().strftime('%d/%m/%Y')}",
    )


def generate_week_pdf(year: int, week: int, employee: str,
                      days: Dict[str, Dict[str, Any]]) -> bytes:
    """PDF settimanale di un singolo dipendente (una pagina)."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(f"Foglio ore {employee} — settimana {week}/{year}")
    _draw_page(c, year, week, employee, days)
    c.showPage()
    c.save()
    return buf.getvalue()


def generate_admin_report(year: int, week: int,
                          all_data: Dict[str, Dict[str, Dict[str, Any]]]) -> bytes:
    """Report cumulativo: una pagina-modulo per ogni dipendente."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(f"Report fogli ore — settimana {week}/{year}")
    for employee, days in all_data.items():
        _draw_page(c, year, week, employee, days)
        c.showPage()
    c.save()
    return buf.getvalue()
