#!/usr/bin/env python3
"""
Add the projects in new_projects_data.py (named + unnamed slide each) to the EPC base deck.

    build_new_slides.py --out scratch.pptx          build a candidate deck (base untouched)
    build_new_slides.py --out x.pptx --install      ... and install it as the EPC base (old base archived, Excel synced)

The template is an existing slide of the base deck (the BESS slide), cloned and filled by shape name,
so the new slides look exactly like the existing ones.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deckcore as core  # noqa: E402
import new_projects_data as data  # noqa: E402

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: E402
from pptx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

TEMPLATE_ID = "togo_bess_named"
TOKEN = re.compile(r"\{\{(.*?)\|(.*?)\}\}")


def render(text: str, variant: str) -> str:
    return TOKEN.sub(lambda m: m.group(1) if variant == "named" else m.group(2), text)


REQUIRED_SHAPES = ("Title", "Subtitle", "Card head 1", "Card sub 1", "Bullets 1", "Chip 1.1", "Highlight 1",
                   "Card head 2", "Card sub 2", "Bullets 2", "Chip 2.1", "Highlight 2", "Strip label",
                   "Step text 1", "Step text 2", "Step text 3", "Step text 4", "Footer")


def find_template(prs):
    """The standard project slide: the BESS slide if present, otherwise ANY slide that has all the standard named shapes
    (so deleting the BESS project can never break 'add project')."""
    fallback = None
    for s in prs.slides:
        names = {sh.name for sh in s.shapes}
        if all(n in names for n in REQUIRED_SHAPES):
            if f"ID: {TEMPLATE_ID}" in core._notes(s):
                return s
            fallback = fallback or s
    if fallback is not None:
        return fallback
    raise core.DeckError("No standard project slide (with shapes 'Title', 'Card head 1', 'Bullets 1' ...) was found in the base "
                         "deck to use as the template.")


def clone_slide(prs, src):
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    tree_dst, tree_src = new.shapes._spTree, src.shapes._spTree
    keep = (qn("p:nvGrpSpPr"), qn("p:grpSpPr"))
    for ch in list(tree_dst):
        if ch.tag not in keep:
            tree_dst.remove(ch)
    for ch in tree_src:
        if ch.tag not in keep:
            tree_dst.append(copy.deepcopy(ch))
    bg_src = src._element.cSld.find(qn("p:bg"))
    if bg_src is not None and new._element.cSld.find(qn("p:bg")) is None:
        new._element.cSld.insert(0, copy.deepcopy(bg_src))
    rid_map = {}
    for rel in src.part.rels.values():
        if "image" in rel.reltype:
            rid_map[rel.rId] = new.part.relate_to(rel.target_part, RT.IMAGE)
    for el in new._element.iter():
        for a in list(el.attrib):
            if a.split("}")[-1] in ("embed", "link") and el.attrib[a] in rid_map:
                el.attrib[a] = rid_map[el.attrib[a]]
    return new


def _shape(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    raise KeyError(f"shape '{name}' missing in template")


def _set_paras(shape, rows):
    """rows: list of [text, text, ...] -> one paragraph each; run i takes the template paragraph's run i."""
    txb = shape._element.txBody
    paras = txb.findall(qn("a:p"))
    tmpl = copy.deepcopy(paras[0])
    for p in paras:
        txb.remove(p)
    for row in rows:
        p = copy.deepcopy(tmpl)
        runs = p.findall(qn("a:r"))
        for i, r in enumerate(runs):
            if i < len(row):
                r.find(qn("a:t")).text = row[i]
            else:
                p.remove(r)
        txb.append(p)


def set_notes(slide, template, text):
    """Notes slide with a real text frame: borrow the shape structure of the template slide's notes."""
    ns = slide.notes_slide
    if ns.notes_text_frame is None:
        keep = (qn("p:nvGrpSpPr"), qn("p:grpSpPr"))
        tree_dst, tree_src = ns.shapes._spTree, template.notes_slide.shapes._spTree
        for ch in list(tree_dst):
            if ch.tag not in keep:
                tree_dst.remove(ch)
        for ch in tree_src:
            if ch.tag not in keep:
                tree_dst.append(copy.deepcopy(ch))
    tf = ns.notes_text_frame
    if tf is None:
        raise core.DeckError("Could not create speaker notes for a new slide.")
    tf.text = text


def _drop(slide, *names):
    """Remove the named shapes from the slide (silently ignores names that are not there)."""
    for sh in list(slide.shapes):
        if sh.name in names:
            sh._element.getparent().remove(sh._element)


def _relayout_steps(slide, active):
    """Re-space the snapshot boxes so that k (1-4) boxes fill the row evenly. active = 1-based step numbers kept."""
    k = len(active)
    shapes = {sh.name: sh for sh in slide.shapes}
    left0, total, gap = Inches(0.4), Inches(12.53), Inches(0.14)
    w = int((total - gap * (k - 1)) / k)
    for j, i in enumerate(active):
        x = int(left0 + j * (w + gap))
        box, num, txt = shapes[f"Step box {i}"], shapes[f"Step num {i}"], shapes[f"Step text {i}"]
        box.left, box.width = x, w
        num.left = x + int((w - num.width) / 2)
        txt.left, txt.width = x + Inches(0.05), w - Inches(0.1)
    for c in (1, 2, 3):  # chevrons sit between neighbouring boxes
        ch = shapes.get(f"Chevron {c}")
        if ch is None:
            continue
        if c <= k - 1:
            box_left = int(left0 + (c - 1) * (w + gap))  # chevron c sits in the gap right after box c
            ch.left = box_left + w + int((gap - ch.width) / 2)
        else:
            ch._element.getparent().remove(ch._element)


def fill(slide, d, variant, template, tag_variant=None):
    """
    Fill the standard project slide.  ONLY the title is required: every empty field simply removes its box from the
    slide (a card with nothing in it disappears completely; the snapshot row re-spaces itself).
    tag_variant='single' writes an untagged-suffix ID (one slide used for both versions).
    """
    R = lambda t: render(t, variant)  # noqa: E731
    core._strip_value_shapes(slide)  # never inherit a value box from the template slide
    _set_paras(_shape(slide, "Title"), [[R(d["title"])]])
    if R(d.get("sub", "")).strip():
        _set_paras(_shape(slide, "Subtitle"), [[R(d["sub"])]])
    else:
        _drop(slide, "Subtitle")
    for i, key in ((1, "A"), (2, "B")):
        head, sub, bullets, chip, hl = d.get(key) or ("", "", [], "", "")
        rb = [(R(a), R(b)) for a, b in bullets if (R(a) + R(b)).strip()]
        if not (R(head).strip() or R(sub).strip() or rb or R(chip).strip() or R(hl).strip()):
            _drop(slide, f"Card {i}", f"Badge {i}", f"Card head {i}", f"Card sub {i}", f"Bullets {i}", f"Chip {i}.1", f"Highlight {i}")
            continue
        for nm, txt in ((f"Card head {i}", R(head)), (f"Card sub {i}", R(sub)), (f"Chip {i}.1", R(chip)), (f"Highlight {i}", R(hl))):
            if txt.strip():
                _set_paras(_shape(slide, nm), [[txt]])
            else:
                _drop(slide, nm)
        if rb:
            _set_paras(_shape(slide, f"Bullets {i}"), [list(x) for x in rb])
        else:
            _drop(slide, f"Bullets {i}")
    steps = [(R(a), R(b)) for a, b in d.get("steps", [])][:4]
    steps += [("", "")] * (4 - len(steps))
    active = [i for i, (a, b) in enumerate(steps, 1) if (a + b).strip()]
    for i, (a, b) in enumerate(steps, 1):
        if i in active:
            _set_paras(_shape(slide, f"Step text {i}"), [[a], [b]] if b.strip() else [[a]])
        else:
            _drop(slide, f"Step box {i}", f"Step num {i}", f"Step text {i}")
    if active:
        strip = R(d.get("strip", "")).strip() or "PROJECT SNAPSHOT"
        _set_paras(_shape(slide, "Strip label"), [[strip]])
        _relayout_steps(slide, active)
    else:
        _drop(slide, "Strip label", "Chevron 1", "Chevron 2", "Chevron 3")
    if R(d.get("footer", "")).strip():
        _set_paras(_shape(slide, "Footer"), [[R(d["footer"])]])
    else:
        _drop(slide, "Footer")
    if d.get("value"):
        tb = slide.shapes.add_textbox(Inches(6.9), Inches(7.0), Inches(6.03), Inches(0.38))
        tb.name = "VALUE"  # removed automatically unless 'show value' is ticked
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_top = tf.margin_bottom = 0
        tf.margin_right = Inches(0.2)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        r = p.add_run()
        r.text = R(d["value"])
        r.font.size, r.font.bold, r.font.name = Pt(10), True, "Calibri"
        r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    suffix = "" if tag_variant == "single" else "_" + variant
    cat = d.get("category") or ("Hold" if d.get("hold") else "")
    set_notes(slide, template, f"ID: {d['key']}{suffix}" + (chr(10) + "CATEGORY: " + cat if cat else ""))


def slide_text(slide):
    return core._slide_text(slide)


def check_no_leak(d, unnamed_slide):
    """Every distinctive word on the named side of a token must be absent from the unnamed slide."""
    txt = slide_text(unnamed_slide).lower()
    probs = []
    allsrc = " ".join([d["title"], d["sub"], d["strip"], d["footer"], d.get("value", "")]
                      + [x for k in ("A", "B") for x in (d[k][0], d[k][1], d[k][3], d[k][4])]
                      + [a + b for k in ("A", "B") for a, b in d[k][2]] + [a + b for a, b in d["steps"]])
    for named, alt in TOKEN.findall(allsrc):
        alt_words = {w.lower() for w in re.findall(r"\w+", alt)}
        for w in re.findall(r"[^\W\d_]{4,}", named, re.U):
            if w.lower() not in alt_words and re.search(r"(?<!\w)" + re.escape(w.lower()) + r"(?!\w)", txt):
                probs.append(w)
    for t in core.load_config()["sensitive_terms"] + [d["country"]]:
        if len(t) > 2 and re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", txt):
            probs.append(t)
    return sorted(set(probs))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args()

    src = core.base_path("EPC")
    prs = core._open_presentation(src)
    existing = {s["key"] for s in core.scan_base(src)["projects"]}
    todo = [d for d in data.P if d["key"] not in existing]
    if not todo:
        print("Nothing to add - every project in new_projects_data.py is already in the base deck.")
        return 0
    template = find_template(prs)
    sld = prs.slides._sldIdLst
    original_ids = [e.get(qn("r:id")) for e in sld]
    created = {}  # key -> [named_rid, unnamed_rid]
    problems = []
    for d in todo:
        created[d["key"]] = []
        for variant in ("named", "unnamed"):
            s = clone_slide(prs, template)
            fill(s, d, variant, template)
            created[d["key"]].append(list(prs.slides._sldIdLst)[-1].get(qn("r:id")))
            if variant == "unnamed":
                bad = check_no_leak(d, s)
                if bad:
                    problems.append((d["key"], bad))
    if problems:
        for k, b in problems:
            print(f"LEAK in unnamed slide of {k}: {b}")
        raise SystemExit("Aborted: named-side words found on unnamed slides (nothing was written).")

    # ---- order: insert each section's block after the last slide of its anchor project
    rid_el = {e.get(qn("r:id")): e for e in prs.slides._sldIdLst}
    order = list(original_ids)
    key_of = {}
    for i, s in enumerate(list(prs.slides)[:len(original_ids)]):
        m = core.ID_RE.search(core._notes(s))
        if m:
            key_of[original_ids[i]] = core.norm_id(m.group(1))
    for section, after in data.AFTER.items():
        block = []
        for d in todo:
            if d["section"] == section:
                block += created[d["key"]]
        idxs = [i for i, r in enumerate(order) if key_of.get(r, "").startswith(after + "_") or key_of.get(r) == after]
        if not idxs:
            raise SystemExit(f"Anchor project '{after}' not found in the base deck.")
        order[idxs[-1] + 1:idxs[-1] + 1] = block
    lst = prs.slides._sldIdLst
    for e in list(lst):
        lst.remove(e)
    for r in order:
        lst.append(rid_el[r])
    prs.save(args.out)
    print(f"Built {len(todo)} projects x 2 versions = {2 * len(todo)} slides -> {args.out}  ({len(order)} slides total)")
    if args.install:
        core.replace_base("EPC", args.out)
        # fill Country / Region / Model for the new registry rows
        from openpyxl import load_workbook
        wb = load_workbook(core.REGISTRY_XLSX)
        ws = wb[core.audience_cfg("EPC")["sheet"][:31]]
        hdr = {c.value: i + 1 for i, c in enumerate(ws[1])}
        by = {d["key"]: d for d in todo}
        for r in range(2, ws.max_row + 1):
            k = ws.cell(r, hdr["ID"]).value
            if k in by:
                d = by[k]
                ws.cell(r, hdr["Country"]).value = d["country"]
                ws.cell(r, hdr["Region (Unnamed)"]).value = data.REGION[d["country"]]
                ws.cell(r, hdr["Model"]).value = d["model"]
                ws.cell(r, hdr["Notes"]).value = ("DRAFT placeholder - details to be added"
                                                  if d.get("placeholder") else "Added from pipeline sheet")
        core._backup_registry()
        wb.save(core.REGISTRY_XLSX)
        print("Registry updated with country / region / model for the new projects.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except core.DeckError as exc:
        print("\n*** PROBLEM ***\n" + str(exc))
        sys.exit(1)
