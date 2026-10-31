#!/usr/bin/env python3
"""Blend Hub - print centre documents (PDF via Edge/Chrome headless). One document per question the team asks:

  overview   one-page-ish management summary (portrait)
  country    pipeline by country, optional transaction list under each (landscape)
  sector     pipeline by sector, same (landscape)
  register   transaction register, compact or detailed, grouped, numbered (landscape)
  discuss    owner meeting sheet: a card per transaction with room to write the decision (portrait)
  actions    action tracker by owner with tick boxes (portrait)
  parties    counterparty map: every EPC / bank / ECA / investor / insurer and where it is mapped (landscape)
  txn        one-pager per transaction (portrait)
  pack       cover + contents + all of the above in one PDF
"""
from __future__ import annotations

import base64
import html
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import hubdb as H
import hubreport as R

NAVY, RED, AMBER, MUTE = "#1B2F5B", "#D81F26", "#F4A21E", "#6B7690"
STC = {"Tie-up done": "#17935F", "P1": "#2C6BED", "P2": "#7A4FE0", "Preliminary": "#C27A06", "On hold": "#6B7690"}
HOT = ("Tie-up done", "P1", "P2")
TYPES = R.TYPES
TYPE_PLURAL = {"EPC": "EPCs", "Bank / Lender": "Banks / Lenders", "ECA": "ECAs", "Investor": "Investors", "Insurer": "Insurers"}
STATE_MARK = {"Yes": ("✔", "#17935F"), "In progress": ("◐", "#C27A06"), "No": ("✖", "#D81F26"), "N.A.": ("–", "#6B7690"), "": ("○", "#B8C0D0")}

KINDS = {
    "overview": ("Pipeline overview", "Management summary: totals, value, status, owners, top countries and sectors, what needs attention.", "portrait"),
    "country": ("By country", "One row per country with transaction counts by status and approximate value.", "land"),
    "sector": ("By sector", "One row per sector with transaction counts by status and approximate value.", "land"),
    "register": ("Transaction register", "Every transaction with status, value and shortlisted EPCs / banks / ECAs. Compact or detailed.", "land"),
    "discuss": ("Owner discussion sheet", "A card per transaction, grouped by owner, with comments, actions and space to write the decision.", "portrait"),
    "actions": ("Action tracker", "Open actions by owner, overdue first, with a tick box for each.", "portrait"),
    "sources": ("By source", "Who introduced what: transactions, status and value per source (introducer).", "land"),
    "decks": ("Deck project list", "The projects in the EPC or Investor base deck: category, version, country, sector, model, source.", "land"),
    "bosses": ("Owners by country", "Which owner leads which country, with transactions and value.", "portrait"),
    "log": ("Change log", "Who changed what in the last days - for audit and catching up.", "land"),
    "parties": ("Counterparty map", "Each EPC, bank, ECA, investor and insurer with the transactions it is mapped to.", "land"),
    "milestones": ("Milestone tracker", "Meeting with ministry / owner, LoI / EoI, information, EPC mapping and review - per transaction, with dates and comments.", "land"),
    "txn": ("Transaction one-pager", "Full profile of one transaction: facts, readiness, counterparties, discussion, actions.", "portrait"),
    "pack": ("Complete pack", "Cover, contents and every section above in one PDF - for a full review.", "portrait"),
}

_LOGO = None

GROUP_COLS = [("n", "Transactions", 1), ("status", "Count per status", 1), ("value", "Approx. value", 1), ("bar", "Value bar", 1), ("hot", "Tie-up / P1 / P2 value", 1),
              ("given", "Value given (x of y)", 1), ("ep", "With a shortlisted EPC", 1), ("boss", "Owner(s)", 1),
              ("ms", "Milestones: meetings held, LoI / EoI sent, info, EPC, proceed", 1)]
COLS = {
    "overview": [("kpis", "Key figures", 1), ("status", "By status", 1), ("boss", "By owner", 1), ("top", "Top countries and sectors", 1), ("hot", "Tie-up / P1 / P2 list", 1), ("overdue", "Overdue actions", 1)],
    "country": GROUP_COLS, "sector": GROUP_COLS, "sources": GROUP_COLS,
    "register": [("sr", "Sr. number", 1), ("sub", "Country · sector · model under the name", 1), ("boss", "Owner", 1), ("status", "Status", 1), ("client", "Client type", 1), ("value", "Approx. value", 1),
                 ("source", "Source", 0), ("meeting", "Meeting with ministry / owner", 1), ("loi", "LoI / EoI", 1), ("info", "Information · model · owner financials", 0),
                 ("intake", "Received · data · review dates", 0), ("review", "Review outcome", 0), ("mgmt", "Management comment", 0), ("epc", "EPCs", 1), ("bank", "Banks / Lenders", 1), ("eca", "ECAs", 1), ("investor", "Investors", 1), ("insurer", "Insurers", 1),
                 ("ready", "Readiness", 1), ("facts", "FSR · land · concession", 0), ("tasks", "Next tasks (owner · due)", 1), ("comment", "Last comment", 0), ("next", "Next steps", 0)],
    "discuss": [("meta", "Country, sector, model, readiness line", 1), ("facts", "FSR · land · concession", 1), ("parties", "Shortlisted EPCs / banks / ECAs…", 1), ("next", "Next steps", 1),
                ("comments", "Comments", 1), ("actions", "Open actions", 1), ("decide", "Box to write the decision", 1)],
    "actions": [("tick", "Tick box", 1), ("txn", "Transaction", 1), ("boss", "Owner", 1), ("due", "Due date", 1)],
    "parties": [("notes", "Notes under the name", 1), ("mapped", "Mapped", 1), ("short", "Shortlisted +", 1), ("appointed", "Appointed", 1), ("txns", "List of transactions", 1)],
    "milestones": [("summary", "Summary cards per milestone", 1), ("sub", "Country · sector under the name", 1), ("boss", "Owner", 1), ("status", "Status", 1),
                   ("meeting", "Meeting with ministry / owner", 1), ("loi", "LoI / EoI", 1), ("info", "Documents and information held (12 columns)", 1), ("intake", "Received · data · review dates", 1),
                   ("review", "Review outcome and notes", 1), ("epc", "Shortlisted EPCs", 0), ("mgmt", "Latest management comment", 1), ("notes", "Meeting / LoI / EoI comments", 0)],
    "txn": [("track", "Tracker (meeting, LoI / EoI, information, intake, review)", 1), ("facts", "Facts grid", 1), ("summary", "Summary", 1), ("next", "Next steps", 1), ("ready", "Readiness checklist", 1), ("parties", "Counterparties", 1), ("discuss", "Discussion", 1), ("actions", "Actions", 1)],
    "bosses": [("n", "Transactions", 1), ("active", "Active", 1), ("hot", "Tie-up / P1 / P2", 1), ("value", "Approx. value", 1)],
    "decks": [("unnamed", "Unnamed title", 1), ("category", "Category", 1), ("version", "Version", 1), ("country", "Country", 1), ("sector", "Sector", 1), ("model", "Model", 1),
              ("source", "Source", 1), ("value", "Value slide", 1), ("status", "Status", 1)],
    "log": [("who", "Who", 1), ("txn", "Transaction", 1), ("what", "What", 1), ("detail", "Detail", 1)],
}


def want(c, kind: str, cid: str) -> bool:
    """Is this column / section switched on? 'cols' in the options (from the Print centre) wins; otherwise the defaults."""
    cl = c.opts.get("cols")
    if cl is not None:
        return cid in cl
    if kind == "register" and cid in ("facts", "comment", "next") and c.opts.get("density") == "detailed":
        return True
    return any(i == cid and d for i, _, d in COLS.get(kind, []))


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def parse_val(v):
    return H.value_to_eur(v)


def money(n) -> str:
    if n is None or n <= 0:
        return "—"
    return f"€{n / 1000:.{1 if n >= 10000 else 2}f} bn" if n >= 1000 else f"€{round(n):,} mn"


def logo() -> str:
    global _LOGO
    if _LOGO is None:
        p = Path(__file__).parent / "hubweb" / "logo.png"
        _LOGO = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else ""
    return _LOGO


def chip(status: str) -> str:
    return f'<span class="chip" style="background:{STC.get(status, "#999")}">{e(status)}</span>'


# --------------------------------------------------------------------------- data
class Ctx:
    def __init__(self, snap: dict, ids: List[int], opts: dict):
        self.snap, self.opts = snap, opts
        self.ix = R._index(snap)
        by_id = {t["id"]: {**t, "vn": parse_val(t["value"])} for t in snap["txns"]}
        order = {s: i for i, s in enumerate(H.STATUSES)}
        self.ts = sorted((by_id[i] for i in ids if i in by_id), key=lambda t: (order.get(t["status"], 9), -(t["vn"] or 0), t["name"].lower()))
        self.ids = {t["id"] for t in self.ts}
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.acts = [a for a in snap["actions"] if a["txn_id"] in self.ids]
        self.by_id = by_id

    def short(self, t, ty):
        return [l for l in self.ix["L"].get(t["id"], []) if l["p"]["type"] == ty and l["status"] in H.SHORTLISTED_UP]

    def overdue(self, a):
        return (not a["done"]) and a["due"] and a["due"] < self.today

    def doc_title(self):
        return self.opts.get("title") or "Blend - pipeline"


def total(ts):
    return sum(t["vn"] or 0 for t in ts)


# --------------------------------------------------------------------------- shared pieces
def header(c: Ctx, title: str, sub: str = "") -> str:
    lines = "".join(f"<div>{e(x)}</div>" for x in c.opts.get("filters", []) if x)
    return (f'<div class="hdr"><img src="{logo()}"><div class="ht"><h1>{e(title)}</h1><div class="sub">{e(sub)}</div></div>'
            f'<div class="hr">{datetime.now():%d %b %Y}<br><b>INTERNAL</b><br>not for clients</div></div><div class="bar"></div>'
            + (f'<div class="scope">{lines}</div>' if lines else ""))


def kpi_strip(items) -> str:
    return '<div class="kpis">' + "".join(f'<div class="k"><b>{e(v)}</b><span>{e(l)}</span></div>' for l, v in items) + "</div>"


def vbar(n, mx, color=NAVY) -> str:
    return f'<span class="vb"><i style="width:{round((n or 0) / mx * 100) if mx else 0}%;background:{color}"></i></span>'


def group_rows(c: Ctx, keyf) -> List[dict]:
    g: Dict[str, dict] = {}
    pairs = []
    for t in c.ts:
        ks = keyf(t)
        pairs += [(k, t) for k in (ks if isinstance(ks, list) else [ks])]
    for k, t in pairs:
        x = g.setdefault(k, {"k": k, "n": 0, "st": {}, "v": 0.0, "nv": 0, "hotv": 0.0, "ep": 0, "od": 0, "boss": {}, "ts": []})
        x["n"] += 1
        x["ts"].append(t)
        x["st"][t["status"]] = x["st"].get(t["status"], 0) + 1
        if t["vn"] is not None:
            x["v"] += t["vn"]
            x["nv"] += 1
            if t["status"] in HOT:
                x["hotv"] += t["vn"]
        if c.short(t, "EPC"):
            x["ep"] += 1
        x["od"] += sum(1 for a in c.ix["A"].get(t["id"], []) if c.overdue(a))
        b = t["lead"] or "–"
        x["boss"][b] = x["boss"].get(b, 0) + 1
    for x in g.values():
        x["ms"] = ms_counts(c, x["ts"])
    return sorted(g.values(), key=lambda x: (-x["v"], -x["n"], x["k"].lower()))


def top_table(rows, label, limit=10) -> str:
    mx = max([x["v"] for x in rows] + [1])
    out = f'<table><thead><tr><th>{label}</th><th class="n">Txns</th><th class="n">Tie-up / P1 / P2</th><th class="n">Approx. value</th><th></th></tr></thead><tbody>'
    for x in rows[:limit]:
        hot = sum(x["st"].get(s, 0) for s in HOT)
        out += f'<tr><td>{e(x["k"])}</td><td class="n">{x["n"]}</td><td class="n">{hot or "·"}</td><td class="n"><b>{money(x["v"])}</b></td><td class="w">{vbar(x["v"], mx)}</td></tr>'
    if len(rows) > limit:
        rest = rows[limit:]
        out += f'<tr class="mute"><td>+ {len(rest)} more</td><td class="n">{sum(x["n"] for x in rest)}</td><td></td><td class="n">{money(sum(x["v"] for x in rest))}</td><td></td></tr>'
    return out + "</tbody></table>"


NOTE_VALUE = ('<div class="note">Values are approximate and in USD: typed amounts are converted (EUR × 1.08), a range uses its midpoint, and transactions '
              'with no value are not counted - so totals are a floor, not a forecast.</div>')


# --------------------------------------------------------------------------- 1 overview
def sec_overview(c: Ctx) -> str:
    ts = c.ts
    act = [t for t in ts if t["active"]]
    opens = [a for a in c.acts if not a["done"]]
    od = [a for a in opens if c.overdue(a)]
    nv = sum(1 for t in ts if t["vn"] is not None)
    h = header(c, "Pipeline overview", f"{len(ts)} transactions · {len(act)} active · {nv} with a value")
    W = lambda i: want(c, "overview", i)
    _s = len(h)
    h += kpi_strip([("Transactions", len(ts)), ("Approx. value", money(total(ts))), ("Tie-up / P1 / P2 value", money(total([t for t in ts if t["status"] in HOT]))),
                    ("With a shortlisted EPC", sum(1 for t in ts if c.short(t, "EPC"))), ("Open actions", len(opens)), ("Overdue", len(od))])
    if not W("kpis"):
        h = h[:_s]
    _s = len(h)
    mx = max([sum(t["vn"] or 0 for t in ts if t["status"] == s) for s in H.STATUSES] + [1])
    h += '<h2>By internal status</h2><table><thead><tr><th>Status</th><th class="n">Transactions</th><th class="n">Approx. value</th><th></th></tr></thead><tbody>'
    for s in H.STATUSES:
        sub = [t for t in ts if t["status"] == s]
        h += f'<tr><td>{chip(s)}</td><td class="n">{len(sub)}</td><td class="n"><b>{money(total(sub))}</b></td><td class="w">{vbar(total(sub), mx, STC[s])}</td></tr>'
    h += "</tbody></table>"
    if not W("status"):
        h = h[:_s]
    _s = len(h)
    h += '<h2>By boss (active transactions)</h2><table><thead><tr><th>Owner</th><th class="n">Active</th><th class="n">Tie-up / P1 / P2</th><th class="n">Approx. value</th><th class="n">Open actions</th><th class="n">Overdue</th></tr></thead><tbody>'
    for b in ["RB", "JT", "SS", "Unassigned"]:
        sub = [t for t in act if (t["lead"] or "Unassigned") == b]
        ids = {t["id"] for t in sub}
        oa = [a for a in opens if a["txn_id"] in ids]
        h += (f'<tr><td><b>{b}</b></td><td class="n">{len(sub)}</td><td class="n">{sum(1 for t in sub if t["status"] in HOT) or "·"}</td><td class="n">{money(total(sub))}</td>'
              f'<td class="n">{len(oa) or "·"}</td><td class="n red">{sum(1 for a in oa if c.overdue(a)) or "·"}</td></tr>')
    h += "</tbody></table>"
    if not W("boss"):
        h = h[:_s]
    _s = len(h)
    h += '<div class="two"><div><h2>Top countries by value</h2>' + top_table(group_rows(c, lambda t: t["country"] or "(no country)"), "Country", 8) + \
         '</div><div><h2>Top sectors by value</h2>' + top_table(group_rows(c, lambda t: t["sector"] or "(none)"), "Sector", 8) + "</div></div>"
    if not W("top"):
        h = h[:_s]
    hot = sorted([t for t in ts if t["status"] in HOT], key=lambda t: -(t["vn"] or 0))[:10]
    if hot and W("hot"):
        h += '<h2>Tie-up / P1 / P2 transactions</h2><table><thead><tr><th>Transaction</th><th>Owner</th><th>Status</th><th class="n">Approx. value</th><th>Shortlisted EPCs</th></tr></thead><tbody>'
        for t in hot:
            h += (f'<tr><td><b>{e(t["name"])}</b><br><small>{e(t["country"])} · {e(t["sector"])}</small></td><td>{e(t["lead"])}</td><td>{chip(t["status"])}</td>'
                  f'<td class="n">{money(t["vn"])}</td><td>{e(", ".join(l["p"]["name"] for l in c.short(t, "EPC")) or "—")}</td></tr>')
        h += "</tbody></table>"
    if od and W("overdue"):
        h += '<h2>Overdue actions</h2><table><thead><tr><th>Action</th><th>Transaction</th><th>Owner</th><th>Due</th></tr></thead><tbody>'
        for a in sorted(od, key=lambda a: a["due"])[:10]:
            t = c.by_id[a["txn_id"]]
            h += f'<tr><td>{e(a["text"])}</td><td>{e(t["name"])}<br><small>{e(t["country"])}</small></td><td>{e(a["owner"] or "–")}</td><td class="red">{e(a["due"])}</td></tr>'
        h += "</tbody></table>"
    return f'<section class="pg portrait">{h}{NOTE_VALUE}</section>'


# --------------------------------------------------------------------------- 2/3 country + sector
def sec_group(c: Ctx, mode: str) -> str:
    keyf = {"country": lambda t: t["country"] or "(no country)", "sector": lambda t: t["sector"] or "(none)", "source": lambda t: split_src(t["introduced"])}[mode]
    rows = group_rows(c, keyf)
    label = mode.title()
    plural = {"country": "countries", "sector": "sectors", "source": "sources"}[mode]
    mx = max([x["v"] for x in rows] + [1])
    h = header(c, f"Pipeline by {mode}", f"{len(rows)} {plural} · {len(c.ts)} transactions · approx. value {money(total(c.ts))}" + (" · a transaction with two sources counts under both" if mode == "source" else ""))
    K = "sources" if mode == "source" else mode
    W = lambda i: want(c, K, i)
    h += f'<table class="big"><thead><tr><th>{label}</th>'
    if W("n"):
        h += '<th class="n">Txns</th>'
    if W("status"):
        h += "".join(f'<th class="n" style="color:{STC[s]}">{e(s)}</th>' for s in H.STATUSES)
    if W("value"):
        h += '<th class="n">Approx. value</th>'
    if W("bar"):
        h += "<th></th>"
    if W("hot"):
        h += '<th class="n">Tie-up / P1 / P2 value</th>'
    if W("given"):
        h += '<th class="n">Value given</th>'
    if W("ep"):
        h += '<th class="n">With shortlisted EPC</th>'
    if W("ms"):
        h += '<th class="n">Meetings held</th><th class="n">LoI / EoI sent</th><th class="n">Info recd</th><th class="n">EPC short-listed</th><th class="n">Proceed</th><th class="n">EPC not finalised</th>'
    if W("boss"):
        h += "<th>Owner</th>"
    h += "</tr></thead><tbody>"
    for x in rows:
        bosses = " ".join(f'<span class="boss">{e(b)}</span>' for b, _ in sorted(x["boss"].items(), key=lambda kv: -kv[1])) if mode == "country" else \
            " · ".join(f"{e(b)} {n}" for b, n in sorted(x["boss"].items(), key=lambda kv: -kv[1]))
        r = f'<tr><td><b>{e(x["k"])}</b></td>'
        if W("n"):
            r += f'<td class="n"><b>{x["n"]}</b></td>'
        if W("status"):
            r += "".join(f'<td class="n">{x["st"].get(s) or "<span class=z>·</span>"}</td>' for s in H.STATUSES)
        if W("value"):
            r += f'<td class="n"><b>{money(x["v"])}</b></td>'
        if W("bar"):
            r += f'<td class="w">{vbar(x["v"], mx)}</td>'
        if W("hot"):
            r += f'<td class="n">{money(x["hotv"])}</td>'
        if W("given"):
            r += f'<td class="n mute">{x["nv"]} of {x["n"]}</td>'
        if W("ep"):
            r += f'<td class="n">{x["ep"] or "·"}</td>'
        if W("ms"):
            r += "".join(f'<td class="n">{v or "<span class=z>·</span>"}</td>' for v in x["ms"])
        if W("boss"):
            r += f"<td>{bosses}</td>"
        h += r + "</tr>"
    r = f'<tr class="tot"><td>Total{" (distinct transactions)" if mode == "source" else ""}</td>'
    if W("n"):
        r += f'<td class="n">{len(c.ts)}</td>'
    if W("status"):
        r += "".join(f'<td class="n">{sum(1 for t in c.ts if t["status"] == s)}</td>' for s in H.STATUSES)
    if W("value"):
        r += f'<td class="n">{money(total(c.ts))}</td>'
    if W("bar"):
        r += "<td></td>"
    if W("hot"):
        r += f'<td class="n">{money(total([t for t in c.ts if t["status"] in HOT]))}</td>'
    if W("given"):
        r += f'<td class="n">{sum(1 for t in c.ts if t["vn"] is not None)} of {len(c.ts)}</td>'
    if W("ep"):
        r += f'<td class="n">{sum(x["ep"] for x in rows)}</td>'
    if W("ms"):
        r += "".join(f'<td class="n">{v}</td>' for v in ms_counts(c, c.ts))
    if W("boss"):
        r += "<td></td>"
    h += r + f"</tr></tbody></table>{NOTE_VALUE}"
    main = f'<section class="pg land">{h}</section>'
    if c.opts.get("detail"):
        out = ""
        for x in rows:
            body = (f'<div class="gh"><h2>{e(x["k"])}</h2><span>{x["n"]} transactions · {money(x["v"])}</span></div>'
                    '<table><thead><tr><th class="n">#</th><th>Transaction</th><th>Owner</th><th>Status</th><th>Client</th><th class="n">Approx. value</th><th>Shortlisted EPCs</th><th>Next steps</th></tr></thead><tbody>')
            for i, t in enumerate(sorted(x["ts"], key=lambda t: (H.STATUSES.index(t["status"]), -(t["vn"] or 0))), 1):
                other = t["sector"] if mode == "country" else (t["country"] + " · " + t["sector"] if mode == "source" else t["country"])
                body += (f'<tr class="{"" if t["active"] else "dim"}"><td class="n">{i}</td><td><b>{e(t["name"])}</b><br><small>{e(other)} {e(t["structure"])}</small></td><td>{e(t["lead"])}</td><td>{chip(t["status"])}</td>'
                         f'<td>{e(t["client_type"])}</td><td class="n">{money(t["vn"])}</td><td>{e(", ".join(l["p"]["name"] for l in c.short(t, "EPC")) or "—")}</td><td>{e((t["next_steps"] or "")[:160])}</td></tr>')
            out += f'<div class="gblock">{body}</tbody></table></div>'
        main += f'<section class="pg land flow">{out}</section>'
    return main


# --------------------------------------------------------------------------- 4 register
def sec_register(c: Ctx) -> str:
    o = c.opts
    group = o.get("group", "none")
    rows = R.rows_for(c.snap, [t["id"] for t in c.ts], group, o.get("numbering", "dynamic"))
    vn = {t["id"]: t["vn"] for t in c.ts}
    h = header(c, o.get("title") or "Transaction register", f"{len(c.ts)} transactions · approx. value {money(total(c.ts))}" + (f" · grouped by {R.GROUPS[group].lower()}" if group != "none" else ""))
    W = lambda i: want(c, "register", i)
    TY = {"epc": "EPC", "bank": "Bank / Lender", "eca": "ECA", "investor": "Investor", "insurer": "Insurer"}

    def name_cell(r, t):
        sub = (f'<br><small>{e(t["country"])} · {e(t["sector"])}{" · " + e(t["structure"]) if t["structure"] else ""}'
               f'{" · " + e(t["procurement"]) if t["procurement"] not in ("", "To confirm") else ""}</small>') if W("sub") else ""
        return f'<td><b>{e(t["name"])}</b>{sub}</td>'

    def facts_cell(r, t):
        f = "<br>".join(x for x in (("FSR: " + e(r["fsr"])) if r["fsr"] else "", ("Land: " + e(r["land"])) if r["land"] else "", ("Concession: " + e(r["conc"])) if r["conc"] else "") if x)
        return f"<td>{f or '—'}</td>"

    spec = [("sr", "Sr.", lambda r, t: f'<td class="n">{r["n"]}</td>'), ("name", "Transaction", name_cell), ("boss", "Owner", lambda r, t: f'<td>{e(t["lead"])}</td>'),
            ("status", "Status", lambda r, t: f'<td>{chip(t["status"])}</td>'), ("client", "Client", lambda r, t: f'<td>{e(t["client_type"])}</td>'),
            ("value", "Value", lambda r, t: f'<td class="n">{money(vn.get(t["id"]))}</td>'), ("source", "Source", lambda r, t: f'<td>{e(t["introduced"]) or "—"}</td>')]
    for k, ty in TY.items():
        spec.append((k, TYPE_PLURAL[ty], (lambda ty: lambda r, t: f'<td>{e(r["cells"][ty]) or "<span class=z>—</span>"}</td>')(ty)))
    spec = spec[:7] + [("meeting", "Meeting", lambda r, t: f"<td>{_meeting_txt(t)}</td>"), ("loi", "LoI / EoI", lambda r, t: f"<td>{_loi_txt(t)}</td>"), ("info", "Info · model · owner fin.", lambda r, t: f"<td>{_info_txt(c, t)}</td>"),
                       ("intake", "Intake", lambda r, t: f"<td>{_intake_txt(t)}</td>"), ("review", "Review", lambda r, t: f"<td>{_review_txt(t)}</td>"),
                       ("mgmt", "Management comment", lambda r, t: (lambda m: f'<td>{e(m["day"])}: {e(m["text"][:240])}</td>' if m else "<td>—</td>")(mgmt_comment(c, t)))] + spec[7:]
    def tasks_cell(r, t):
        acts = sorted([a for a in r["actions"] if not a["done"]], key=lambda a: (a["due"] or "9999", a["id"]))
        if not acts:
            return "<td>—</td>"
        td = datetime.now().strftime("%Y-%m-%d")
        return "<td>" + "<br>".join(f'• {e(a["text"][:90])} — <b>{e(a["owner"] or "no owner")}</b>' + (f' <span class="{"red" if a["due"] < td else ""}">{e(a["due"])}</span>' if a["due"] else "") for a in acts[:4]) + (f"<br><small>+{len(acts) - 4} more</small>" if len(acts) > 4 else "") + "</td>"

    spec += [("tasks", "Next tasks (owner · due)", tasks_cell), ("ready", "Ready", lambda r, t: f'<td class="n">{r["ready"]}</td>'), ("facts", "FSR · Land · Concession", facts_cell),
             ("comment", "Last comment", lambda r, t: f'<td>{e(r["last_comment"][:240]) or "—"}</td>'), ("next", "Next steps", lambda r, t: f'<td>{e((t["next_steps"] or "")[:240]) or "—"}</td>')]
    spec = [x for x in spec if x[0] == "name" or W(x[0])]
    h += "<table class='reg'><thead><tr>" + "".join(f"<th>{x[1]}</th>" for x in spec) + "</tr></thead><tbody>"
    ncol = len(spec)
    for r in rows:
        if "group" in r:
            sub = [t for t in c.ts if (t["lead"] or "Unassigned" if group == "lead" else t["country"] or "(no country)" if group == "country" else t["status"] if group == "status"
                                       else t["client_type"] if group == "client" else t["sector"] or "(no sector)") == r["group"]]
            h += f'<tr class="g"><td colspan="{ncol}">{e(r["group"])} <span>{r["count"]} · {money(total(sub))}</span></td></tr>'
            continue
        t = r["t"]
        h += f'<tr class="{"" if t["active"] else "dim"}">' + "".join(x[2](r, t) for x in spec) + "</tr>"
    return f'<section class="pg land">{h}</tbody></table>{NOTE_VALUE}</section>'


# --------------------------------------------------------------------------- 5 discuss
def sec_discuss(c: Ctx) -> str:
    o = c.opts
    n_cm = 99 if o.get("comments") == "all" else int(o.get("comments", 3) or 0)
    W = lambda i: want(c, "discuss", i)
    out = ""
    for boss in ["RB", "JT", "SS", "Unassigned"]:
        sub = [t for t in c.ts if (t["lead"] or "Unassigned") == boss]
        if not sub:
            continue
        h = header(c, f"Discussion sheet - {boss}", f"{len(sub)} transactions · approx. value {money(total(sub))} · PMs: {c.snap.get('pms', '')}")
        for i, t in enumerate(sub, 1):
            ix, tid = c.ix, t["id"]
            cm = sorted(ix["CM"].get(tid, []), key=lambda x: (x["day"], x["id"]), reverse=True)[:n_cm]
            ac = [a for a in ix["A"].get(tid, []) if not a["done"]]
            ck = ix["C"].get(tid, {})
            facts = " &nbsp;·&nbsp; ".join(f"<b>{lab}:</b> {e(R._fact(ix, tid, key)) or '<span class=z>not recorded</span>'}" for lab, key in
                                           (("FSR", "FSR (feasibility study)"), ("Land", "Land available"), ("Concession", "Concession agreement")))
            parties = " &nbsp;·&nbsp; ".join(f"<b>{TYPE_PLURAL[ty]}:</b> {e(R._cell(ix, tid, ty)) or '<span class=z>—</span>'}" for ty in TYPES)
            card = (f'<div class="dcard" style="--c:{STC.get(t["status"], "#999")}"><div class="dh"><b>{i}. {e(t["name"])}</b>{chip(t["status"])}<span class="ct">{e(t["client_type"])}</span>'
                    f'<span class="val">{money(t["vn"])}</span></div>')
            if W("meta"):
                card += (f'<div class="meta">{e(t["country"])} · {e(t["sector"])}{" · " + e(t["structure"]) if t["structure"] else ""}{" · " + e(t["procurement"]) if t["procurement"] not in ("", "To confirm") else ""}'
                         f' · readiness {R._ready(ix, tid)}{" · source " + e(t["introduced"]) if t["introduced"] else ""}</div>')
            if W("facts"):
                card += f'<div class="facts">{facts}</div>'
            if W("parties"):
                card += f'<div class="facts">{parties}</div>'
            if t["next_steps"] and W("next"):
                card += f'<div class="facts"><b>Next steps:</b> {e(t["next_steps"][:300])}</div>'
            if cm and W("comments"):
                card += '<div class="cms">' + "".join(f'<div><small>{e(x["day"])} · {e(x["by"])}</small> {_cm_line(x)}</div>' for x in cm) + "</div>"
            if ac and W("actions"):
                card += '<div class="acs">' + "".join(f'<div><span class="cb"></span>{e(a["text"])} <small>— {e(a["owner"] or "no owner")}{", due " + e(a["due"]) if a["due"] else ""}</small>'
                                                     f'{" <b class=red>OVERDUE</b>" if c.overdue(a) else ""}</div>' for a in ac) + "</div>"
            if W("decide"):
                card += '<div class="decide"><span>Decision / comment from discussion</span></div>'
            h += card + "</div>"
        out += f'<section class="pg portrait flow">{h}</section>'
    return out or f'<section class="pg portrait">{header(c, "Discussion sheet", "")}<p>No transactions in this selection.</p></section>'


# --------------------------------------------------------------------------- 6 actions
def sec_actions(c: Ctx) -> str:
    inc_done = c.opts.get("include_done", False)
    acts = [a for a in c.acts if inc_done or not a["done"]]
    opens = [a for a in acts if not a["done"]]
    h = header(c, "Action tracker", f"{len(opens)} open · {sum(1 for a in opens if c.overdue(a))} overdue")
    if not acts:
        return f'<section class="pg portrait">{h}<p>No open actions in this selection.</p></section>'
    W = lambda i: want(c, "actions", i)
    owners = sorted({a["owner"] or "(no owner)" for a in acts}, key=lambda s: (s == "(no owner)", s))
    for ow in owners:
        mine = sorted([a for a in acts if (a["owner"] or "(no owner)") == ow], key=lambda a: (a["done"], a["due"] or "9999", a["id"]))
        h += (f'<div class="gblock"><div class="gh"><h2>{e(ow)}</h2><span>{sum(1 for a in mine if not a["done"])} open</span></div><table><thead><tr>' + ("<th></th>" if W("tick") else "") +
              "<th>Action</th>" + ("<th>Transaction</th>" if W("txn") else "") + ("<th>Owner</th>" if W("boss") else "") + ("<th>Due</th>" if W("due") else "") + "</tr></thead><tbody>")
        for a in mine:
            t = c.by_id[a["txn_id"]]
            due = f'<b class="red">{e(a["due"])} · overdue</b>' if c.overdue(a) else e(a["due"] or "—")
            h += (f'<tr class="{"dim" if a["done"] else ""}">' + (f'<td><span class="cb {"on" if a["done"] else ""}"></span></td>' if W("tick") else "") + f'<td>{e(a["text"])}</td>' +
                  (f'<td>{e(t["name"])}<br><small>{e(t["country"])}</small></td>' if W("txn") else "") + (f'<td>{e(t["lead"])}</td>' if W("boss") else "") + (f"<td>{due}</td>" if W("due") else "") + "</tr>")
        h += "</tbody></table></div>"
    return f'<section class="pg portrait flow">{h}</section>'


# --------------------------------------------------------------------------- 7 parties
def sec_parties(c: Ctx) -> str:
    W = lambda i: want(c, "parties", i)
    h = header(c, "Counterparty map", "Every counterparty mapped to the selected transactions · bold = shortlisted or further")
    out = ""
    for ty in TYPES:
        rows = []
        for p in c.snap["parties"]:
            if p["type"] != ty:
                continue
            ls = [l for l in c.snap["links"] if l["party_id"] == p["id"] and l["txn_id"] in c.ids]
            if ls:
                rows.append((p, ls))
        if not rows:
            continue
        rows.sort(key=lambda x: (-sum(1 for l in x[1] if l["status"] in H.SHORTLISTED_UP), -len(x[1]), x[0]["name"].lower()))
        b = (f'<div class="gblock"><div class="gh"><h2>{TYPE_PLURAL[ty]}</h2><span>{len(rows)}</span></div><table><thead><tr><th>{ty}</th>' + ('<th class="n">Mapped</th>' if W("mapped") else "") +
             ('<th class="n">Shortlisted +</th>' if W("short") else "") + ('<th class="n">Appointed</th>' if W("appointed") else "") + ("<th>Transactions</th>" if W("txns") else "") + "</tr></thead><tbody>")
        for p, ls in rows:
            ls.sort(key=lambda l: (l["status"] not in H.SHORTLISTED_UP, c.by_id[l["txn_id"]]["name"].lower()))
            txt = "; ".join((f'<b>{e(c.by_id[l["txn_id"]]["name"][:48])}</b>' if l["status"] in H.SHORTLISTED_UP else e(c.by_id[l["txn_id"]]["name"][:48]))
                            + f' <small>({e(c.by_id[l["txn_id"]]["country"])}{", " + e(l["status"]) if l["status"] != "Shortlisted" else ""})</small>' for l in ls[:14])
            if len(ls) > 14:
                txt += f" <small>+ {len(ls) - 14} more</small>"
            b += (f'<tr><td><b>{e(p["name"])}</b>{"<br><small>" + e(p["notes"][:90]) + "</small>" if p["notes"] and W("notes") else ""}</td>' + (f'<td class="n">{len(ls)}</td>' if W("mapped") else "") +
                  (f'<td class="n">{sum(1 for l in ls if l["status"] in H.SHORTLISTED_UP) or "·"}</td>' if W("short") else "") +
                  (f'<td class="n">{sum(1 for l in ls if l["status"] == "Appointed") or "·"}</td>' if W("appointed") else "") + (f"<td>{txt}</td>" if W("txns") else "") + "</tr>")
        out += b + "</tbody></table></div>"
    return f'<section class="pg land flow">{h}{out or "<p>No counterparties are mapped to this selection yet.</p>"}</section>'


# --------------------------------------------------------------------------- 8 one-pager
def sec_txn(c: Ctx, t: dict) -> str:
    ix, tid = c.ix, t["id"]
    W = lambda i: want(c, "txn", i)
    h = header(c, t["name"], f'{t["country"]} · {t["sector"]}')
    kv = [("Status", chip(t["status"]) + ("" if t["active"] else " <small>parked</small>")), ("Owner", e(t["lead"] or "–")), ("Client type", e(t["client_type"])), ("Tender / negotiated", e(t["procurement"])),
          ("Model", e(t["structure"] or "—")), ("Approx. value", f'<b>{money(t["vn"])}</b>' + (f' <small>({e(t["value"][:40])})</small>' if t["value"] and not re.fullmatch(r"[\d.]+", str(t["value"])) else "")),
          ("Source", e(t["introduced"] or "—")), ("Readiness", R._ready(ix, tid)), ("Last reviewed", e(t["last_reviewed"] or "—")), ("Next review", e(t["next_review"] or "—"))]
    if W("facts"):
        h += '<div class="kvg">' + "".join(f'<div><span class="l">{k}</span>{v}</div>' for k, v in kv) + "</div>"
    if W("track"):
        h += sec_txn_track(c, t)
    if t["summary"] and W("summary"):
        h += f'<h2>Summary</h2><p class="txt">{e(t["summary"][:1400])}</p>'
    if t["next_steps"] and W("next"):
        h += f'<h2>Next steps</h2><p class="txt">{e(t["next_steps"][:900])}</p>'
    _s = len(h)
    ck = ix["C"].get(tid, {})
    h += f'<h2>Readiness checklist <small>{R._ready(ix, tid)}</small></h2><table class="chk"><tbody>'
    items = list(H.CHECK_ITEMS) + sorted(k for k in ck if k not in H.CHECK_ITEMS)  # + this project's own items
    for i in range(0, len(items), 2):
        h += "<tr>"
        for it in items[i:i + 2]:
            x = ck.get(it, {})
            m, col = STATE_MARK.get(x.get("state", ""), STATE_MARK[""])
            h += f'<td class="mk" style="color:{col}">{m}</td><td><b>{e(it)}</b>{": " + e(x.get("state")) if x.get("state") else ""}<br><small>{e(x.get("remark", ""))}</small></td>'
        h += "</tr>"
    h += "</tbody></table>"
    if not W("ready"):
        h = h[:_s]
    _s = len(h)
    h += "<h2>Counterparties</h2><table><thead><tr><th>Type</th><th>Name</th><th>Mapping</th><th>Remark</th></tr></thead><tbody>"
    for ty in TYPES:
        if ix["N"].get((tid, ty)) == "Not needed":
            bl = [l for l in ix["L"].get(tid, []) if l["p"]["type"] == ty and l["status"] != "Dropped"]
            h += f'<tr><td>{TYPE_PLURAL[ty]}</td><td colspan="3"><i>Not needed for this transaction</i>' + (f' - brought to us by <b>{e("; ".join(l["p"]["name"] for l in bl))}</b>' if bl else "") + "</td></tr>"
            continue
        ls = sorted([l for l in ix["L"].get(tid, []) if l["p"]["type"] == ty], key=lambda l: (l["status"] not in H.SHORTLISTED_UP, l["p"]["name"].lower()))
        if not ls:
            h += f'<tr><td>{TYPE_PLURAL[ty]}</td><td colspan="3" class="mute">none mapped yet</td></tr>'
        for j, l in enumerate(ls):
            h += (f'<tr class="{"dim" if l["status"] == "Dropped" else ""}"><td>{TYPE_PLURAL[ty] if j == 0 else ""}</td><td><b>{e(l["p"]["name"])}</b></td>'
                  f'<td>{e(l["status"])}</td><td>{e(l["remark"])}</td></tr>')
    h += "</tbody></table>"
    if not W("parties"):
        h = h[:_s]
    cm = sorted(ix["CM"].get(tid, []), key=lambda x: (x["day"], x["id"]), reverse=True)[:12]
    if cm and W("discuss"):
        h += '<h2>Discussion</h2><div class="cms">' + "".join(f'<div><small>{e(x["day"])} · {e(x["by"])}</small> {_cm_line(x)}</div>' for x in cm) + "</div>"
    ac = ix["A"].get(tid, [])
    if ac and W("actions"):
        h += '<h2>Actions</h2><div class="acs">' + "".join(f'<div><span class="cb {"on" if a["done"] else ""}"></span>{e(a["text"])} <small>— {e(a["owner"] or "no owner")}{", due " + e(a["due"]) if a["due"] else ""}</small>'
                                                         f'{" <b class=red>OVERDUE</b>" if c.overdue(a) else ""}</div>' for a in ac) + "</div>"
    return f'<section class="pg portrait">{h}</section>'



# --------------------------------------------------------------------------- milestones (meeting, LoI / EoI, information, intake / review)
def _chk(c, t, item):
    return (c.ix["C"].get(t["id"], {}).get(item) or {}).get("state", "")


def _info_state(c, t):
    g = lambda i: _chk(c, t, i)
    if g("Information package received") == "Yes" or g("FSR (feasibility study)") == "Yes":
        return "Received"
    docs = ["Information package received", "Pre-feasibility / APS", "FSR (feasibility study)", "Land available", "Concession agreement", "Government guarantee", "ESIA / permits", "Technical documents", "Project proposal submitted"]
    return "Partial" if any(g(i) in ("Yes", "In progress") for i in docs) else "Not yet"


def _state_ms(c, key, t):
    if key == "meeting":
        return t.get("meeting_status") or "Not held"
    if key == "loi":
        if t.get("loi_sent") == "Yes":
            return {"Accepted": "Accepted", "Negotiating": "Negotiating", "Rejected": "Rejected"}.get(t.get("loi_response") or "", "Sent · awaiting")
        st = _chk(c, t, "LoI / EoI submitted")
        return "In progress" if st == "In progress" else "Not applicable" if st == "N.A." else "Not sent"
    if key == "info":
        return _info_state(c, t)
    if key == "epc":
        ls = [l for l in c.ix["L"].get(t["id"], []) if l["p"]["type"] == "EPC"]
        if c.ix["N"].get((t["id"], "EPC")) == "Not needed":
            return "Not needed"
        rank = [H.LINK_STATUS.index(l["status"]) for l in ls if l["status"] != "Dropped"]
        if not rank:
            return "None"
        st = H.LINK_STATUS[max(rank)]
        return "In discussion" if st == "Term sheet received" else st
    return t.get("review_outcome") or "Pending"


MS_DEF = [("meeting", "Meeting with ministry / owner", ["Not held", "Requested", "Scheduled", "Held"]), ("loi", "LoI / EoI", ["Not sent", "In progress", "Sent · awaiting", "Accepted", "Negotiating", "Rejected", "Not applicable"]),
          ("info", "Information (readiness)", ["Not yet", "Partial", "Received"]), ("epc", "EPC mapping", ["None", "Identified", "Shortlisted", "To be approached", "Approached", "In discussion", "Appointed", "Not needed"]),
          ("review", "Review outcome", ["Pending", "Proceed", "Customise", "Hold", "Drop"])]
MS_GOOD = {"Held", "Accepted", "Received", "Available", "Shortlisted", "Appointed", "Not needed", "Proceed"}


def ms_counts(c, ts):
    """meetings held, LoI / EoI sent, information received, EPC shortlisted, review = proceed"""
    return (sum(1 for t in ts if t.get("meeting_status") == "Held"), sum(1 for t in ts if t.get("loi_sent") == "Yes"), sum(1 for t in ts if _info_state(c, t) == "Received"),
            sum(1 for t in ts if _state_ms(c, "epc", t) in ("Shortlisted", "To be approached", "Approached", "In discussion", "Appointed")), sum(1 for t in ts if t.get("review_outcome") == "Proceed"),
            sum(1 for t in ts if _state_ms(c, "epc", t) in ("None", "Identified", "Shortlisted", "To be approached", "Approached", "In discussion")))


def mgmt_comment(c, t):
    cm = sorted([x for x in c.ix["CM"].get(t["id"], []) if x.get("kind")], key=lambda x: (x["day"], x["id"]), reverse=True)
    return cm[0] if cm else None


def _meeting_txt(t):
    bits = [x for x in (t.get("meeting_with"), t.get("meeting_date")) if x]
    return f'<b>{e(t.get("meeting_status") or "Not held")}</b>' + (f'<br><small>{e(" · ".join(bits))}</small>' if bits else "")


def _loi_txt(t):
    if t.get("loi_sent") != "Yes":
        return "<span class=z>Not sent</span>"
    return f'<b>Sent</b> {e(t.get("loi_date") or "")}<br><small>{e(t.get("loi_response") or "Awaiting response")}</small>'


def _info_txt(c, t):
    f = lambda item: {"Yes": "Yes", "In progress": "In progress", "No": "Not yet", "N.A.": "N.A."}.get(_chk(c, t, item), "—")
    return (f'Info: <b>{e(f("Information package received"))}</b><br>Model: <b>{e(f("Financial model available"))}</b><br>'
            f'Owner fin.: <b>{e(f("Owner financials received"))}</b>')


def _intake_txt(t):
    rec = t.get("received_date") or (t.get("created") or "")[:10]
    return f'Received {e(rec or "—")}<br>Data {e(t.get("data_date") or "—")}<br>Review {e(t.get("review_date") or "—")}'


def _review_txt(t):
    return f'<b>{e(t.get("review_outcome") or "Pending")}</b>' + (f'<br><small>{e((t.get("review_notes") or "")[:200])}</small>' if t.get("review_notes") else "")


def _cm_line(x):
    return ('<b class=red>MGMT</b> ' if x.get("kind") else "") + e(x["text"])


def milestone_rows(c):
    docs = ["Information package received", "Pre-feasibility / APS", "FSR (feasibility study)", "Technical documents", "ESIA / permits", "Land available", "Financial model available",
            "Owner financials received", "EPC contract signed", "Concession agreement", "Offtake agreement", "Government guarantee", "MoU with owner", "Project proposal submitted"]
    lab = {"Yes": "Yes", "In progress": "In progress", "No": "Not yet", "N.A.": "N.A.", "": ""}
    head = (["Transaction", "Country", "Sector", "Owner", "Status", "Received", "Data received", "Meeting status", "Meeting date", "Meeting with", "Meetings", "LoI / EoI", "LoI / EoI date", "LoI / EoI response", "LoI / EoI note",
             "Review outcome", "Review date"] + docs + ["EPC mapping", "Meeting with", "Meeting comments", "Review notes", "Latest management comment"])
    rows = []
    for t in c.ts:
        m = mgmt_comment(c, t)
        note = (c.ix["C"].get(t["id"], {}).get("LoI / EoI submitted") or {}).get("remark") or t.get("loi_notes") or ""
        rows.append([t["name"], t["country"], t["sector"], t["lead"], t["status"], t.get("received_date") or (t.get("created") or "")[:10], t.get("data_date"), t.get("meeting_status"), t.get("meeting_date"), t.get("meeting_with"), len(c.ix["M"].get(t["id"], [])),
                     {"Yes": "Sent", "In progress": "In progress", "N.A.": "Not applicable"}.get(_chk(c, t, "LoI / EoI submitted") or ("Yes" if t.get("loi_sent") == "Yes" else ""), "Not yet"), t.get("loi_date"), t.get("loi_response"), note, t.get("review_outcome"), t.get("review_date")]
                    + [lab.get(_chk(c, t, d), "") for d in docs] + [_state_ms(c, "epc", t), t.get("meeting_with"), t.get("meeting_notes"), t.get("review_notes"), (f'{m["day"]} {m["by"]}: {m["text"]}' if m else "")])
    return head, rows


def sec_milestones(c: Ctx) -> str:
    W = lambda i: want(c, "milestones", i)
    h = header(c, c.opts.get("title") or "Milestone tracker", f"{len(c.ts)} transactions · meeting with ministry / owner, LoI / EoI, information, EPC mapping, review")
    if W("summary"):
        h += '<div class="msg">'
        for key, label, vals in MS_DEF:
            h += f'<div class="msc"><h3>{e(label)}</h3><table><tbody>'
            mx = max([sum(1 for t in c.ts if _state_ms(c, key, t) == v) for v in vals] + [1])
            for v in vals:
                m = [t for t in c.ts if _state_ms(c, key, t) == v]
                col = "#17935F" if v in MS_GOOD else ("#D81F26" if v in ("Rejected", "Drop") else "#C27A06" if v not in (vals[0],) else "#B8C0D0")
                h += f'<tr><td>{e(v)}</td><td class="n"><b>{len(m)}</b></td><td class="n mute">{money(total(m))}</td><td class="w">{vbar(len(m), mx, col)}</td></tr>'
            h += "</tbody></table></div>"
        h += "</div>"
    DOCS = [("Information package received", "Info pkg"), ("Pre-feasibility / APS", "Pre-feas."), ("FSR (feasibility study)", "FSR"), ("Technical documents", "Tech docs"), ("ESIA / permits", "ESIA"),
            ("Land available", "Land"), ("Financial model available", "Fin. model"), ("Owner financials received", "Owner fin."), ("EPC contract signed", "EPC contract"), ("Concession agreement", "Concession"), ("Offtake agreement", "Offtake"),
            ("Government guarantee", "Govt guar."), ("MoU with owner", "MoU"), ("Project proposal submitted", "Proposal")]
    d_ = lambda v: f'<td class="dt">{e(v) if v else ""}</td>'
    def doc(t, item):
        st = _chk(c, t, item)
        mark, col = {"Yes": ("✔", "#17935F"), "In progress": ("◐", "#C27A06"), "No": ("Not yet", "#D81F26"), "N.A.": ("n/a", "#6B7690"), "": ("·", "#B8C0D0")}.get(st, ("·", "#B8C0D0"))
        return f'<td class="ck" style="color:{col}">{mark}</td>'
    groups = [("", [("Transaction", lambda t: f'<td><b>{e(t["name"])}</b>' + (f'<br><small>{e(t["country"])} · {e(t["sector"])}</small>' if W("sub") else "") + "</td>")])]
    if W("status"): groups.append(("", [("Status", lambda t: f'<td>{chip(t["status"])}</td>')]))
    if W("boss"): groups.append(("", [("Owner", lambda t: f'<td>{e(t["lead"])}</td>')]))
    if W("intake"): groups.append(("Intake", [("Received", lambda t: d_(t.get("received_date") or (t.get("created") or "")[:10])), ("Data recd", lambda t: d_(t.get("data_date")))]))
    if W("meeting"): groups.append(("Latest meeting · ministry / owner", [("Status", lambda t: f'<td>{e(t.get("meeting_status") or "Not held")}</td>'), ("Date", lambda t: d_(t.get("meeting_date"))),
                                                                         ("With whom", lambda t: f'<td>{e(t.get("meeting_with") or "")}</td>'), ("#", lambda t: f'<td class="dt">{len(c.ix["M"].get(t["id"], [])) or ""}</td>')]))
    if W("loi"): groups.append(("LoI / EoI", [("Sent", lambda t: f'<td>{ {"Yes": "Sent", "In progress": "In progress", "N.A.": "Not applicable"}.get(_chk(c, t, "LoI / EoI submitted") or ("Yes" if t.get("loi_sent") == "Yes" else ""), "Not yet") }</td>'), ("Date", lambda t: d_(t.get("loi_date"))),
                                              ("Response", lambda t: f'<td>{e(t.get("loi_response") or "")}</td>'), ("Note", lambda t: f'<td><small>{e(((c.ix["C"].get(t["id"], {}).get("LoI / EoI submitted") or {}).get("remark") or t.get("loi_notes") or "")[:120])}</small></td>')]))
    if W("loi"): groups.append(("Bank term sheet", [("Banks", lambda t: f'<td><small>{e(", ".join(l["p"]["name"] for l in c.ix["L"].get(t["id"], []) if l["p"]["type"] == "Bank / Lender" and l["status"] == "Term sheet received") or "—")}</small></td>')]))
    if W("review"): groups.append(("Review", [("Outcome", lambda t: f'<td>{e(t.get("review_outcome") or "Pending")}</td>'), ("Date", lambda t: d_(t.get("review_date")))]))
    if W("info"): groups.append(("Documents &amp; information held", [(lab, (lambda it: (lambda t: doc(t, it)))(it)) for it, lab in DOCS]))
    if W("epc"): groups.append(("", [("Shortlisted EPCs", lambda t: f'<td>{e(", ".join(l["p"]["name"] for l in c.short(t, "EPC")) or "—")}</td>')]))
    if W("mgmt"): groups.append(("", [("Management comment", lambda t: (lambda m: f'<td><small>{e(m["day"])} · {e(m["by"])}</small><br>{e(m["text"][:200])}</td>' if m else "<td>—</td>")(mgmt_comment(c, t)))]))
    if W("notes"): groups.append(("", [("Meeting comments", lambda t: f'<td><small>{e((t.get("meeting_notes") or "")[:200]) or "—"}</small></td>')]))
    h += '<table class="reg mx"><thead><tr><th>Sr.</th>' + "".join(f'<th>{cols[0][0]}</th>' if not g else f'<th class="mxg" colspan="{len(cols)}">{g}</th>' for g, cols in groups) + "</tr><tr><th></th>" + "".join("<th></th>" if not g else "".join(f"<th>{lab}</th>" for lab, _ in cols) for g, cols in groups) + "</tr></thead><tbody>"
    flat = [fn for g, cols in groups for _, fn in cols]
    for i, t in enumerate(c.ts, 1):
        h += f'<tr class="{"" if t["active"] else "dim"}"><td class="n">{i}</td>' + "".join(fn(t) for fn in flat) + "</tr>"
    h += "</tbody></table>"
    return f'<section class="pg land flow">{h}</section>'


def sec_txn_track(c: Ctx, t: dict) -> str:
    rec = t.get("received_date") or (t.get("created") or "")[:10]
    cells = [("Transaction received", e(rec or "—")), ("Data received", e(t.get("data_date") or "—")), ("Review date", e(t.get("review_date") or "—")), ("Review outcome", _review_txt(t)),
             ("Meeting", _meeting_txt(t)), ("LoI / EoI", _loi_txt(t)), ("Information", e(_chk(c, t, "Information package received") or "—")), ("Financial model", e(_chk(c, t, "Financial model available") or "—")),
             ("Owner financials", e(_chk(c, t, "Owner financials received") or "—")), ("EPC mapping", e(_state_ms(c, "epc", t)))]
    h = '<h2>Tracker</h2><div class="kvg tk5">' + "".join(f'<div><span class="l">{k}</span>{v}</div>' for k, v in cells) + "</div>"
    notes = [(lab, t.get(k)) for lab, k in (("Meeting", "meeting_notes"), ("LoI / EoI", "loi_notes"), ("Review", "review_notes")) if t.get(k)]
    if notes:
        h += '<div class="cms">' + "".join(f"<div><b>{lab}:</b> {e(v[:300])}</div>" for lab, v in notes) + "</div>"
    m = mgmt_comment(c, t)
    if m:
        h += f'<div class="cms"><div><b class="red">MANAGEMENT</b> <small>{e(m["day"])} · {e(m["by"])}</small> {e(m["text"][:400])}</div></div>'
    return h

# --------------------------------------------------------------------------- sources / decks / bosses / change log (simple tables)
def split_src(s: str) -> List[str]:
    return [x.strip() for x in re.split(r"[/;]", s or "") if x.strip()] or ["(no source)"]


def data_decks(opts: dict):
    import hubdeck
    aud = opts.get("aud", "EPC")
    ps = hubdeck.projects(aud)["projects"]
    if not opts.get("include_retired"):
        ps = [p for p in ps if not p["retired"]]
    head = ["Sr.", "Project (named)", "Project (unnamed)", "Category", "Version", "Country", "Sector", "Model", "Source", "Value slide", "Status"]
    rows = [[p["sr"], p["name"], p["unnamed_name"], p["category"], p["version"], p["country"], p["sector"], p["model"], p["source"],
             "yes" if p["has_value"] else "", "retired" if p["retired"] else ("in list" if p["include"] else "hidden")] for p in ps]
    return f"Decks - {aud} base deck", f"{len(rows)} projects in the {aud} deck list", head, rows


def data_bosses(c: Ctx):
    geo = {g["country"]: g["lead"] for g in c.snap["geo"]}
    by: Dict[str, dict] = {}
    for t in c.ts:
        k = t["country"] or "(no country)"
        x = by.setdefault(k, {"n": 0, "act": 0, "hot": 0, "v": 0.0})
        x["n"] += 1
        x["act"] += 1 if t["active"] else 0
        x["hot"] += 1 if t["status"] in HOT else 0
        x["v"] += t["vn"] or 0
    for k in geo:
        by.setdefault(k, {"n": 0, "act": 0, "hot": 0, "v": 0.0})
    rows = sorted(([geo.get(k) or "Unassigned", k, x["n"], x["act"], x["hot"], round(x["v"], 1)] for k, x in by.items()),
                  key=lambda r: (["RB", "JT", "SS"].index(r[0]) if r[0] in ("RB", "JT", "SS") else 9, -r[5], r[1]))
    return "Owners by country", f"{len(rows)} countries · who leads which geography", ["Owner", "Country", "Transactions", "Active", "Tie-up / P1 / P2", "Approx. value (USD mn)"], rows


def data_log(c: Ctx, opts: dict):
    days = int(opts.get("days", 7) or 7)
    ch = H.recent_changes(days, 1500)
    rows = [[(x["ts"] or "")[:16], x["by"], x["name"] or "", x["what"], (x["detail"] or "")[:160]] for x in ch]
    return "Change log", f"Last {days} days · {len(rows)} entries" + (" (showing the latest 1500)" if len(rows) >= 1500 else ""), ["When", "Who", "Transaction", "What", "Detail"], rows


def sec_table(c: Ctx, title: str, sub: str, head: List[str], rows: List[list], land: bool = True, right=(), money_col=None, keep=None) -> str:
    keep = list(range(len(head))) if keep is None else keep
    h = header(c, title, sub)
    h += "<table><thead><tr>" + "".join(f'<th class="{"n" if i in right else ""}">{e(head[i])}</th>' for i in keep) + "</tr></thead><tbody>"
    last = None
    for r in rows:
        if r and head[0] == "Owner" and r[0] != last:
            last = r[0]
            sub_rows = [x for x in rows if x[0] == last]
            h += f'<tr class="g"><td colspan="{len(keep)}">{e(last)} <span>{len(sub_rows)} countries · {sum(x[2] for x in sub_rows)} transactions · {money(sum(x[5] for x in sub_rows))}</span></td></tr>'
        h += "<tr>" + "".join(f'<td class="{"n" if i in right else ""}">{(money(r[i]) if i == money_col else e(r[i] if r[i] not in (None, "") else "—"))}</td>' for i in keep) + "</tr>"
    if not rows:
        h += f'<tr><td colspan="{len(keep)}">Nothing to show.</td></tr>'
    return f'<section class="pg {"land" if land else "portrait"} flow">{h}</tbody></table></section>'


DECK_IDS = [None, None, "unnamed", "category", "version", "country", "sector", "model", "source", "value", "status"]
BOSS_IDS = [None, None, "n", "active", "hot", "value"]
LOG_IDS = [None, "who", "txn", "what", "detail"]


def keep_cols(c: Ctx, kind: str, ids) -> List[int]:
    return [i for i, cid in enumerate(ids) if cid is None or want(c, kind, cid)]


def sec_decks(c: Ctx) -> str:
    t, s, head, rows = data_decks(c.opts)
    return sec_table(c, t, s, head, rows, True, keep=keep_cols(c, "decks", DECK_IDS))


def sec_bosses(c: Ctx) -> str:
    t, s, head, rows = data_bosses(c)
    return sec_table(c, t, s, head, rows, False, right=(2, 3, 4, 5), money_col=5, keep=keep_cols(c, "bosses", BOSS_IDS))


def sec_log(c: Ctx) -> str:
    t, s, head, rows = data_log(c, c.opts)
    return sec_table(c, t, s, head, rows, True, keep=keep_cols(c, "log", LOG_IDS))


# --------------------------------------------------------------------------- pack cover
def sec_cover(c: Ctx, parts: List[str]) -> str:
    items = "".join(f'<li><b>{KINDS[k][0]}</b><span>{KINDS[k][1]}</span></li>' for k in parts)
    lines = "".join(f"<div>{e(x)}</div>" for x in c.opts.get("filters", []) if x)
    return (f'<section class="pg portrait cover"><img class="cl" src="{logo()}"><div class="bar"></div><h1>{e(c.opts.get("title") or "Pipeline review pack")}</h1>'
            f'<div class="sub">{datetime.now():%d %B %Y} · {len(c.ts)} transactions · prepared by {e(c.snap.get("pms", "Vishnu & Vijayraj"))}</div><div class="scope">{lines}</div>'
            + kpi_strip([("Transactions", len(c.ts)), ("Approx. value", money(total(c.ts))), ("Tie-up / P1 / P2", sum(1 for t in c.ts if t["status"] in HOT)),
                         ("Open actions", sum(1 for a in c.acts if not a["done"]))]) + f'<h2>Contents</h2><ol class="toc">{items}</ol>'
            '<div class="note">INTERNAL - contains names of counterparties, sources and commercial comments. Not for clients or counterparties.</div></section>')


# --------------------------------------------------------------------------- assemble
def css(paper: str) -> str:
    land = "A3 landscape" if paper == "A3" else "A4 landscape"
    foot = lambda: ('@bottom-left{content:"Blend · INTERNAL - not for clients";font:8px Segoe UI,Arial;color:#6B7690}'
                    '@bottom-right{content:"Page " counter(page) " of " counter(pages);font:8px Segoe UI,Arial;color:#6B7690}')
    return f"""@page portrait{{size:A4 portrait;margin:12mm 11mm 14mm;{foot()}}}@page land{{size:{land};margin:10mm 9mm 13mm;{foot()}}}
*{{box-sizing:border-box}}body{{margin:0;font:10.5px/1.38 "Segoe UI",Arial,sans-serif;color:#16213A}}
.portrait{{page:portrait}}.land{{page:land}}section.pg{{break-after:page}}section.pg:last-child{{break-after:auto}}
.hdr{{display:flex;align-items:center;gap:14px}}.hdr img{{height:34px}}.ht{{flex:1}}h1{{margin:0;font-size:21px;color:{NAVY};letter-spacing:-.01em}}.sub{{color:{MUTE};font-size:11px;margin-top:1px}}
.hr{{text-align:right;color:{MUTE};font-size:9.5px;line-height:1.3}}.hr b{{color:{RED};letter-spacing:.06em}}
.bar{{height:3px;background:linear-gradient(90deg,{RED},{AMBER});margin:7px 0 9px;border-radius:2px}}.scope{{color:{MUTE};font-size:9.5px;margin-bottom:6px}}
h2{{font-size:12.5px;margin:15px 0 5px;color:{NAVY};break-after:avoid}}h2 small{{color:{MUTE};font-weight:500}}
table{{border-collapse:collapse;width:100%;margin:2px 0 4px}}th{{background:{NAVY};color:#fff;text-align:left;padding:5px 6px;font-size:8.5px;text-transform:uppercase;letter-spacing:.03em}}
td{{padding:4px 6px;border-bottom:1px solid #DDE3EE;vertical-align:top}}tr{{break-inside:avoid}}.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}th.n{{text-align:right}}
.w{{width:24%}}.vb{{display:block;height:6px;border-radius:5px;background:#EEF1F7}}.vb i{{display:block;height:100%;border-radius:5px}}
.dim{{opacity:.5}}small{{color:{MUTE}}}.mute{{color:{MUTE}}}.red{{color:{RED};font-weight:700}}.z{{color:#B8C0D0}}.note{{color:{MUTE};font-size:9px;margin-top:8px}}
tr.g td{{background:#E8EDF7;font-weight:700;color:{NAVY}}}tr.g span{{color:{MUTE};font-weight:500;margin-left:6px}}tr.tot td{{background:#E8EDF7;font-weight:800;color:{NAVY};border-top:2px solid {NAVY}}}
.chip{{display:inline-block;color:#fff;border-radius:9px;padding:1px 8px;font-weight:700;font-size:9px;white-space:nowrap}}
.boss{{display:inline-block;background:#E8EDF7;color:{NAVY};border-radius:5px;padding:0 6px;font-weight:700;font-size:9.5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin:6px 0 4px}}.k{{border:1px solid #DDE3EE;border-top:3px solid {NAVY};border-radius:8px;padding:7px 9px}}
.k b{{display:block;font-size:17px;color:{NAVY};letter-spacing:-.02em}}.k span{{color:{MUTE};font-size:9px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.gh{{display:flex;align-items:baseline;gap:10px;border-bottom:2px solid {NAVY};margin-top:12px;break-after:avoid}}.gh h2{{margin:0 0 3px}}.gh span{{color:{MUTE}}}
.gblock{{break-inside:auto}}
.dcard{{border:1px solid #DDE3EE;border-left:4px solid var(--c);border-radius:8px;padding:8px 10px;margin:7px 0;break-inside:avoid}}
.dh{{display:flex;gap:8px;align-items:center}}.dh b{{font-size:12px;color:{NAVY};flex:1}}.dh .val{{font-weight:800;color:{NAVY}}}.ct{{color:{MUTE};font-size:9px;border:1px solid #DDE3EE;border-radius:9px;padding:0 6px}}
.meta{{color:{MUTE};font-size:9.5px;margin:2px 0 4px}}.facts{{margin:2px 0;font-size:9.8px}}
.cms div,.acs div{{margin:2px 0;padding-left:8px;border-left:2px solid #DDE3EE}}.acs div{{border-left:0;padding-left:0}}
.cb{{display:inline-block;width:9px;height:9px;border:1.3px solid {NAVY};border-radius:2px;margin-right:6px;vertical-align:-1px}}.cb.on{{background:{NAVY}}}
.decide{{margin-top:6px;height:15mm;border:1px dashed #AAB4C8;border-radius:6px;padding:3px 7px}}.decide span{{color:#9AA4B8;font-size:8.5px}}
.kvg{{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin:4px 0}}.kvg div{{border:1px solid #DDE3EE;border-radius:7px;padding:5px 8px}}.kvg .l{{display:block;color:{MUTE};font-size:8.5px;text-transform:uppercase;letter-spacing:.04em}}
p.txt{{margin:2px 0;white-space:pre-wrap}}table.chk td{{border-bottom:1px solid #EEF1F7}}.mk{{width:16px;font-weight:800;font-size:13px;text-align:center}}
.cover{{padding-top:20mm}}.cover .cl{{height:56px}}.cover h1{{font-size:30px;margin-top:6px}}.toc{{padding-left:18px}}.toc li{{margin:7px 0;font-size:11.5px}}.toc li span{{display:block;color:{MUTE};font-size:10px}}
.msg{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px 14px;margin:4px 0 8px}}.msc{{border:1px solid #DDE3EE;border-radius:8px;padding:5px 9px;break-inside:avoid}}.msc h3{{margin:0 0 3px;font-size:10.5px;color:{NAVY}}}.msc td{{padding:2px 4px;font-size:9.3px}}.msc .w{{width:30%}}
.tk5{{grid-template-columns:repeat(5,1fr)}}table.reg td,table.reg th{{font-size:9.4px}}table.mx td,table.mx th{{padding:3px 4px;font-size:8.6px}}table.mx th.mxg{{text-align:center;border-left:1px solid #D5DBE8}}table.mx td.ck{{text-align:center;font-weight:700;white-space:nowrap;font-size:9px}}table.mx td.dt{{white-space:nowrap}}table.big td{{padding:6px}}table.big .w{{width:11%}}table.big td:last-child{{white-space:nowrap}}"""


def build(kind: str, snap: dict, ids: List[int], opts: dict) -> str:
    c = Ctx(snap, ids, opts)
    if kind == "overview":
        body = sec_overview(c)
    elif kind in ("country", "sector"):
        body = sec_group(c, kind)
    elif kind == "sources":
        body = sec_group(c, "source")
    elif kind == "decks":
        body = sec_decks(c)
    elif kind == "bosses":
        body = sec_bosses(c)
    elif kind == "log":
        body = sec_log(c)
    elif kind == "register":
        body = sec_register(c)
    elif kind == "discuss":
        body = sec_discuss(c)
    elif kind == "actions":
        body = sec_actions(c)
    elif kind == "parties":
        body = sec_parties(c)
    elif kind == "milestones":
        body = sec_milestones(c)
    elif kind == "txn":
        body = "".join(sec_txn(c, t) for t in c.ts) or "<section class='pg portrait'>Nothing selected.</section>"
    elif kind == "pack":
        fn = {"overview": sec_overview, "country": lambda x: sec_group(x, "country"), "sector": lambda x: sec_group(x, "sector"), "register": sec_register,
              "discuss": sec_discuss, "actions": sec_actions, "parties": sec_parties, "sources": lambda x: sec_group(x, "source"), "bosses": sec_bosses, "milestones": sec_milestones, "txn": lambda x: "".join(sec_txn(x, t) for t in x.ts)}
        parts = [k for k in opts.get("sections", ["overview", "country", "sector", "register", "discuss", "actions", "parties"]) if k in fn]
        body = sec_cover(c, parts) + "".join(fn[k](c) for k in parts)
    else:
        raise H.HubError("Unknown document type " + kind)
    title = opts.get("title") or KINDS[kind][0]
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{e(title)}</title><style>{css(opts.get("paper", "A4"))}</style></head><body>{body}</body></html>'


def build_pdf(kind: str, snap: dict, ids: List[int], opts: dict) -> Path:
    import printing
    p = printing.write_html(f"Blend_{kind}", build(kind, snap, ids, opts))
    pdf = printing.to_pdf(p)
    try:
        p.unlink()
    except OSError:
        pass
    return pdf


def build_xlsx(kind: str, snap: dict, ids: List[int], opts: dict, path: Path) -> Path:
    """Register + discussion + counterparties sheets (existing) plus By country / By sector with approximate value."""
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    c = Ctx(snap, ids, opts)
    if kind in ("decks", "bosses", "log"):
        from openpyxl import Workbook
        title, sub, head, rows = data_decks(opts) if kind == "decks" else data_bosses(c) if kind == "bosses" else data_log(c, opts)
        k = keep_cols(c, kind, DECK_IDS if kind == "decks" else BOSS_IDS if kind == "bosses" else LOG_IDS)
        head, rows = [head[i] for i in k], [[r[i] for i in k] for r in rows]
        wb = Workbook()
        ws = wb.active
        ws.title = title[:30]
        ws.append(head)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1B2F5B")
        for r in rows:
            ws.append(r)
        for i in range(1, len(head) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 34 if i in (2, 3, 5) and kind != "log" else 18
        ws.freeze_panes = "A2"
        wb.save(path)
        return path
    if kind == "milestones":
        from openpyxl import Workbook
        head, rows = milestone_rows(c)
        wb = Workbook()
        ws = wb.active
        ws.title = "Milestones"
        ws.append(head)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1B2F5B")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for r in rows:
            ws.append(r)
        for i in range(1, len(head) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 34 if head[i - 1] in ("Transaction", "Review notes", "Meeting comments", "LoI / EoI comments", "Latest management comment") else 16
        ws.freeze_panes = "B2"
        wb.save(path)
        return path
    R.build_xlsx(snap, ids, opts, path)
    wb = load_workbook(path)
    ws = wb.create_sheet("Milestones")
    mh, mrows = milestone_rows(c)
    ws.append(mh)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B2F5B")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for r in mrows:
        ws.append(r)
    for i in range(1, len(mh) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 34 if mh[i - 1] in ("Transaction", "Review notes", "Meeting comments", "LoI / EoI comments", "Latest management comment") else 16
    ws.freeze_panes = "B2"
    for name, keyf in (("By country", lambda t: t["country"] or "(no country)"), ("By sector", lambda t: t["sector"] or "(none)"), ("By source", lambda t: split_src(t["introduced"]))):
        ws = wb.create_sheet(name)
        ws.append([name[3:].title(), "Transactions"] + list(H.STATUSES) + ["Approx. value (USD mn)", "Tie-up / P1 / P2 value (USD mn)", "With a value", "With shortlisted EPC"])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1B2F5B")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for x in group_rows(c, keyf):
            ws.append([x["k"], x["n"]] + [x["st"].get(s, 0) for s in H.STATUSES] + [round(x["v"], 1), round(x["hotv"], 1), x["nv"], x["ep"]])
        n = ws.max_row
        ws.append(["Total", f"=SUM(B2:B{n})"] + [f"=SUM({get_column_letter(i)}2:{get_column_letter(i)}{n})" for i in range(3, 3 + len(H.STATUSES) + 4)])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
        ws.column_dimensions["A"].width = 30
        for i in range(2, 12):
            ws.column_dimensions[get_column_letter(i)].width = 14
        ws.freeze_panes = "B2"
    wb.save(path)
    return path
