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
    cpl = max(8, usable * 72 / (pt * 0.45))  # ~0.45 em par caractère en Calibri, avec marge
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


HEAD_H = 0.38      # hauteur d'un en-tête de section (libellé + filet)
BLOCK_GAP = 0.12   # espace minimal entre deux blocs de la colonne gauche
BODY_SIZES = (14, 13, 12, 11, 10.5, 10)
RECO_MARK = "★ recommandé"


def option_columns(options):
    """Colonnes chiffrées communes à toutes les options (champ `valeurs`), sinon None."""
    if len(options) < 2 or not all(isinstance(o.get("valeurs"), dict) and o["valeurs"] for o in options):
        return None
    keys = list(options[0]["valeurs"].keys())
    if any(list(o["valeurs"].keys()) != keys for o in options):
        WARNINGS.append("AVERTISSEMENT : les options n'ont pas toutes les mêmes clés dans `valeurs` — affichées en liste.")
        return None
    return keys


def option_paragraphs(options, rec):
    paras, flat = [], []
    for i, o in enumerate(options):
        nom = o["nom"]
        detail = o.get("detail", "")
        runs = [(nom, True)]
        if i == rec:
            runs.append(("  " + RECO_MARK, True))
        if detail:
            runs.append((" — " + detail, False))
        paras.append(runs)
        flat.append("".join(t for t, _ in runs))
    return paras, flat


def table_height(options, keys, w, pt):
    has_detail = any(o.get("detail") for o in options)
    name_w = w * (0.30 if has_detail else 0.40)
    detail_w = w * 0.34 if has_detail else 0
    line = pt * 1.2 / 72
    total = line + 0.08  # en-tête
    for o in options:
        n = max(est_height([o["nom"] + "  ★"], name_w, pt, bullet=False, spacing_pt=0),
                est_height([o.get("detail", "")], detail_w, pt, bullet=False, spacing_pt=0) if has_detail else 0)
        total += max(n, line) + 0.08
    return total


def options_table(slide, x, y, w, options, keys, rec, pt, primary, accent):
    has_detail = any(o.get("detail") for o in options)
    headers = ["Option"] + keys + (["Commentaire"] if has_detail else [])
    name_w = w * (0.30 if has_detail else 0.40)
    detail_w = w * 0.34 if has_detail else 0
    val_w = (w - name_w - detail_w) / len(keys)
    widths = [name_w] + [val_w] * len(keys) + ([detail_w] if has_detail else [])
    h = table_height(options, keys, w, pt)
    gf = slide.shapes.add_table(len(options) + 1, len(headers), Inches(x), Inches(y), Inches(w), Inches(h))
    gf.name = "Tableau options"
    tbl = gf.table
    tbl.first_row = True
    row_h = Inches(pt * 1.2 / 72 + 0.08)
    for r in tbl.rows:
        r.height = row_h
    for c, cw in enumerate(widths):
        tbl.columns[c].width = Inches(cw)

    def fill(cell, text, bold, color, bg, align=PP_ALIGN.LEFT):
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(bg)
        cell.margin_left = cell.margin_right = Inches(0.06)
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        runs = [(text, bold)] if isinstance(text, str) else text
        for t, b in runs:
            rr = p.add_run()
            rr.text = t
            rr.font.name = FONT
            rr.font.size = Pt(pt)
            rr.font.bold = b
            rr.font.color.rgb = rgb(color if not (len(runs) > 1 and t.strip().startswith("★")) else accent)

    for c, hd in enumerate(headers):
        fill(tbl.cell(0, c), hd, True, "FFFFFF", primary, PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
    for r, o in enumerate(options, 1):
        is_rec = (r - 1) == rec
        bg = "FCEBDD" if is_rec else ("FFFFFF" if r % 2 else "F2F4F8")
        name = [(o["nom"], True)] + ([("  ★", True)] if is_rec else [])
        fill(tbl.cell(r, 0), name, True, "222222", bg)
        for c, k in enumerate(keys, 1):
            fill(tbl.cell(r, c), str(o["valeurs"].get(k, "")), is_rec, "222222", bg, PP_ALIGN.CENTER)
        if has_detail:
            fill(tbl.cell(r, len(headers) - 1), o.get("detail", ""), False, "444444", bg)
    return h


def left_column(slide, x, y, w, avail, spec, primary, accent):
    """Place Contexte / Enjeux / Options avec UNE taille de police commune,
    et répartit l'espace restant entre les blocs (pas de trou en bas)."""
    blocks = []
    for label, key in (("Contexte", "contexte"), ("Enjeux & risques", "enjeux_risques")):
        items = [i if isinstance(i, str) else i["texte"] for i in spec.get(key, [])]
        if items:
            blocks.append({"label": label, "kind": "bullets", "paras": items, "flat": items})
    options = spec.get("options", [])
    rec = spec.get("option_recommandee")
    if options:
        keys = option_columns(options)
        if keys:
            blocks.append({"label": "Options étudiées", "kind": "table", "options": options, "keys": keys})
        else:
            paras, flat = option_paragraphs(options, rec)
            blocks.append({"label": "Options étudiées", "kind": "bullets", "paras": paras, "flat": flat})
    if not blocks:
        return

    def need(b, pt):
        if b["kind"] == "table":
            return HEAD_H + table_height(b["options"], b["keys"], w, pt) + 0.05
        return HEAD_H + est_height(b["flat"], w, pt)

    gaps = BLOCK_GAP * (len(blocks) - 1)
    pt = None
    for cand in BODY_SIZES:
        if sum(need(b, cand) for b in blocks) + gaps <= avail:
            pt = cand
            break
    if pt is None:
        pt = BODY_SIZES[-1]
        WARNINGS.append("AVERTISSEMENT : Contexte + Enjeux + Options ne tiennent pas ensemble même en "
                        f"{pt} pt — raccourcissez les puces les plus longues ou retirez-en une.")
    needs = [need(b, pt) for b in blocks]
    # l'espace libre va entre les blocs, pas en bas : la colonne reste remplie et aérée
    spare = max(0.0, avail - sum(needs) - gaps)
    extra_gap = spare / len(blocks) if len(blocks) > 1 else 0
    cy = y
    for b, n in zip(blocks, needs):
        section_header(slide, x, cy, w, b["label"], primary)
        body_h = n - HEAD_H
        if b["kind"] == "table":
            options_table(slide, x, cy + HEAD_H, w, b["options"], b["keys"], rec, pt, primary, accent)
        else:
            add_text(slide, x, cy + HEAD_H, w, body_h + extra_gap, b["paras"], pt, bullet=True,
                     name=f"Corps {b['label']}")
        cy += n + BLOCK_GAP + extra_gap


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
    # une seule taille pour tous les libellés, calée sur le plus long
    lib_pt = 11
    for cand in (11, 10, 9):
        lib_pt = cand
        if all(est_height([k["libelle"]], tw - 0.2, cand, bullet=False) <= th * 0.5 - 0.1 for k in kpis):
            break
    else:
        WARNINGS.append("AVERTISSEMENT : un libellé de chiffre clé est trop long — raccourcissez-le (≤ 50 caractères).")
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
        # La couleur dit si c'est une bonne nouvelle, la flèche dit le sens :
        # une baisse de coûts est verte, une hausse du churn est rouge.
        fav = k.get("tendance_favorable")
        if tend in ("hausse", "baisse") and fav is None:
            WARNINGS.append(f"AVERTISSEMENT : KPI « {val} » sans `tendance_favorable` — flèche affichée en gris.")
        sign_color = {True: "2E7D32", False: "C62828"}.get(fav, "666666")
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
        add_text(slide, tx + 0.15, ty + th * 0.5, this_w - 0.2, lib_h, [k["libelle"]], lib_pt,
                 color="444444", name=f"Libellé KPI {i+1}")


def build(spec, out_path):
    theme = spec.get("theme", {})
    primary = theme.get("primaire", "1F3864")
    accent = theme.get("accent", "C55A11")
    instance = spec.get("instance", "COMEX").strip() or "COMEX"

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

    left_column(slide, MARGIN, top, left_w, decision_y - top - 0.1, spec, primary, accent)
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
    add_text(slide, right_x + 0.15, decision_y + 0.08, right_w - 0.3, 0.3, [f"DÉCISION ATTENDUE DU {instance.upper()}"], 11,
             color="FFFFFF", bold=True, name="Titre décision")
    add_text(slide, right_x + 0.15, decision_y + 0.36, right_w - 0.3, bh - 0.42, [dec], dpt, color="FFFFFF",
             bold=True, name="Corps décision")

    # Pied de page
    foot_y = H - 0.45
    add_text(slide, MARGIN, foot_y, 8.5, 0.3, [spec.get("source", "")], 9, color="888888", name="Source")
    add_text(slide, W - MARGIN - 4, foot_y, 4, 0.3, [spec.get("confidentialite", f"Confidentiel — {instance}")], 9,
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
