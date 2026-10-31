#!/usr/bin/env python3
"""
Printing for the project lists (main screen, Manage projects, Sources).

* Print...   : opens the list in your browser, laid out for the paper size and orientation you chose (landscape by default),
               and the browser's print dialog opens by itself.
* Save PDF   : writes a real PDF (via Edge / Chrome, no extra software) and opens it.
* Excel      : a worksheet already set to print landscape, fit to one page wide, header row repeated on every page.
Page layout rules: header row repeats on every page, rows are never split across pages, page numbers in the footer.
"""
from __future__ import annotations

import html
import os
import subprocess
import tempfile
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Tuple

import deckcore as core

PAPERS = {"A4": "A4", "A3": "A3", "Letter": "Letter", "Legal": "Legal"}
FONT = {"Small": 7.5, "Normal": 9, "Large": 10.5}
CAT_COLOR = {"Closed": "#2E7D32", "Active": "#1565C0", "BIP": "#B07800", "Hold": "#C62828"}
PRINT_DIR = core.OUTPUT_DIR / "Prints"


def find_browser() -> Optional[str]:
    return core.find_chromium()


# --------------------------------------------------------------------------- HTML
def _grouped(rows: List[dict], group_by: Optional[str]) -> List[dict]:
    """Stable: rows of the same group are brought together, their on-screen order is kept inside each group; blanks last."""
    if not group_by:
        return rows
    key = lambda r: (str(r.get(group_by, "") or "").strip() == "", str(r.get(group_by, "") or "").lower())  # noqa: E731
    return sorted(rows, key=key)


def build_html(title: str, meta: List[str], columns: List[Tuple[str, str]], rows: List[dict], paper: str = "A4",
               landscape: bool = True, font_pt: float = 9, group_by: Optional[str] = None, auto_print: bool = False,
               footer: str = "DealDeck Studio - confidential") -> str:
    """columns = [(key, heading)]; rows = list of dict. Everything is escaped."""
    e = html.escape
    size = f"{PAPERS.get(paper, 'A4')} {'landscape' if landscape else 'portrait'}"
    css = f"""
@page {{ size: {size}; margin: 11mm 10mm 13mm 10mm;
  @bottom-left {{ content: "{e(footer)}"; font: 7.5pt Segoe UI, Arial; color: #78909C; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font: 7.5pt Segoe UI, Arial; color: #78909C; }} }}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {font_pt}pt; color: #22293A; margin: 0; }}
h1 {{ font-size: {font_pt + 6}pt; color: #1B3A5F; margin: 0 0 2px 0; }}
.meta {{ color: #546E7A; font-size: {font_pt - 0.5}pt; margin: 0 0 6px 0; line-height: 1.35; }}
table {{ border-collapse: collapse; width: 100%; }}
thead {{ display: table-header-group; }}
tfoot {{ display: table-footer-group; }}
th {{ background: #1B3A5F; color: #fff; text-align: left; padding: 4px 6px; font-weight: 600; }}
td {{ padding: 3px 6px; border-bottom: 1px solid #D5DBE3; vertical-align: top; }}
tr {{ page-break-inside: avoid; break-inside: avoid; }}
tbody tr:nth-child(even) td {{ background: #F4F7FB; }}
tr.group td {{ background: #DCE6F2 !important; color: #1B3A5F; font-weight: 700; border-top: 2px solid #1B3A5F; padding: 4px 6px; }}
.cat {{ font-weight: 700; }}
.num {{ text-align: right; color: #78909C; white-space: nowrap; }}
.nw {{ white-space: nowrap; }}
.blank {{ color: #B0BEC5; }}
@media screen {{ body {{ margin: 14px 18px; }} }}
"""
    rows = _grouped(rows, group_by)
    head = "".join(f"<th>{e(h)}</th>" for _, h in columns)
    body, last, n_in_group = [], object(), 0

    def cell(key, val):
        v = "" if val is None else str(val)
        if key == "category" and v in CAT_COLOR:
            return f'<td class="cat nw" style="color:{CAT_COLOR[v]}">{e(v)}</td>'
        cls = "num" if key in ("sr", "dyn", "n") else ("nw" if key in ("show", "version", "default", "ticked", "slides", "count", "active", "bip", "hold", "closed") else "")
        if not v.strip():
            return f'<td class="{cls} blank">&mdash;</td>' if key not in ("show", "check") else f'<td class="{cls}"></td>'
        return f'<td class="{cls}">{e(v)}</td>'

    for r in rows:
        if group_by:
            g = str(r.get(group_by, "") or "(none)")
            if g != last:
                cnt = sum(1 for x in rows if str(x.get(group_by, "") or "(none)") == g)
                body.append(f'<tr class="group"><td colspan="{len(columns)}">{e(g)} &nbsp;<span style="font-weight:400">({cnt})</span></td></tr>')
                last = g
        body.append("<tr>" + "".join(cell(k, r.get(k)) for k, _ in columns) + "</tr>")
    meta_html = "<br>".join(e(m) for m in meta if m)
    script = "<script>window.addEventListener('load',function(){setTimeout(function(){window.print();},350);});</script>" if auto_print else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{e(title)}</title><style>{css}</style></head><body>"
            f"<h1>{e(title)}</h1><div class='meta'>{meta_html}</div>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>{script}</body></html>")


def write_html(name: str, content: str) -> Path:
    PRINT_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip().replace(" ", "_")[:60] or "list"
    p = PRINT_DIR / f"{safe}_{datetime.now():%Y%m%d_%H%M%S}.html"
    p.write_text(content, encoding="utf-8")
    return p


def to_pdf(html_path: Path) -> Path:
    exe = find_browser()
    if not exe:
        raise core.DeckError("Microsoft Edge or Google Chrome is needed to create the PDF, and neither was found (Safari cannot do it). "
                             "Use 'Print...' instead (it opens in your default browser) or save as Excel.")
    pdf = html_path.with_suffix(".pdf")
    prof = tempfile.mkdtemp(prefix="dds_pdf_")
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={prof}",
           f"--print-to-pdf={pdf}", html_path.as_uri()]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise core.DeckError("Creating the PDF took too long. Try 'Print...' instead.")
    import time
    last, t0 = -1, time.time()
    while time.time() - t0 < 25:  # the browser flushes the file shortly AFTER it exits: wait until it exists and stops growing
        size = pdf.stat().st_size if pdf.exists() else 0
        if size > 500 and size == last:
            return pdf
        last = size
        time.sleep(0.6)
    raise core.DeckError("The PDF could not be created. Use 'Print...' instead (it opens in your browser).")


def open_file(p: Path) -> None:
    try:
        core.os_open(p)
    except Exception as exc:
        raise core.DeckError(f"Could not open {p.name}: {exc}")


def to_excel(name: str, title: str, meta: List[str], columns: List[Tuple[str, str]], rows: List[dict], paper: str = "A4",
             landscape: bool = True, group_by: Optional[str] = None) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "List"[:31]
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14, color="1B3A5F")
    for m in meta:
        if m:
            ws.append([m])
    ws.append([])
    hdr_row = ws.max_row + 1
    ws.append([h for _, h in columns])
    for c in ws[hdr_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1B3A5F")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    last = object()
    rows = _grouped(rows, group_by)
    for r in rows:
        if group_by:
            g = str(r.get(group_by, "") or "(none)")
            if g != last:
                ws.append([g])
                for c in ws[ws.max_row]:
                    c.font = Font(bold=True, color="1B3A5F")
                    c.fill = PatternFill("solid", fgColor="DCE6F2")
                last = g
        ws.append([("" if r.get(k) is None else r.get(k)) for k, _ in columns])
    widths = {"sr": 8, "dyn": 6, "lead": 12, "lead_country": 24, "model": 16, "show": 9, "name": 56, "key": 28, "category": 10, "version": 11, "country": 16, "sector": 22, "source": 30,
              "role": 70, "type": 22, "slides": 14}
    for i, (k, _) in enumerate(columns):
        ws.column_dimensions[ws.cell(hdr_row, i + 1).column_letter].width = widths.get(k, 16)
        for cell in ws[ws.cell(hdr_row, i + 1).column_letter][hdr_row:]:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = ws.cell(hdr_row + 1, 1)
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = {"A4": 9, "A3": 8, "Letter": 1, "Legal": 5}.get(paper, 9)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{hdr_row}:{hdr_row}"
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top, ws.page_margins.bottom = 0.5, 0.6
    ws.oddFooter.left.text = "DealDeck Studio - confidential"
    ws.oddFooter.right.text = "Page &P of &N"
    PRINT_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip().replace(" ", "_")[:60] or "list"
    out = PRINT_DIR / f"{safe}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    wb.save(out)
    return out


NUMBERING = ["Dynamic: 1, 2, 3 in printed order", "Deck Sr. No. (as on screen)", "Both"]


def apply_numbering(cols, rows, group_by, mode, restart):
    """Replace the 'sr' column by a fresh running number (after grouping, so it never looks random), the deck's own
    Sr. No., or both. Rows are copied; the originals are untouched."""
    rows = [dict(r) for r in _grouped(rows, group_by)]
    n, last = 0, object()
    for r in rows:
        g = str(r.get(group_by, "") or "(none)") if group_by else None
        if restart and g != last:
            n, last = 0, g
        n += 1
        r["dyn"] = n
    out = []
    for k, h in cols:
        if k != "sr":
            out.append((k, h))
        elif mode.startswith("Dynamic"):
            out.append(("dyn", "No."))
        elif mode.startswith("Deck"):
            out.append(("sr", "Sr."))
        else:
            out += [("dyn", "No."), ("sr", "Deck Sr.")]
    return out, rows


# --------------------------------------------------------------------------- the window
class PrintDialog(tk.Toplevel):
    """
    provider = {
      "title": str, "name": str (file name base),
      "meta": Callable[[], List[str]]            lines under the title (filters, client, ...),
      "columns": [(key, heading, default_on)],
      "rows": Callable[[bool], List[dict]]       rows in the order shown; arg = only the selected / ticked ones,
      "only_label": str                          text of the 'only ...' choice,
      "groups": {label: key}                     optional 'group by' choices,
    }
    """

    def __init__(self, parent, provider: dict):
        super().__init__(parent)
        self.p = provider
        self.title("Print / PDF - " + provider["title"])
        self.transient(parent)
        self.grab_set()
        f = tk.Frame(self, padx=14, pady=10)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Print the list exactly as it is shown on screen (current sort and filters).", anchor="w",
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")

        tk.Label(f, text="Rows:").grid(row=1, column=0, sticky="nw", pady=(10, 0))
        self.only = tk.BooleanVar(value=False)
        tk.Radiobutton(f, text="All rows shown", value=False, variable=self.only).grid(row=1, column=1, sticky="w", pady=(8, 0))
        tk.Radiobutton(f, text=provider.get("only_label", "Only the selected rows"), value=True, variable=self.only).grid(row=2, column=1, sticky="w")

        tk.Label(f, text="Columns:").grid(row=3, column=0, sticky="nw", pady=(10, 0))
        cf = tk.Frame(f)
        cf.grid(row=3, column=1, columnspan=3, sticky="w", pady=(8, 0))
        self.cols = {}
        for i, (k, h, on) in enumerate(provider["columns"]):
            v = tk.BooleanVar(value=on)
            self.cols[k] = (v, h)
            ttk.Checkbutton(cf, text=h, variable=v).grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 18))

        tk.Label(f, text="Paper:").grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.paper = tk.StringVar(value="A4")
        ttk.Combobox(f, textvariable=self.paper, values=list(PAPERS), state="readonly", width=9).grid(row=4, column=1, sticky="w", pady=(12, 0))
        self.orient = tk.StringVar(value="Landscape")
        ttk.Combobox(f, textvariable=self.orient, values=["Landscape", "Portrait"], state="readonly", width=11).grid(row=4, column=2, sticky="w", pady=(12, 0))
        tk.Label(f, text="Text size:").grid(row=5, column=0, sticky="w", pady=4)
        self.font = tk.StringVar(value="Normal")
        ttk.Combobox(f, textvariable=self.font, values=list(FONT), state="readonly", width=9).grid(row=5, column=1, sticky="w")
        groups = provider.get("groups") or {}
        tk.Label(f, text="Group by:").grid(row=6, column=0, sticky="w", pady=4)
        self.group = tk.StringVar(value="(none)")
        ttk.Combobox(f, textvariable=self.group, values=["(none)"] + list(groups), state="readonly", width=16).grid(row=6, column=1, sticky="w")
        self.has_sr = any(k == "sr" for k, _, _ in provider["columns"])
        if self.has_sr:
            tk.Label(f, text="Numbering:").grid(row=7, column=0, sticky="w", pady=4)
            self.numbering = tk.StringVar(value=NUMBERING[0])
            ttk.Combobox(f, textvariable=self.numbering, values=NUMBERING, state="readonly", width=34).grid(row=7, column=1, columnspan=2, sticky="w")
            self.restart = tk.BooleanVar(value=False)
            ttk.Checkbutton(f, text="restart at 1 in each group", variable=self.restart).grid(row=7, column=3, sticky="w")
        tk.Label(f, text="Title:").grid(row=8, column=0, sticky="w", pady=4)
        self.ttl = tk.StringVar(value=provider["title"])
        ttk.Entry(f, textvariable=self.ttl, width=60).grid(row=8, column=1, columnspan=3, sticky="w")

        self.warn_src = tk.Label(f, text="\u26a0 This printout shows SOURCE names - for internal use only, do not send it to a client.",
                                 fg="#C62828", font=("Segoe UI", 9, "bold"), anchor="w")
        self.warn_src.grid(row=9, column=0, columnspan=4, sticky="w", pady=(8, 0))
        for k, (v, h) in self.cols.items():
            v.trace_add("write", lambda *a: self._src_warn())
        self._src_warn()
        self.msg = tk.Label(f, text="", fg="#C62828", anchor="w", wraplength=520, justify="left")
        self.msg.grid(row=10, column=0, columnspan=4, sticky="w", pady=(2, 0))
        b = tk.Frame(f)
        b.grid(row=11, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Close", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(b, text="Save as Excel (landscape)", command=lambda: self.go("xlsx")).pack(side="right", padx=4)
        ttk.Button(b, text="Save as PDF", command=lambda: self.go("pdf")).pack(side="right", padx=4)
        tk.Button(b, text="Print\u2026", command=lambda: self.go("print"), bg="#1565C0", fg="white", relief="flat", padx=16, pady=3,
                  font=("Segoe UI", 10, "bold")).pack(side="right", padx=4)

    def _src_warn(self):
        shown = "source" in self.cols and self.cols["source"][0].get()
        if shown:
            self.warn_src.grid()
        else:
            self.warn_src.grid_remove()

    def _collect(self):
        cols = [(k, h) for k, (v, h) in self.cols.items() if v.get()]
        if not cols:
            raise core.DeckError("Tick at least one column.")
        rows = self.p["rows"](bool(self.only.get()))
        if not rows:
            raise core.DeckError("There are no rows to print with this choice.")
        grp = (self.p.get("groups") or {}).get(self.group.get())
        if self.has_sr and any(k == "sr" for k, _ in cols):
            cols, rows = apply_numbering(cols, rows, grp, self.numbering.get(), bool(self.restart.get()))
        meta = list(self.p["meta"]()) + [f"{len(rows)} row(s)  \u00b7  printed {datetime.now():%d %b %Y, %H:%M}"]
        return cols, rows, grp, meta

    def go(self, kind: str):
        self.msg.configure(text="")
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            cols, rows, grp, meta = self._collect()
            land = self.orient.get() == "Landscape"
            if kind == "xlsx":
                out = to_excel(self.p["name"], self.ttl.get(), meta, cols, rows, self.paper.get(), land, grp)
                open_file(out)
                self.msg.configure(text=f"Saved: {out}", fg="#2E7D32")
                return
            doc = build_html(self.ttl.get(), meta, cols, rows, self.paper.get(), land, FONT[self.font.get()], grp, auto_print=(kind == "print"))
            path = write_html(self.p["name"], doc)
            if kind == "print":
                open_file(path)  # the page asks the browser to open its print dialog
                self.msg.configure(text="Opened in your browser - choose your printer in the print window. "
                                        "(Layout is already " + ("landscape" if land else "portrait") + ", " + self.paper.get() + ".)", fg="#2E7D32")
            else:
                pdf = to_pdf(path)
                open_file(pdf)
                self.msg.configure(text=f"Saved: {pdf}", fg="#2E7D32")
        except core.DeckError as exc:
            self.msg.configure(text=str(exc), fg="#C62828")
        finally:
            self.configure(cursor="")
