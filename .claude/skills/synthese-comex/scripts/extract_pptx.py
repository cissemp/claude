#!/usr/bin/env python3
"""Extrait tout le contenu utile d'un .pptx en Markdown, diapo par diapo.

Usage : python extract_pptx.py source.pptx [sortie.md]

Récupère : titres, textes (y compris dans les groupes), tableaux,
données des graphiques natifs, texte alternatif des images et notes
de l'orateur. Les notes contiennent souvent l'essentiel du raisonnement :
ne les ignorez pas.
"""
import sys
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def iter_shapes(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(sh.shapes)
        else:
            yield sh


def shape_to_md(sh):
    out = []
    if sh.has_text_frame:
        for p in sh.text_frame.paragraphs:
            t = "".join(r.text for r in p.runs).strip()
            if t:
                out.append(("  " * p.level) + "- " + t)
    if getattr(sh, "has_table", False) and sh.has_table:
        rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in sh.table.rows]
        if rows:
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "---|" * len(rows[0]))
            for r in rows[1:]:
                out.append("| " + " | ".join(r) + " |")
    if getattr(sh, "has_chart", False) and sh.has_chart:
        ch = sh.chart
        title = ""
        try:
            if ch.has_title:
                title = ch.chart_title.text_frame.text
        except Exception:
            pass
        out.append(f"[Graphique{': ' + title if title else ''}]")
        try:
            cats = list(ch.plots[0].categories)
            for plot in ch.plots:
                for s in plot.series:
                    vals = list(s.values)
                    pairs = ", ".join(f"{c}={v}" for c, v in zip(cats, vals))
                    out.append(f"  - {s.name} : {pairs}")
        except Exception:
            out.append("  - (données non lisibles)")
    if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            alt = sh._element.nvPicPr.cNvPr.get("descr") or ""
        except Exception:
            alt = ""
        out.append(f"[Image{': ' + alt if alt else ' sans texte alternatif'}]")
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    prs = Presentation(sys.argv[1])
    lines = []
    for i, slide in enumerate(prs.slides, 1):
        title = slide.shapes.title.text.strip() if slide.shapes.title is not None and slide.shapes.title.has_text_frame else ""
        lines.append(f"\n## Diapo {i}{' — ' + title if title else ''}")
        for sh in iter_shapes(slide.shapes):
            if slide.shapes.title is not None and sh.shape_id == slide.shapes.title.shape_id:
                continue
            lines.extend(shape_to_md(sh))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append("> Notes : " + notes.replace("\n", " "))
    md = "\n".join(lines).strip() + "\n"
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Écrit : {sys.argv[2]} ({len(prs.slides)} diapos)")
    else:
        print(md)


if __name__ == "__main__":
    main()
