#!/usr/bin/env python3
"""Construit la diapositive unique de synthèse COMEX à partir d'un JSON.

Usage :
    python build_slide.py contenu.json sortie.pptx [--png]

--png : rend aussi un aperçu PNG (via LibreOffice) à côté du .pptx, pour
        vérifier visuellement qu'aucun texte ne déborde.

Le format du JSON est décrit dans references/format_contenu.md.
Le script choisit lui-même la taille de police de chaque bloc pour que le
texte tienne ; s'il doit descendre sous la taille minimale lisible, il
l'écrit dans un AVERTISSEMENT : raccourcissez alors le texte concerné
plutôt que d'accepter un bloc illisible.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

FONT = "Calibri"
W, H = 13.333, 7.5
MARGIN = 0.5
WARNINGS = []


def rgb(hexstr):
    return RGBColor.from_string(hexstr.lstrip("#").upper()[:6])


def est_height(paragraphs, width_in, pt, bullet=True, spacing_pt=4):
    """Estimation prudente de la hauteur (en pouces) d'un bloc de texte."""
    usable = width_in - (0.25 if bullet else 0.0) - 0.1
    cpl = max(8, usable * 72 / (pt * 0.50))  # ~0.5 em par caractère en Calibri
    lines = sum(max(1, math.ceil(len(p) / cpl)) for p in paragraphs)
    return lines * pt * 1.2 / 72 + len(paragraphs) * spacing_pt / 72


def pick_size(paragraphs, width_in, height_in, sizes, label, bullet=True):
    for pt in sizes:
        if est_height(paragraphs, width_in, pt, bullet) <= height_in:
            return pt
    WARNINGS.append(
        f"AVERTISSEMENT : « {label} » est trop long pour sa zone même en {sizes[-1]} pt — raccourcissez-le."
    )
    return sizes[-1]


def add_box(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, name=None):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        shp.name = name
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def add_text(slide, x, y, w, h, runs_by_para, pt, color="222222", bold=False,
             anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, bullet=False, name=None,
             spacing_pt=4):
    """runs_by_para : liste de paragraphes ; chaque paragraphe = str ou liste de (texte, gras)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs_by_para):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing_pt)
        runs = [(para, bold)] if isinstance(para, str) else para
        if bullet:
            runs = [("▪  ", False)] + list(runs)
        for text, is_bold in runs:
            r = p.add_run()
            r.text = text
            r.font.name = FONT
            r.font.size = Pt(pt)
            r.font.bold = is_bold
            r.font.color.rgb = rgb(color)
    return tb


def section_header(slide, x, y, w, label, color):
    add_text(slide, x, y, w, 0.3, [label.upper()], 11, color=color, bold=True, name=f"Titre {label}")
    ln = slide.shapes.add_connector(1, Inches(x + 0.05), Inches(y + 0.31), Inches(x + w), Inches(y + 0.31))
    ln.line.color.rgb = rgb(color)
    ln.line.width = Pt(1)


def bullets_block(slide, x, y, w, h, items, label, color_head, sizes=(13, 12, 11, 10.5, 10)):
    section_header(slide, x, y, w, label, color_head)
    body_h = h - 0.38
    paras = [i if isinstance(i, str) else i["texte"] for i in items]
    pt = pick_size(paras, w, body_h, sizes, label)
    add_text(slide, x, y + 0.38, w, body_h, paras, pt, bullet=True, name=f"Corps {label}")


def options_block(slide, x, y, w, h, options, color_head, recommended_idx):
    section_header(slide, x, y, w, "Options étudiées", color_head)
    body_h = h - 0.38
    paras, flat = [], []
    for i, o in enumerate(options):
        nom = o["nom"] + ("  (recommandée)" if i == recommended_idx else "")
        detail = o.get("detail", "")
        paras.append([(nom + (" — " if detail else ""), True), (detail, False)])
        flat.append(nom + " — " + detail)
    pt = pick_size(flat, w, body_h, (13, 12, 11, 10.5, 10), "Options étudiées")
    add_text(slide, x, y + 0.38, w, body_h, paras, pt, bullet=True, name="Corps Options")


def kpi_tiles(slide, x, y, w, h, kpis, primary, accent):
    section_header(slide, x, y, w, "Chiffres clés", primary)
    kpis = kpis[:4]
    n = len(kpis)
    if n == 0:
        return
    cols = 2 if n >= 2 else 1
    rows = math.ceil(n / cols)
    gap = 0.15
    top = y + 0.45
    tw = (w - gap * (cols - 1)) / cols
    th = (h - 0.45 - gap * (rows - 1)) / rows
    arrows = {"hausse": "▲", "baisse": "▼", "neutre": "►"}
    for i, k in enumerate(kpis):
        r, c = divmod(i, cols)
        # une seule tuile sur la dernière ligne : elle prend toute la largeur
        this_w = w if (n % 2 == 1 and i == n - 1 and cols == 2) else tw
        tx = x + c * (tw + gap)
        ty = top + r * (th + gap)
        add_box(slide, tx, ty, this_w, th, fill="F2F4F8", name=f"Tuile KPI {i+1}")
        add_box(slide, tx, ty, 0.07, th, fill=primary, name=f"Liseré KPI {i+1}")
        val = k["valeur"]
        tend = k.get("tendance")
        val_pt = 26 if len(val) <= 7 else 22 if len(val) <= 10 else 18
        sign = arrows.get(tend, "")
        sign_color = {"hausse": "2E7D32", "baisse": "C62828"}.get(tend, "666666")
        if k.get("tendance_favorable") is False and tend in ("hausse", "baisse"):
            sign_color = "C62828"
        elif k.get("tendance_favorable") is True and tend in ("hausse", "baisse"):
            sign_color = "2E7D32"
        runs = [(val, True)]
        tb = add_text(slide, tx + 0.15, ty + 0.08, this_w - 0.2, th * 0.5, [runs], val_pt,
                      color=primary, anchor=MSO_ANCHOR.MIDDLE, name=f"Valeur KPI {i+1}")
        if sign:
            r2 = tb.text_frame.paragraphs[0].add_run()
            r2.text = "  " + sign
            r2.font.size = Pt(val_pt * 0.55)
            r2.font.name = FONT
            r2.font.color.rgb = rgb(sign_color)
        lib_h = th * 0.5 - 0.1
        lib_pt = pick_size([k["libelle"]], this_w - 0.2, lib_h, (11, 10, 9), f"libellé KPI {val}", bullet=False)
        add_text(slide, tx + 0.15, ty + th * 0.5, this_w - 0.2, lib_h, [k["libelle"]], lib_pt,
                 color="444444", name=f"Libellé KPI {i+1}")


def build(spec, out_path):
    theme = spec.get("theme", {})
    primary = theme.get("primaire", "1F3864")
    accent = theme.get("accent", "C55A11")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # vierge

    # Bandeau titre
    add_box(slide, 0, 0, W, 0.12, fill=primary, name="Bandeau")
    title = spec["titre"]
    tpt = pick_size([title], W - 2 * MARGIN, 0.95, (26, 24, 22, 20, 18), "titre", bullet=False)
    add_text(slide, MARGIN, 0.25, W - 2 * MARGIN, 0.95, [title], tpt, color=primary, bold=True,
             anchor=MSO_ANCHOR.MIDDLE, name="Titre (message clé)", spacing_pt=0)
    if spec.get("sous_titre"):
        add_text(slide, MARGIN, 1.18, W - 2 * MARGIN, 0.32, [spec["sous_titre"]], 12, color="666666",
                 name="Sous-titre")

    # Colonnes
    top = 1.62
    left_w = 7.75
    right_x = MARGIN + left_w + 0.35
    right_w = W - MARGIN - right_x
    decision_y = 5.72

    bullets_block(slide, MARGIN, top, left_w, 1.28, spec.get("contexte", []), "Contexte", primary)
    bullets_block(slide, MARGIN, top + 1.36, left_w, 1.42, spec.get("enjeux_risques", []), "Enjeux & risques", primary)
    options = spec.get("options", [])
    if options:
        options_block(slide, MARGIN, top + 2.86, left_w, decision_y - (top + 2.86) - 0.08, options, primary,
                      spec.get("option_recommandee"))
    kpi_tiles(slide, right_x, top, right_w, decision_y - top - 0.12, spec.get("chiffres_cles", []), primary, accent)

    # Bande décision
    bh = 1.2
    rec_w = left_w
    add_box(slide, MARGIN, decision_y, rec_w, bh, fill=primary, name="Fond recommandation")
    rec = spec["recommandation"]
    rpt = pick_size([rec], rec_w - 0.3, bh - 0.4, (14, 13, 12, 11), "recommandation", bullet=False)
    add_text(slide, MARGIN + 0.15, decision_y + 0.08, rec_w - 0.3, 0.3, ["RECOMMANDATION"], 11,
             color="FFFFFF", bold=True, name="Titre recommandation")
    add_text(slide, MARGIN + 0.15, decision_y + 0.36, rec_w - 0.3, bh - 0.42, [rec], rpt, color="FFFFFF",
             name="Corps recommandation")

    add_box(slide, right_x, decision_y, right_w, bh, fill=accent, name="Fond décision")
    dec = spec["decision_attendue"]
    dpt = pick_size([dec], right_w - 0.3, bh - 0.4, (14, 13, 12, 11), "décision attendue", bullet=False)
    add_text(slide, right_x + 0.15, decision_y + 0.08, right_w - 0.3, 0.3, ["DÉCISION ATTENDUE DU COMEX"], 11,
             color="FFFFFF", bold=True, name="Titre décision")
    add_text(slide, right_x + 0.15, decision_y + 0.36, right_w - 0.3, bh - 0.42, [dec], dpt, color="FFFFFF",
             bold=True, name="Corps décision")

    # Pied de page
    foot_y = H - 0.45
    add_text(slide, MARGIN, foot_y, 8.5, 0.3, [spec.get("source", "")], 9, color="888888", name="Source")
    add_text(slide, W - MARGIN - 4, foot_y, 4, 0.3, [spec.get("confidentialite", "Confidentiel — COMEX")], 9,
             color="888888", align=PP_ALIGN.RIGHT, name="Confidentialité")

    if spec.get("notes"):
        slide.notes_slide.notes_text_frame.text = spec["notes"]

    prs.core_properties.title = title[:250]
    prs.save(out_path)
    return out_path


def render_png(pptx_path):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("LibreOffice introuvable : pas d'aperçu PNG.")
        return None
    outdir = os.path.dirname(os.path.abspath(pptx_path))
    with tempfile.TemporaryDirectory() as prof:
        cmd = [soffice, f"-env:UserInstallation=file://{prof}", "--headless", "--convert-to", "png",
               "--outdir", outdir, pptx_path]
        try:
            subprocess.run(cmd, check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Rendu PNG impossible : {e}")
            return None
    png = os.path.splitext(os.path.abspath(pptx_path))[0] + ".png"
    return png if os.path.exists(png) else None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    with open(args[0], encoding="utf-8") as f:
        spec = json.load(f)
    for key in ("titre", "recommandation", "decision_attendue"):
        if not spec.get(key):
            sys.exit(f"Champ obligatoire manquant dans le JSON : {key}")
    build(spec, args[1])
    print(f"Diapositive écrite : {args[1]}")
    if "--png" in sys.argv:
        png = render_png(args[1])
        if png:
            print(f"Aperçu : {png}")
    for w in WARNINGS:
        print(w)


if __name__ == "__main__":
    main()
