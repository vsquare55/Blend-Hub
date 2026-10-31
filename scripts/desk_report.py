#!/usr/bin/env python3
"""Project Desk reports (internal): discussion sheet, weekly review (what changed since a date) and action list by owner.
Each prints, saves as PDF or exports to Excel for exactly the projects currently shown in the Desk."""
from __future__ import annotations

import html
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
from typing import Callable, Dict, List

import deckcore as core
import printing as pr
import tracker as T

CAT = pr.CAT_COLOR
E = html.escape


def _css(paper: str, landscape: bool, f: float) -> str:
    return f"""
@page {{ size: {paper} {'landscape' if landscape else 'portrait'}; margin: 11mm 10mm 13mm 10mm;
  @bottom-left {{ content: "DealDeck Studio - Project Desk - INTERNAL, not for clients"; font: 7.5pt Segoe UI, Arial; color: #C62828; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font: 7.5pt Segoe UI, Arial; color: #78909C; }} }}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {f}pt; color: #22293A; margin: 0; }}
h1 {{ font-size: {f + 6}pt; color: #1B3A5F; margin: 0 0 2px; }}
.meta {{ color: #546E7A; font-size: {f - 0.5}pt; margin: 0 0 8px; line-height: 1.4; }}
h2 {{ background: #1B3A5F; color: #fff; padding: 4px 8px; margin: 12px 0 6px; font-size: {f + 1.5}pt; break-after: avoid; }}
h3 {{ color: #1B3A5F; border-bottom: 2px solid #1B3A5F; margin: 10px 0 5px; padding-bottom: 2px; font-size: {f + 1}pt; break-after: avoid; }}
.proj {{ border: 1px solid #CFD8DC; border-radius: 4px; margin: 0 0 8px; padding: 6px 8px; break-inside: avoid; page-break-inside: avoid; }}
.ph {{ font-weight: 700; font-size: {f + 1.5}pt; color: #1B3A5F; }}
.pm {{ color: #546E7A; font-size: {f - 0.5}pt; margin: 1px 0 4px; }}
.tag {{ display: inline-block; padding: 0 6px; border-radius: 8px; background: #E3EAF3; margin-right: 4px; font-size: {f - 1}pt; }}
.sum {{ background: #F7F9FC; border-left: 3px solid #90A4AE; padding: 3px 6px; margin: 3px 0; font-style: italic; }}
.kpi {{ display: inline-block; margin: 0 14px 4px 0; }} .kpi b {{ font-size: {f + 4}pt; color: #1B3A5F; }}
table {{ border-collapse: collapse; width: 100%; margin: 2px 0 4px; }}
th {{ text-align: left; background: #ECEFF1; color: #37474F; padding: 2px 5px; font-size: {f - 1}pt; }}
td {{ padding: 2px 5px; border-bottom: 1px solid #E4E8EC; vertical-align: top; }}
.nw {{ white-space: nowrap; }}
.sec {{ font-weight: 700; color: #455A64; margin-top: 4px; font-size: {f - 0.5}pt; text-transform: uppercase; letter-spacing: .4px; }}
.none {{ color: #90A4AE; font-style: italic; }} .done {{ color: #90A4AE; text-decoration: line-through; }} .over {{ color: #C62828; font-weight: 700; }}
@media screen {{ body {{ margin: 14px 18px; }} }}
"""


def _page(title, meta, body, css, auto_print):
    script = "<script>window.addEventListener('load',function(){setTimeout(function(){window.print();},350);});</script>" if auto_print else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{E(title)}</title><style>{css}</style></head><body>"
            f"<h1>{E(title)}</h1><div class='meta'>{'<br>'.join(E(m) for m in meta if m)}</div>{body}{script}</body></html>")


def _lead_head(lead: str) -> str:
    tm = ", ".join(T.team().get(lead, [])) if lead else ""
    return f"<h2>{E(lead or 'Unassigned')}" + (f" &nbsp;<span style='font-weight:400'>team: {E(tm)}</span>" if tm else "") + "</h2>"


# --------------------------------------------------------------------------- 1. discussion sheet
def build_report(items: List[dict], sections: Dict[str, bool], title: str, meta: List[str], group: bool, paper: str, landscape: bool,
                 font_pt: float, auto_print: bool, show_closed: bool) -> str:
    """items: [{'p': project, 'lead': 'JT', 'o': overview, 'proj': proj record, 'reqs', 'cmts', 'acts'}] in the order to print."""
    parts: List[str] = []
    last_lead = last_country = object()
    td = T.today()
    for it in items:
        p, lead, pj = it["p"], it["lead"], it["proj"]
        if group:
            if lead != last_lead:
                parts.append(_lead_head(lead))
                last_lead, last_country = lead, object()
            if (p.get("country") or "") != last_country:
                parts.append(f"<h3>{E(p.get('country') or '(no country)')}</h3>")
                last_country = p.get("country") or ""
        col = CAT.get(p.get("category", ""), "#455A64")
        b = [f'<div class="proj"><div class="ph">{E(str(p.get("sr", "")))}. {E(p["name"])}</div>',
             f'<div class="pm"><span class="tag" style="color:{col};font-weight:700">{E(p.get("category", ""))}</span>'
             f'<span class="tag">{E(p.get("country", "") or "-")}</span><span class="tag">{E(p.get("sector", "") or "-")}</span>'
             f'<span class="tag">Lead: {E(lead or "unassigned")}</span><span class="tag">PM: {E(pj["pm_eff"])}</span>'
             f'<span class="tag">Stage: {E(pj["stage"])}</span><span class="tag">Priority: {E(pj["priority"])}</span>'
             + (f'<span class="tag">Next review: {E(pj["next_review"])}</span>' if pj.get("next_review") else "") + '</div>']
        if pj.get("summary"):
            b.append(f'<div class="sum">{E(pj["summary"])}</div>')
        if sections.get("ext"):
            e = it.get("ext")
            b.append('<div class="sec">Internal status (from the team status file)</div>')
            if not e or e.get("none"):
                b.append('<div class="none">no data on this project in the status file</div>')
            else:
                lab = {"high": "match", "possible": "POSSIBLE match - verify", "linked": "linked"}.get(e["conf"], "")
                b.append(f'<div class="pm"><span class="tag">{E(e["file"])}</span><span class="tag">{E(e["sheet"])} - {lab}</span>'
                         + "".join(f'<span class="tag" style="font-weight:700">{E(v.splitlines()[0])}</span>' for v in (e["stage"], e["class"]) if v) + '</div>')
                if e["next"]:
                    b.append(f'<div class="sum" style="border-left-color:#F9A825;background:#FFF8DC;font-style:normal"><b>Next steps:</b> {E(e["next"]).replace(chr(10), "<br>")}</div>')
                if e["parties"] or e["banks"]:
                    rows = "".join(f"<tr><td style='width:22%;{'color:#B71C1C;font-weight:700' if p['kind'] == 'Bank / lender' else 'font-weight:600'}'>{E(p['role'])}</td>"
                                   f"<td>{E(p['name'])}</td><td>{E(' - '.join(v for v in (p.get('status'), p.get('notes')) if v))}</td></tr>" for p in e["parties"])
                    known = " ".join(p["name"].lower() for p in e["parties"])
                    more = [x for x in e["banks"] if x.lower() not in known]
                    if more:
                        rows += f"<tr><td style='color:#B71C1C;font-weight:700'>Financiers mentioned</td><td colspan='2'>{E(', '.join(more))}</td></tr>"
                    b.append(f"<table><tr><th>Partner / bank</th><th>Name</th><th>Status</th></tr>{rows}</table>")
                for mo in e.get("more", []):
                    nx = (mo["next"] or "").replace(chr(10), " ")
                    b.append(f'<div class="pm"><b>Also in the file:</b> {E(mo["file"])} ({E(mo["sheet"])})'
                             + (f" - {E(mo['stage'])}" if mo["stage"] else "") + (f" - <i>{E(nx[:220])}{'...' if len(nx) > 220 else ''}</i>" if nx else "") + "</div>")
        if sections.get("req"):
            rq = [r for r in it["reqs"] if show_closed or r["status"] not in T.CLOSED_REQ]
            b.append('<div class="sec">What is needed</div>')
            b.append("<table><tr><th style='width:16%'>Needed</th><th>Detail</th><th style='width:12%'>Status</th></tr>" +
                     "".join(f"<tr><td>{E(r['kind'])}</td><td>{E(r['detail'])}</td><td>{E(r['status'])}</td></tr>" for r in rq) + "</table>"
                     if rq else '<div class="none">nothing recorded</div>')
        if sections.get("cmt"):
            b.append('<div class="sec">Comments from discussions</div>')
            cm = it["cmts"]
            b.append("<table><tr><th style='width:11%'>Date</th><th style='width:9%'>By</th><th>Comment</th></tr>" +
                     "".join(f"<tr><td class='nw'>{E(c['day'] or '')}</td><td>{E(c['by'])}</td><td>{E(c['text']).replace(chr(10), '<br>')}</td></tr>" for c in cm) + "</table>"
                     if cm else '<div class="none">no comments yet</div>')
        if sections.get("act"):
            ac = [a for a in it["acts"] if show_closed or not a["done"]]
            b.append('<div class="sec">Actions</div>')
            rows = []
            for a in ac:
                cls = "done" if a["done"] else ("over" if a["due"] and a["due"] < td else "")
                rows.append(f"<tr><td class='{cls}'>{'&#10003; ' if a['done'] else '&#9744; '}{E(a['text'])}</td><td>{E(a['owner'])}</td><td class='{cls}'>{E(a['due'])}</td></tr>")
            b.append("<table><tr><th>Action</th><th style='width:14%'>Owner</th><th style='width:11%'>Due</th></tr>" + "".join(rows) + "</table>"
                     if rows else '<div class="none">no open actions</div>')
        if sections.get("log"):
            hs = T.history(p["id"], 60)
            b.append('<div class="sec">Change history</div>')
            b.append("<table><tr><th style='width:15%'>When</th><th style='width:9%'>Who</th><th>What</th></tr>" +
                     "".join(f"<tr><td class='nw'>{E(h['ts'])}</td><td>{E(h['user'])}</td><td>{E(fmt_event(h))}</td></tr>" for h in hs) + "</table>"
                     if hs else '<div class="none">no history</div>')
        b.append("</div>")
        parts.append("".join(b))
    return _page(title, meta, "".join(parts), _css(paper, landscape, font_pt), auto_print)


# --------------------------------------------------------------------------- 2. weekly review
def fmt_event(h: dict) -> str:
    a, f, o, n, note = h["action"], h["field"], h["old"], h["new"], h["note"]
    if a == "Comment added":
        return f"Comment ({f}): {n}"
    if a == "Requirement added":
        return f"Need added - {f}: {note or '-'}"
    if a == "Requirement changed":
        return f"Need changed - {f}: {o or '-'} → {n or '-'}"
    if a == "Requirement deleted":
        return f"Need removed - {f}: {o}"
    if a == "Action added":
        return f"Action added: {n}" + (f" (owner {f})" if f else "") + (f", due {note}" if note else "")
    if a in ("Action done", "Action reopened", "Action deleted", "Action changed"):
        return f"{a}: {n or o}"
    if a == "Updated":
        return f"{f.replace('_', ' ').capitalize()}: {o or '-'} → {n or '-'}"
    if a == "Reviewed":
        return "Reviewed" + (f" ({note})" if note else "")
    s = a + (f": {f}" if f else "")
    if o or n:
        s += f" ({o or '-'} → {n or '-'})"
    return s + (f" [{note}]" if note else "")


def build_weekly(items: List[dict], since: str, title: str, meta: List[str], paper: str, landscape: bool, font_pt: float,
                 auto_print: bool) -> str:
    keys = [it["p"]["id"] for it in items]
    ev: Dict[str, List[dict]] = {}
    for h in T.changes_since(since, keys):
        ev.setdefault(h["key"], []).append(h)
    td = T.today()
    parts: List[str] = []
    leads = []
    for it in items:
        if it["lead"] not in leads:
            leads.append(it["lead"])
    for lead in leads:
        its = [it for it in items if it["lead"] == lead]
        touched = [it for it in its if ev.get(it["p"]["id"])]
        allev = [h for it in its for h in ev.get(it["p"]["id"], [])]
        cnt = lambda act: sum(1 for h in allev if h["action"] == act)  # noqa: E731
        parts.append(_lead_head(lead))
        parts.append("".join(f'<span class="kpi"><b>{n}</b> {lbl}</span>' for n, lbl in (
            (len(its), "projects"), (len(touched), "with activity"), (cnt("Comment added"), "comments"), (cnt("Requirement added"), "needs added"),
            (cnt("Action added"), "actions added"), (cnt("Action done"), "actions done"), (cnt("Reviewed"), "reviews"))))
        if not touched:
            parts.append('<div class="none">no activity on these projects in this period</div>')
        for it in touched:
            p = it["p"]
            rows = "".join(f"<tr><td class='nw' style='width:13%'>{E(h['ts'][5:16])}</td><td style='width:9%'>{E(h['user'])}</td><td>{E(fmt_event(h))}</td></tr>"
                           for h in ev[p["id"]])
            parts.append(f'<div class="proj"><div class="ph">{E(str(p.get("sr", "")))}. {E(p["name"])} '
                         f'<span class="tag">{E(p.get("country", "") or "-")}</span><span class="tag">Stage: {E(it["proj"]["stage"])}</span></div>'
                         f"<table>{rows}</table></div>")
        quiet = len(its) - len(touched)
        if quiet:
            parts.append(f'<div class="none">{quiet} project(s) without activity.</div>')
        # still open
        rq = [(it["p"], r) for it in its for r in it["reqs"] if r["status"] not in T.CLOSED_REQ]
        if rq:
            parts.append('<div class="sec">Needs still open</div><table><tr><th style="width:30%">Project</th><th style="width:14%">Needed</th><th>Detail</th><th style="width:11%">Status</th></tr>' +
                         "".join(f"<tr><td>{E(p['name'])}</td><td>{E(r['kind'])}</td><td>{E(r['detail'])}</td><td>{E(r['status'])}</td></tr>" for p, r in rq) + "</table>")
        ac = [(it["p"], a) for it in its for a in it["acts"] if not a["done"]]
        if ac:
            ac.sort(key=lambda t: t[1]["due"] or "9999")
            parts.append('<div class="sec">Actions still open</div><table><tr><th style="width:30%">Project</th><th>Action</th><th style="width:12%">Owner</th><th style="width:11%">Due</th></tr>' +
                         "".join(f"<tr><td>{E(p['name'])}</td><td>{E(a['text'])}</td><td>{E(a['owner'])}</td>"
                                 f"<td class='{'over' if a['due'] and a['due'] < td else ''}'>{E(a['due'])}</td></tr>" for p, a in ac) + "</table>")
    return _page(title, meta + [f"Changes from {since} to {T.today()}"], "".join(parts), _css(paper, landscape, font_pt), auto_print)


# --------------------------------------------------------------------------- 3. action list by owner
def build_actions(items: List[dict], title: str, meta: List[str], paper: str, landscape: bool, font_pt: float, auto_print: bool,
                  include_done: bool) -> str:
    td = T.today()
    rows: List[tuple] = []
    for it in items:
        for a in it["acts"]:
            if include_done or not a["done"]:
                rows.append((it["p"], it["lead"], a))
    by_owner: Dict[str, list] = {}
    for p, lead, a in sorted(rows, key=lambda t: (t[2]["done"], t[2]["due"] or "9999-99-99")):
        by_owner.setdefault(a["owner"] or "(no owner)", []).append((p, lead, a))
    parts = []
    for owner in sorted(by_owner, key=lambda o: (o == "(no owner)", o.lower())):
        lst = by_owner[owner]
        over = sum(1 for _, _, a in lst if not a["done"] and a["due"] and a["due"] < td)
        parts.append(f"<h2>{E(owner)} &nbsp;<span style='font-weight:400'>{len(lst)} action(s)" + (f", {over} overdue" if over else "") + "</span></h2>")
        parts.append('<table><tr><th style="width:3%"></th><th>Action</th><th style="width:30%">Project</th><th style="width:6%">Lead</th><th style="width:11%">Due</th></tr>' +
                     "".join(f"<tr><td>{'&#10003;' if a['done'] else '&#9744;'}</td><td class='{'done' if a['done'] else ''}'>{E(a['text'])}</td><td>{E(p['name'])}</td>"
                             f"<td>{E(lead)}</td><td class='{'over' if (not a['done'] and a['due'] and a['due'] < td) else ''}'>{E(a['due'])}</td></tr>" for p, lead, a in lst) + "</table>")
    if not parts:
        parts.append('<div class="none">no open actions in the current view</div>')
    return _page(title, meta, "".join(parts), _css(paper, landscape, font_pt), auto_print)


# --------------------------------------------------------------------------- dialog
class ReportDialog(tk.Toplevel):
    """provider(): -> (items, projects, meta_lines)  for the rows currently shown in the Desk."""

    def __init__(self, parent, provider: Callable[[], tuple], lead_label: str = "", has_ext: bool = False):
        super().__init__(parent)
        self.provider = provider
        self.lead_label = lead_label
        self.title("Print / PDF / Excel - Project Desk")
        self.transient(parent)
        self.grab_set()
        f = tk.Frame(self, padx=16, pady=12)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Take what you see in the Desk with you - the projects currently shown (your filters apply).",
                 font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, columnspan=4, sticky="w")
        self.kind = tk.StringVar(value="sheet")
        kinds = (("sheet", "Discussion sheet", "per project: needs, comments, actions - to take into a meeting"),
                 ("weekly", "Weekly review", "what changed since a date, plus what is still open - per lead"),
                 ("actions", "Action list", "all actions by owner, overdue first"))
        for i, (v, t, d) in enumerate(kinds):
            tk.Radiobutton(f, text=t, value=v, variable=self.kind, command=self._kind, font=("Segoe UI", 10, "bold")).grid(row=1 + i, column=0, sticky="w", pady=(6 if i == 0 else 0, 0))
            tk.Label(f, text=d, fg="#546E7A").grid(row=1 + i, column=1, columnspan=3, sticky="w", pady=(6 if i == 0 else 0, 0))
        self.opts = tk.Frame(f)
        self.opts.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.v = {k: tk.BooleanVar(value=on) for k, on in (("req", True), ("cmt", True), ("act", True), ("log", False), ("ext", has_ext))}
        self.sec_cbs = []
        for i, (k, t) in enumerate((("req", "What is needed"), ("cmt", "Comments"), ("act", "Actions"), ("log", "Change history"))
                                   + ((("ext", "Status from file"),) if has_ext else ())):
            cb = ttk.Checkbutton(self.opts, text=t, variable=self.v[k])
            cb.grid(row=0, column=i, padx=(0, 14))
            self.sec_cbs.append(cb)
        self.closed = tk.BooleanVar(value=False)
        self.cb_closed = ttk.Checkbutton(self.opts, text="also finished / matched items", variable=self.closed)
        self.cb_closed.grid(row=1, column=0, columnspan=3, sticky="w")
        self.group = tk.BooleanVar(value=True)
        self.cb_group = ttk.Checkbutton(self.opts, text="group by lead, then country", variable=self.group)
        self.cb_group.grid(row=2, column=0, columnspan=3, sticky="w")
        self.since_row = tk.Frame(f)
        self.since_row.grid(row=5, column=0, columnspan=4, sticky="w")
        tk.Label(self.since_row, text="Changes since:").pack(side="left")
        self.since = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        ttk.Entry(self.since_row, textvariable=self.since, width=12).pack(side="left", padx=6)
        for lbl, d in (("yesterday", 1), ("7 days", 7), ("14 days", 14), ("30 days", 30)):
            ttk.Button(self.since_row, text=lbl, width=9, command=lambda d=d: self.since.set((datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d"))).pack(side="left", padx=2)
        tk.Label(f, text="Paper:").grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.paper = tk.StringVar(value="A4")
        ttk.Combobox(f, textvariable=self.paper, values=list(pr.PAPERS), state="readonly", width=8).grid(row=6, column=1, sticky="w", pady=(10, 0))
        self.orient = tk.StringVar(value="Portrait")
        ttk.Combobox(f, textvariable=self.orient, values=["Portrait", "Landscape"], state="readonly", width=10).grid(row=6, column=2, sticky="w", pady=(10, 0))
        self.size = tk.StringVar(value="Normal")
        ttk.Combobox(f, textvariable=self.size, values=list(pr.FONT), state="readonly", width=8).grid(row=6, column=3, sticky="w", pady=(10, 0))
        tk.Label(f, text="⚠ Internal: contains comments and sources - do not send it to clients.", fg="#C62828",
                 font=("Segoe UI", 9, "bold")).grid(row=7, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.msg = tk.Label(f, text="", anchor="w", wraplength=560, justify="left")
        self.msg.grid(row=8, column=0, columnspan=4, sticky="w")
        b = tk.Frame(f)
        b.grid(row=9, column=0, columnspan=4, sticky="e", pady=(8, 0))
        ttk.Button(b, text="Close", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(b, text="Excel", command=lambda: self.go("xlsx")).pack(side="right", padx=4)
        ttk.Button(b, text="Save as PDF", command=lambda: self.go("pdf")).pack(side="right", padx=4)
        tk.Button(b, text="Print…", command=lambda: self.go("print"), bg="#1565C0", fg="white", relief="flat", padx=16, pady=3,
                  font=("Segoe UI", 10, "bold")).pack(side="right", padx=4)
        self._kind()

    def _kind(self):
        k = self.kind.get()
        st = lambda on: "normal" if on else "disabled"  # noqa: E731
        for cb in self.sec_cbs + [self.cb_group]:
            cb.configure(state=st(k == "sheet"))
        self.cb_closed.configure(state=st(k in ("sheet", "actions")))
        for w in self.since_row.winfo_children():
            try:
                w.configure(state=st(k == "weekly"))
            except tk.TclError:
                pass
        self.orient.set("Landscape" if k == "actions" else "Portrait")

    def go(self, kind: str):
        self.msg.configure(text="", fg="#C62828")
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            items, projects, meta = self.provider()
            if not items:
                raise core.DeckError("There are no projects in the current view.")
            rtype = self.kind.get()
            since = self.since.get().strip()
            if rtype == "weekly":
                try:
                    datetime.strptime(since, "%Y-%m-%d")
                except ValueError:
                    raise core.DeckError("Write the 'changes since' date as YYYY-MM-DD, e.g. 2026-10-20.")
            meta = list(meta) + [f"{len(items)} project(s)  ·  printed {datetime.now():%d %b %Y, %H:%M}  ·  by {T.get_user()}"]
            title = {"sheet": "Project Desk - discussion sheet", "weekly": "Project Desk - weekly review", "actions": "Project Desk - action list"}[rtype]
            if self.lead_label:
                title += f" - {self.lead_label}"
            if kind == "xlsx":
                out = T.export_workbook(pr.PRINT_DIR / f"Desk_{rtype}_{datetime.now():%Y%m%d_%H%M%S}.xlsx", projects, scoped=True,
                                        since=since if rtype == "weekly" else "")
                pr.open_file(out)
                self.msg.configure(text=f"Saved: {out}", fg="#2E7D32")
                return
            land, fp, ap = self.orient.get() == "Landscape", pr.FONT[self.size.get()], kind == "print"
            if rtype == "sheet":
                doc = build_report(items, {k: v.get() for k, v in self.v.items()}, title, meta, self.group.get(), self.paper.get(), land, fp, ap, self.closed.get())
            elif rtype == "weekly":
                doc = build_weekly(items, since, title, meta, self.paper.get(), land, fp, ap)
            else:
                doc = build_actions(items, title, meta, self.paper.get(), land, fp, ap, self.closed.get())
            path = pr.write_html("Desk_" + rtype, doc)
            if kind == "print":
                pr.open_file(path)
                self.msg.configure(text="Opened in your browser - choose your printer in the print window.", fg="#2E7D32")
            else:
                out = pr.to_pdf(path)
                pr.open_file(out)
                self.msg.configure(text=f"Saved: {out}", fg="#2E7D32")
        except core.DeckError as exc:
            self.msg.configure(text=str(exc))
        finally:
            self.configure(cursor="")
