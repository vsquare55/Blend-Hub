#!/usr/bin/env python3
"""Blend Hub - printable reports: formatted Excel and PDF (dashboard with shortlisted EPCs / banks / ECAs / investors / insurers,
optional discussion sheet with every comment and open action)."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import hubdb as H

TYPES = ["EPC", "Bank / Lender", "ECA", "Investor", "Insurer"]
TYPE_HEAD = {"EPC": "EPCs shortlisted", "Bank / Lender": "Banks / Lenders shortlisted", "ECA": "ECAs shortlisted",
             "Investor": "Investors shortlisted", "Insurer": "Insurers shortlisted"}
GROUPS = {"none": None, "lead": "Owner", "country": "Country", "status": "Status", "client": "Client type", "sector": "Sector"}


def _index(snap: dict) -> dict:
    P = {p["id"]: p for p in snap["parties"]}
    ix = {"P": P, "L": {}, "N": {}, "C": {}, "CM": {}, "A": {}, "M": {}}
    for l in snap["links"]:
        if l["party_id"] in P:
            ix["L"].setdefault(l["txn_id"], []).append({**l, "p": P[l["party_id"]]})
    for n in snap["needs"]:
        ix["N"][(n["txn_id"], n["type"])] = n["state"]
    for c in snap["chk"]:
        ix["C"].setdefault(c["txn_id"], {})[c["item"]] = c
    for c in snap["comments"]:
        ix["CM"].setdefault(c["txn_id"], []).append(c)
    for a in snap["actions"]:
        ix["A"].setdefault(a["txn_id"], []).append(a)
    for m in snap.get("meetings", []):
        ix["M"].setdefault(m["txn_id"], []).append(m)
    return ix


def _cell(ix, tid, ty) -> str:
    if ix["N"].get((tid, ty)) == "Not needed":
        bl = [l["p"]["name"] for l in ix["L"].get(tid, []) if l["p"]["type"] == ty and l["status"] != "Dropped"]
        return "not needed" + (" - brought by " + "; ".join(bl) if bl else "")
    ls = [l for l in ix["L"].get(tid, []) if l["p"]["type"] == ty and l["status"] in H.SHORTLISTED_UP]
    return "; ".join(f"{l['p']['name']} ({l['status']})" if l["status"] != "Shortlisted" else l["p"]["name"] for l in ls)


def _ready(ix, tid) -> str:
    c = ix["C"].get(tid, {})
    items = list(H.CHECK_ITEMS) + [k for k in c if k not in H.CHECK_ITEMS]  # the standard items + this project's own
    return f"{sum(1 for i in items if c.get(i, {}).get('state') in ('Yes', 'N.A.'))}/{len(items)}"


def _fact(ix, tid, item) -> str:
    x = ix["C"].get(tid, {}).get(item)
    return "" if not x or not x["state"] else x["state"] + (f" - {x['remark']}" if x["remark"] else "")


def rows_for(snap: dict, ids: List[int], group: str = "none", numbering: str = "dynamic") -> List[dict]:
    """Report rows in order, with group header rows and numbering. numbering: 'dynamic' (1..n through the list), 'restart' (1..n in every group)."""
    ix = _index(snap)
    by_id = {t["id"]: t for t in snap["txns"]}
    ts = [by_id[i] for i in ids if i in by_id]
    gkey = {"lead": lambda t: t["lead"] or "Unassigned", "country": lambda t: t["country"] or "(no country)", "status": lambda t: t["status"],
            "client": lambda t: t["client_type"], "sector": lambda t: t["sector"] or "(no sector)"}.get(group)
    if gkey:
        order = {s: i for i, s in enumerate(H.STATUSES)}
        ts.sort(key=lambda t: ((order.get(gkey(t), 99), gkey(t)) if group == "status" else (gkey(t).lower(),)) + (t["name"].lower(),))
    out, last, n = [], None, 0
    for t in ts:
        if gkey and gkey(t) != last:
            last = gkey(t)
            out.append({"group": last, "count": sum(1 for x in ts if gkey(x) == last)})
            if numbering == "restart":
                n = 0
        n += 1
        tid = t["id"]
        cm = ix["CM"].get(tid, [])
        acts = [a for a in ix["A"].get(tid, []) if not a["done"]]
        out.append({"t": t, "n": n, "ix": ix, "cells": {ty: _cell(ix, tid, ty) for ty in TYPES}, "ready": _ready(ix, tid),
                    "fsr": _fact(ix, tid, "FSR (feasibility study)"), "land": _fact(ix, tid, "Land available"),
                    "conc": _fact(ix, tid, "Concession agreement"), "last_comment": (f"{cm[0]['day']} {cm[0]['by']}: {cm[0]['text']}" if cm else ""),
                    "open_actions": len(acts), "comments": cm, "actions": ix["A"].get(tid, [])})
    return out


def _filters_line(opts: dict) -> List[str]:
    return [x for x in opts.get("filters", []) if x]


# --------------------------------------------------------------------------- Excel
def build_xlsx(snap: dict, ids: List[int], opts: dict, path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    group, numbering = opts.get("group", "none"), opts.get("numbering", "dynamic")
    rows = rows_for(snap, ids, group, numbering)
    wb = Workbook()
    ws = wb.active
    ws.title = "Pipeline"
    navy, red = "1B2F5B", "D81F26"
    head = ["Sr.", "Transaction", "Country", "Owner", "Status", "Client", "Tender / Negotiated", "Sector", "Structure", "Value"] + \
           [TYPE_HEAD[t] for t in TYPES] + ["Readiness", "FSR", "Land", "Concession agreement", "Open actions", "Last comment", "Next steps"]
    ws.append([opts.get("title") or "Blend - pipeline dashboard"])
    ws["A1"].font = Font(bold=True, size=16, color=navy)
    ws.append([f"{datetime.now():%d %b %Y}  ·  {len(ids)} transactions  ·  Prepared by Vishnu & Vijayraj  ·  INTERNAL"] + [""] * 3)
    for line in _filters_line(opts):
        ws.append([line])
    ws.append([])
    hr = ws.max_row + 1
    ws.append(head)
    thin = Side(style="thin", color="D9DEE8")
    for c in ws[hr]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=navy)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    stfill = {"Tie-up done": "DDF3E8", "P1": "E3ECFF", "P2": "ECE5FB", "Preliminary": "FFF0D2", "On hold": "ECEFF5"}
    for r in rows:
        if "group" in r:
            ws.append([f"{r['group']}   ({r['count']})"])
            for c in ws[ws.max_row]:
                c.font = Font(bold=True, color=navy)
                c.fill = PatternFill("solid", fgColor="E8EDF7")
            continue
        t = r["t"]
        ws.append([r["n"], t["name"], t["country"], t["lead"], t["status"], t["client_type"], t["procurement"], t["sector"], t["structure"], t["value"],
                   *[r["cells"][ty] for ty in TYPES], r["ready"], r["fsr"], r["land"], r["conc"], r["open_actions"], r["last_comment"], t["next_steps"]])
        row = ws[ws.max_row]
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = Border(bottom=thin)
        row[4].fill = PatternFill("solid", fgColor=stfill.get(t["status"], "FFFFFF"))
        if not t["active"]:
            for c in row:
                c.font = Font(color="8A93A8")
    widths = [5, 44, 13, 7, 12, 12, 13, 14, 16, 18, 26, 26, 20, 26, 20, 9, 22, 22, 22, 8, 40, 50]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(hr + 1, 3)
    ws.page_setup.orientation, ws.page_setup.paperSize, ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = "landscape", 8, 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{hr}:{hr}"
    if opts.get("discussion", True):
        d = wb.create_sheet("Discussion")
        d.append(["Transaction", "Country", "Owner", "Type", "Date", "By", "Comment / action", "Owner", "Due", "Status"])
        for c in d[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=navy)
        for r in rows:
            if "t" not in r:
                continue
            t = r["t"]
            for cm in sorted(r["comments"], key=lambda x: (x["day"], x["id"])):
                d.append([t["name"], t["country"], t["lead"], "Comment", cm["day"], cm["by"], cm["text"]])
            for a in r["actions"]:
                d.append([t["name"], t["country"], t["lead"], "Action", a["created"][:10], a["by"], a["text"], a["owner"], a["due"], "Done" if a["done"] else "Open"])
        for i, w in enumerate([44, 13, 7, 9, 11, 14, 90, 12, 11, 8], 1):
            d.column_dimensions[get_column_letter(i)].width = w
        for row in d.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        d.freeze_panes = "A2"
        d.page_setup.orientation, d.page_setup.fitToWidth, d.page_setup.fitToHeight = "landscape", 1, 0
        d.sheet_properties.pageSetUpPr.fitToPage = True
    if opts.get("counterparties", True):
        cp = wb.create_sheet("Counterparties")
        cp.append(["Type", "Counterparty", "Transactions mapped", "Shortlisted or further", "Appointed", "Dropped", "Notes"])
        for c in cp[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=navy)
        live = {t["id"] for t in snap["txns"]}
        for p in snap["parties"]:
            ls = [l for l in snap["links"] if l["party_id"] == p["id"] and l["txn_id"] in live]
            if ls:
                cp.append([p["type"], p["name"], len(ls), sum(1 for l in ls if l["status"] in H.SHORTLISTED_UP), sum(1 for l in ls if l["status"] == "Appointed"),
                           sum(1 for l in ls if l["status"] == "Dropped"), p["notes"]])
        for i, w in enumerate([14, 34, 12, 12, 11, 9, 60], 1):
            cp.column_dimensions[get_column_letter(i)].width = w
        cp.freeze_panes = "A2"
    wb.save(path)
    return path


# --------------------------------------------------------------------------- PDF (HTML -> Edge headless)
def build_html(snap: dict, ids: List[int], opts: dict) -> str:
    e = lambda s: html.escape(str(s or ""))
    rows = rows_for(snap, ids, opts.get("group", "none"), opts.get("numbering", "dynamic"))
    stc = {"Tie-up done": "#17935F", "P1": "#2C6BED", "P2": "#7A4FE0", "Preliminary": "#C27A06", "On hold": "#6B7690"}
    th = "".join(f"<th>{h}</th>" for h in ["Sr.", "Transaction", "Owner", "Status", "Client"] + [TYPE_HEAD[t].replace(" shortlisted", "") for t in TYPES] + ["Ready", "FSR / Land / Concession", "Last comment · next steps"])
    body = ""
    for r in rows:
        if "group" in r:
            body += f'<tr class="g"><td colspan="14">{e(r["group"])} <span>{r["count"]}</span></td></tr>'
            continue
        t = r["t"]
        facts = " · ".join(x for x in (("FSR: " + r["fsr"]) if r["fsr"] else "", ("Land: " + r["land"]) if r["land"] else "", ("Concession: " + r["conc"]) if r["conc"] else "") if x)
        body += (f'<tr class="{"" if t["active"] else "dim"}"><td>{r["n"]}</td><td><b>{e(t["name"])}</b><br><small>{e(t["country"])} · {e(t["sector"])} {e(t["structure"])} '
                 f'{e(t["value"])}{" · " + e(t["procurement"]) if t["procurement"] != "To confirm" else ""}</small></td><td>{e(t["lead"])}</td>'
                 f'<td><span class="st" style="background:{stc.get(t["status"], "#999")}">{e(t["status"])}</span></td><td>{e(t["client_type"])}</td>'
                 + "".join(f'<td>{e(r["cells"][ty]) or "—"}</td>' for ty in TYPES)
                 + f'<td>{r["ready"]}</td><td>{e(facts)}</td><td>{e(r["last_comment"])}{("<br><i>" + e(t["next_steps"][:240]) + "</i>") if t["next_steps"] else ""}</td></tr>')
    filt = "".join(f"<div>{e(x)}</div>" for x in _filters_line(opts))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(opts.get("title") or "Blend pipeline")}</title><style>
@page{{size:A3 landscape;margin:10mm}}body{{font:11px/1.35 "Segoe UI",Arial,sans-serif;color:#16213A}}
h1{{margin:0;font-size:20px;color:#1B2F5B}}.sub{{color:#6B7690;margin:2px 0 8px}}.f{{color:#6B7690;font-size:10.5px}}
table{{border-collapse:collapse;width:100%;margin-top:8px}}th{{background:#1B2F5B;color:#fff;text-align:left;padding:6px;font-size:10px;text-transform:uppercase}}
td{{padding:5px 6px;border-bottom:1px solid #DDE3EE;vertical-align:top}}tr{{break-inside:avoid}}tr.g td{{background:#E8EDF7;font-weight:700;color:#1B2F5B}}tr.g span{{color:#6B7690;font-weight:500}}
.st{{color:#fff;border-radius:9px;padding:1px 7px;font-weight:700;font-size:10px;white-space:nowrap}}.dim{{opacity:.55}}small{{color:#6B7690}}
.bar{{height:4px;background:linear-gradient(90deg,#D81F26,#F4A21E);margin-bottom:10px}}</style></head><body><div class="bar"></div>
<h1>{e(opts.get("title") or "Blend - pipeline dashboard")}</h1><div class="sub">{datetime.now():%d %b %Y} · {len([r for r in rows if "t" in r])} transactions · INTERNAL - not for clients</div><div class="f">{filt}</div>
<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></body></html>"""


def build_pdf(snap: dict, ids: List[int], opts: dict) -> Path:
    import printing
    p = printing.write_html("Blend_pipeline", build_html(snap, ids, opts))
    return printing.to_pdf(p)
