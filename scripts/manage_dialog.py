#!/usr/bin/env python3
"""Manage projects: add, edit attributes, delete, retire/restore, reorder, rename, duplicate, undo - single or multi-select."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import List

import deckcore as core
import modelnames
from multipick import MultiPick, selected
import listutil as lu
import sectors
import srcmgr
import projmgr as pm
import tracker as T

NL = chr(10)
KEEP = "(keep current)"
NAVY, MUTE, INK = "#1B3A5F", "#78909C", "#22293A"
LEAD_COL = {"RB": "#00796B", "JT": "#5E35B1", "SS": "#E65100"}
CAT_COL = {"Closed": "#2E7D32", "Active": "#1565C0", "BIP": "#B07800", "Hold": "#C62828"}


def _versions_text(p: dict) -> str:
    sl = p["slides"]
    if sl["single"]:
        return "Both (same slide)"
    return {(True, True): "Named + Unnamed", (True, False): "Named only", (False, True): "Unnamed only"}.get(
        (bool(sl["named"]), bool(sl["unnamed"])), "-")


class ManageDialog(tk.Toplevel):
    def __init__(self, app, audience: str):
        super().__init__(app)
        self.app, self.aud = app, audience
        self.title("Manage projects")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1320, sw - 40), min(780, sh - 100)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+10")
        self.minsize(900, 520)
        self.configure(bg="#F4F6FA")
        self.transient(app)
        self.items: List[dict] = []
        self.show_retired = tk.BooleanVar(value=False)
        self.sort_keys: list = []  # [(column, reverse)], primary first; empty = deck order
        self.f_sector, self.f_country = tk.StringVar(value=lu.ALL), tk.StringVar(value=lu.ALL)
        self.f_cat, self.f_text = tk.StringVar(value=lu.ALL), tk.StringVar()
        self.f_model = tk.StringVar(value=lu.ALL)
        self.f_source = tk.StringVar(value=lu.ALL)
        self.f_lead = tk.StringVar(value="All")
        self._leadmap: dict = {}
        st = ttk.Style(self)
        st.configure("Manage.Treeview", rowheight=28, font=("Segoe UI", 10), borderwidth=0)
        st.configure("Manage.Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=(4, 5))

        # ---- header band
        hd = tk.Frame(self, bg=NAVY, padx=16, pady=9)
        hd.pack(fill="x")
        tk.Label(hd, text="Manage projects", bg=NAVY, fg="white", font=("Segoe UI Semibold", 15)).pack(side="left")
        tk.Label(hd, text="   " + audience + " deck", bg=NAVY, fg="#9FB4CE", font=("Segoe UI", 10)).pack(side="left", pady=(5, 0))
        self.count = tk.Label(hd, text="", bg=NAVY, fg="#C9D6E8", font=("Segoe UI", 10))
        self.count.pack(side="right")

        # ---- action bar
        bar = tk.Frame(self, bg="#FFFFFF", padx=14, pady=9, highlightbackground="#DDE3EC", highlightthickness=1)
        bar.pack(fill="x")

        def btn(parent, text, cmd, kind="plain", pad=(0, 6)):
            bg, fg = {"primary": ("#1565C0", "#FFFFFF"), "danger": ("#FFFFFF", "#B71C1C"), "plain": ("#EEF2F7", INK)}[kind]
            b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat", bd=0, padx=12, pady=4, cursor="hand2",
                          activebackground="#DCE6F2", font=("Segoe UI", 9, "bold" if kind == "primary" else "normal"))
            if kind == "danger":
                b.configure(highlightbackground="#E6B8B8", highlightthickness=1)
            b.pack(side="left", padx=pad)
            return b
        btn(bar, "\uff0b  Add project", self.add, "primary")
        btn(bar, "Edit attributes", self.edit)
        btn(bar, "Duplicate", self.duplicate)
        btn(bar, "Retire / Restore", self.retire)
        btn(bar, "Change boss", self.boss)
        btn(bar, "Delete", self.delete, "danger")
        tk.Frame(bar, bg="#DDE3EC", width=1).pack(side="left", fill="y", padx=10)
        tk.Label(bar, text="Move", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        for t, wh in (("\u25b2", "up"), ("\u25bc", "down"), ("\u2912", "top"), ("\u2913", "bottom")):
            btn(bar, t, lambda wh=wh: self.move(wh), pad=(0, 3))
        mb = tk.Menubutton(bar, text="More \u25be", bg="#EEF2F7", fg=INK, relief="flat", bd=0, padx=12, pady=4, cursor="hand2", activebackground="#DCE6F2")
        mm = tk.Menu(mb, tearoff=0)
        mm.add_command(label="Rename the project key\u2026", command=self.rename)
        mm.add_command(label="Tag slides\u2026", command=self.tag)
        mm.add_command(label="Sources\u2026", command=self.sources)
        mb.configure(menu=mm)
        mb.pack(side="left", padx=(10, 0))
        btn(bar, "Print / PDF\u2026", self.print_list, pad=(0, 0)).pack_configure(side="right")
        btn(bar, "Undo / backups\u2026", self.undo, pad=(0, 8)).pack_configure(side="right")
        ttk.Checkbutton(bar, text="Show retired", variable=self.show_retired, command=self.fill).pack(side="right", padx=14)

        # ---- find / filter bar: boss first
        fb = tk.Frame(self, bg="#FFFFFF", padx=14, pady=8, highlightbackground="#DDE3EC", highlightthickness=1)
        fb.pack(fill="x")
        tk.Label(fb, text="Lead", bg="#FFFFFF", fg=MUTE).pack(side="left")
        self.lead_btns = {}
        for v in ("All", "RB", "JT", "SS", "Unassigned"):
            b = tk.Radiobutton(fb, text=v, value=v, variable=self.f_lead, indicatoron=False, command=self.fill, padx=12, pady=3, bg="#ECEFF4", fg=INK,
                               selectcolor=LEAD_COL.get(v, NAVY), activeforeground="white", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2")
            b.pack(side="left", padx=(6, 0))
            self.lead_btns[v] = b
        tk.Label(fb, text="   Search", bg="#FFFFFF", fg=MUTE).pack(side="left", padx=(14, 4))
        ttk.Entry(fb, textvariable=self.f_text, width=24).pack(side="left")
        self.f_text.trace_add("write", lambda *a: self.fill())
        ttk.Button(fb, text="Clear filters", command=self.clear_filters).pack(side="left", padx=(12, 4))
        ttk.Button(fb, text="Deck order", command=self.reset_sort).pack(side="left")
        fb2 = tk.Frame(self, bg="#FFFFFF", padx=14, pady=0)
        fb2.pack(fill="x")
        self.cb_sector = ttk.Combobox(fb2, textvariable=self.f_sector, state="readonly", width=22)
        self.cb_country = ttk.Combobox(fb2, textvariable=self.f_country, state="readonly", width=16)
        self.cb_cat = ttk.Combobox(fb2, textvariable=self.f_cat, values=[lu.ALL] + core.CATEGORY_ORDER, state="readonly", width=9)
        self.cb_source = ttk.Combobox(fb2, textvariable=self.f_source, state="readonly", width=26)
        for lbl, cb in (("Sector", self.cb_sector), ("Country", self.cb_country), ("Category", self.cb_cat), ("Source", self.cb_source)):
            tk.Label(fb2, text=lbl, bg="#FFFFFF", fg=MUTE).pack(side="left", padx=(0 if lbl == "Sector" else 14, 4))
            cb.pack(side="left", pady=(0, 8))
            cb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        tk.Label(fb2, text="Model", bg="#FFFFFF", fg=MUTE).pack(side="left", padx=(14, 4))
        MultiPick(fb2, self.f_model, modelnames.ORDER, width=11, empty=lu.ALL).pack(side="left", pady=(0, 8))
        self.f_model.trace_add("write", lambda *a: self.fill())
        tk.Label(self, text="Ctrl / Shift-click selects several projects.  Click a heading to sort (click a second heading to sort within the first).  "
                            "Every change backs up the base deck first - Undo / backups brings it back.", anchor="w", padx=16, pady=4, fg=MUTE,
                 bg="#F4F6FA", font=("Segoe UI", 9)).pack(fill="x")

        # ---- the table
        cols = ("n", "name", "key", "cat", "sector", "country", "lead", "src", "vers", "dver", "inc", "status", "slides")
        frame = tk.Frame(self, bg="#FFFFFF", highlightbackground="#DDE3EC", highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended", style="Manage.Treeview")
        self.heads = {"n": "Sr.", "name": "Project", "key": "Key", "cat": "Category", "sector": "Sector", "country": "Country", "lead": "Lead",
                      "src": "Source / Origination", "vers": "Slides available", "dver": "Default", "inc": "Ticked",
                      "status": "Status", "slides": "Slide no."}
        for c, w in (("n", 36), ("name", 270), ("key", 125), ("cat", 62), ("sector", 105), ("country", 82), ("lead", 44), ("src", 150),
                     ("vers", 100), ("dver", 58), ("inc", 46), ("status", 60), ("slides", 70)):
            self.tree.heading(c, text=self.heads[c], command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, anchor="center" if c in ("n", "lead", "inc", "dver", "cat") else "w", stretch=(c == "name"))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("odd", background="#F6F8FB")
        for cat, col in CAT_COL.items():
            self.tree.tag_configure("cat_" + cat, foreground=col)
        self.tree.tag_configure("ret", foreground="#90A4AE")
        self.tree.tag_configure("warn", foreground="#C62828")
        self.msg = tk.Label(self, text="", anchor="w", padx=16, pady=4, fg="#2E7D32", bg="#F4F6FA", font=("Segoe UI", 9, "bold"))
        self.msg.pack(fill="x")
        self.fill()

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------ sorting / filtering
    def sort_by(self, col):
        if col in ("slides", "status"):
            return
        self.sort_keys = [] if col == "n" and self.sort_keys and self.sort_keys[0] == ("n", True) else lu.toggle_sort(self.sort_keys, col)
        self.fill()

    def reset_sort(self):
        self.sort_keys = []
        self.fill()

    def clear_filters(self):
        self.f_sector.set(lu.ALL)
        self.f_country.set(lu.ALL)
        self.f_cat.set(lu.ALL)
        self.f_model.set(lu.ALL)
        self.f_text.set("")
        self.f_source.set(lu.ALL)
        self.f_lead.set("All")
        self.fill()

    def _get(self, p, col):
        return {"n": p["_n"], "name": p["name"], "key": p["id"], "cat": core.CATEGORY_ORDER.index(p["category"]) if p["category"] in core.CATEGORY_ORDER else 9,
                "sector": p["sector"], "country": p["country"], "vers": _versions_text(p), "dver": p["version"],
                "inc": "yes" if p["include"] else "no", "src": p["source"], "lead": self._leadmap.get(p["id"], "")}[col]

    def fill(self, reselect: List[str] | None = None):
        keep = reselect if reselect is not None else list(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        try:
            data = core.load_projects(self.aud, include_retired=True)
        except core.DeckError as exc:
            messagebox.showerror("Cannot read the base deck", str(exc), parent=self)
            self.destroy()
            return
        self.items = data["projects"]
        for i, p in enumerate(self.items, 1):
            p["_n"] = f"{i:04d}"
        self.cb_sector.configure(values=[lu.ALL] + lu.distinct(self.items, "sector"))
        self.cb_country.configure(values=[lu.ALL] + lu.distinct(self.items, "country"))
        src_vals = [lu.ALL, lu.NO_SOURCE] + lu.distinct_sources(self.items)
        self.cb_source.configure(values=src_vals)
        if self.f_source.get() not in src_vals:
            self.f_source.set(lu.ALL)
        for var, vals in ((self.f_sector, lu.distinct(self.items, "sector")), (self.f_country, lu.distinct(self.items, "country"))):
            if var.get() not in [lu.ALL] + vals:
                var.set(lu.ALL)
        ret = sum(1 for p in self.items if p["retired"])
        try:
            geo = {g["country"].lower(): g["lead"] for g in T.geo_list()}
            ov = T.overview()
            self._leadmap = {p["id"]: (ov.get(p["id"], {}).get("lead") or geo.get(T.canonical(p.get("country", "")).lower(), "")) for p in self.items}
        except Exception:
            self._leadmap = {}
        srcs = [] if self.f_source.get() == lu.ALL else [self.f_source.get()]
        base = [p for p in self.items if (self.show_retired.get() or not p["retired"])
                and lu.matches(p, self.f_sector.get(), self.f_country.get(), self.f_cat.get(), self.f_text.get(), srcs, selected(self.f_model))]
        want = self.f_lead.get()
        vis = [p for p in base if want == "All" or (not self._leadmap.get(p["id"]) if want == "Unassigned" else self._leadmap.get(p["id"]) == want)]
        for v, b in self.lead_btns.items():
            n = len(base) if v == "All" else sum(1 for p in base if (not self._leadmap.get(p["id"]) if v == "Unassigned" else self._leadmap.get(p["id"]) == v))
            b.configure(text=f"{v}  {n}")
        vis = lu.sort_items(vis, self.sort_keys, self._get)
        for n, p in enumerate(vis):
            sl = p["slides"]
            nums = ",".join(str(x) for v in ("named", "unnamed", "single") for x in sl[v])
            first = "ret" if p["retired"] else ("warn" if not p["has_unnamed"] else "cat_" + p["category"])
            tags = (first, "odd") if n % 2 else (first,)
            self.tree.insert("", "end", iid=p["id"], tags=tags, values=(
                p["sr"] if p["sr"] != "" else int(p["_n"]), p["name"], p["id"], p["category"], p["sector"], p["country"] or "",
                self._leadmap.get(p["id"], "") or "\u2014", p["source"], _versions_text(p), p["version"],
                "yes" if p["include"] else "no", "RETIRED" if p["retired"] else "", nums))
        for c, t in self.heads.items():
            self.tree.heading(c, text=lu.heading_text(t, self.sort_keys, c))
        total = len(self.items) - (0 if self.show_retired.get() else ret)
        self.count.configure(text=f"{len(self.items) - ret} active  \u00b7  {ret} retired  \u00b7  showing {len(vis)} of {total}"
                                  + ("   (sorted view - Move uses deck order)" if self.sort_keys else ""))
        sel = [k for k in keep if self.tree.exists(k)]
        if sel:
            self.tree.selection_set(sel)

    def _sel(self, need=1, single=False) -> List[str]:
        sel = list(self.tree.selection())
        if len(sel) < need:
            messagebox.showinfo("Select projects", "Select " + ("one project" if single else "at least one project") + " in the list first.", parent=self)
            return []
        if single and len(sel) != 1:
            messagebox.showinfo("One project only", "This action works on one project at a time.", parent=self)
            return []
        return sel

    def _after(self, text: str, keys: List[str] | None = None):
        self.msg.configure(text=text)
        self.fill(reselect=keys)
        self.app.load_audience(preserve=True)

    def _run(self, fn, *a, **k):
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            return fn(*a, **k)
        except core.DeckError as exc:
            self.configure(cursor="")
            messagebox.showerror("Not done", str(exc), parent=self)
            return None
        finally:
            self.configure(cursor="")

    # ------------------------------------------------------------------ actions
    def add(self):
        from add_project_dialog import AddProjectDialog
        AddProjectDialog(self.app, self.aud, [p for p in self.items if not p["retired"]],
                         on_done=lambda: self._after("New project added (see the main list: unticked, marked NEW)."))

    def print_list(self):
        from printing import PrintDialog
        by = {p["id"]: p for p in self.items}
        names = {"n": "Sr.", "name": "Project", "key": "Key", "cat": "Category", "sector": "Sector", "country": "Country", "lead": "Boss",
                 "src": "Source", "vers": "Slides available", "dver": "Default", "inc": "Ticked"}

        def rows(only):
            ids = list(self.tree.selection()) if only else list(self.tree.get_children())
            ids = [i for i in self.tree.get_children() if i in set(ids)]  # keep the order shown on screen
            out = []
            for i in ids:
                p = by[i]
                sl = p["slides"]
                boss = self._leadmap.get(p["id"]) or "Unassigned"
                out.append({"sr": p["sr"], "name": p["name"], "key": p["id"], "category": p["category"], "sector": p["sector"],
                            "country": p["country"], "lead": boss, "lead_country": f"{boss} \u2014 {p['country'] or '(no country)'}",
                            "source": p["source"], "model": p.get("model", ""), "avail": _versions_text(p), "default": p["version"],
                            "ticked": "yes" if p["include"] else "no", "status": "RETIRED" if p["retired"] else "",
                            "slides": ",".join(str(n) for v in ("named", "unnamed", "single") for n in sl[v])})
            return out

        def meta():
            src = [] if self.f_source.get() == lu.ALL else [self.f_source.get()]
            return ["Manage projects - " + self.aud] + (["Boss: " + self.f_lead.get()] if self.f_lead.get() != "All" else []) + lu.describe(self.f_sector.get(), self.f_country.get(), self.f_cat.get(), src,
                                                                   self.f_text.get(), self.sort_keys, names)
        PrintDialog(self, {
            "title": "Projects - " + self.aud, "name": "Projects_" + self.aud, "meta": meta, "rows": rows,
            "only_label": "Only the rows I have selected",
            "columns": [("sr", "Sr.", True), ("name", "Project", True), ("key", "Key", False), ("category", "Category", True),
                        ("sector", "Sector", True), ("country", "Country", True), ("lead", "Boss", True), ("model", "Model", True), ("source", "Source / Origination", False),
                        ("avail", "Slides available", True), ("default", "Default", False), ("ticked", "Ticked", False),
                        ("status", "Status", False), ("slides", "Slide no.", False)],
            "groups": {"Boss": "lead", "Boss, then Country": "lead_country", "Country": "country", "Sector": "sector", "Category": "category", "Model": "model", "Source": "source"}})

    def sources(self):
        from sources_dialog import SourcesDialog
        SourcesDialog(self.app, self.aud, on_show=lambda s: (self.f_source.set(s[0] if len(s) == 1 else lu.ALL), self.fill()))

    def tag(self):
        from tag_dialog import TagDialog
        TagDialog(self.app, self.aud)

    def delete(self):
        keys = self._sel()
        if not keys:
            return
        win = tk.Toplevel(self)
        win.title("Delete")
        win.transient(self)
        win.grab_set()
        names = NL.join("  • " + next(p["name"] for p in self.items if p["id"] == k)[:70] for k in keys[:10])
        tk.Label(win, justify="left", padx=14, pady=10, text=f"Delete from the base deck ({len(keys)} project(s)):" + NL + names +
                 ("" if len(keys) <= 10 else NL + f"  ... and {len(keys) - 10} more")).pack(anchor="w")
        what = tk.StringVar(value="all")
        for v, t in (("all", "The WHOLE project (named + unnamed slides)"), ("named", "Only the NAMED slide(s)"),
                     ("unnamed", "Only the UNNAMED slide(s)")):
            tk.Radiobutton(win, text=t, value=v, variable=what, anchor="w").pack(anchor="w", padx=20)
        tk.Label(win, fg="#546E7A", justify="left", padx=14, pady=6,
                 text="The slides are removed from the base deck (a backup is kept, so 'Undo' can bring them back)." + NL +
                      "Tip: use 'Retire' instead if you may need the project again.").pack(anchor="w")

        def go():
            versions = None if what.get() == "all" else ([what.get()])
            win.destroy()
            res = self._run(pm.delete_projects, self.aud, keys, versions, lambda m: None)
            if res:
                self._after(f"Deleted {len(res['slides'])} slide(s).")
        f = tk.Frame(win, pady=8)
        f.pack(fill="x")
        ttk.Button(f, text="Delete", command=go).pack(side="right", padx=10)
        ttk.Button(f, text="Cancel", command=win.destroy).pack(side="right")

    def retire(self):
        keys = self._sel()
        if not keys:
            return
        by = {p["id"]: p for p in self.items}
        restore = all(by[k]["retired"] for k in keys)
        if not restore and not messagebox.askyesno(
                "Retire?", f"Retire {len(keys)} project(s)?" + NL + NL + "They disappear from the main list and are never put in a deck, "
                "but their slides stay in the base deck. Restore them any time (tick 'Show retired').", parent=self):
            return
        res = self._run(pm.set_retired, self.aud, keys, not restore)
        if res:
            self._after(("Restored " if restore else "Retired ") + f"{len(keys)} project(s).", keys)

    def boss(self):
        keys = self._sel()
        if keys:
            from boss_dialog import BossDialog
            by = {p["id"]: p for p in self.items}
            BossDialog(self, [by[k] for k in keys], on_done=self.fill)

    def move(self, where):
        keys = self._sel()
        if not keys:
            return
        res = self._run(pm.move_projects, self.aud, keys, where)
        if res is not None:
            self._after("Moved." if res.get("moved") else "Already there.", keys)

    def rename(self):
        keys = self._sel(single=True)
        if not keys:
            return
        new = simpledialog.askstring("Rename key", "New project key for '" + keys[0] + "':" + NL + "(its Excel details are carried over)", initialvalue=keys[0], parent=self)
        if new and core.norm_id(new) != keys[0]:
            if self._run(pm.rename_project, self.aud, keys[0], new) is None and not self.tree.exists(core.norm_id(new)):
                pass
            self._after("Renamed to '" + core.norm_id(new) + "'.", [core.norm_id(new)])

    def duplicate(self):
        keys = self._sel(single=True)
        if not keys:
            return
        new = simpledialog.askstring("Duplicate", "Key for the copy of '" + keys[0] + "':", initialvalue=keys[0] + "_copy", parent=self)
        if new:
            if self._run(pm.duplicate_project, self.aud, keys[0], new) is not None:
                self._after("Copied. Open the base deck in PowerPoint to edit the copy's text.", [core.norm_id(new)])

    def edit(self):
        keys = self._sel()
        if keys:
            EditDialog(self, keys)

    def undo(self):
        BackupDialog(self)


class EditDialog(tk.Toplevel):
    """Change ONLY the attributes you touch, on every selected project."""

    def __init__(self, parent: ManageDialog, keys: List[str]):
        super().__init__(parent)
        self.p, self.keys = parent, keys
        self.title(f"Edit attributes - {len(keys)} project(s)")
        self.transient(parent)
        self.grab_set()
        by = {p["id"]: p for p in parent.items}
        one = by[keys[0]] if len(keys) == 1 else None
        tk.Label(self, justify="left", padx=14, pady=8, wraplength=560, text=(
            "Only the fields you change are applied; everything left on '(keep current)' / unchanged stays as it is."
            + (" Several projects selected: the name fields are not available." if len(keys) > 1 else ""))).grid(row=0, column=0, columnspan=2, sticky="w")
        self.v = {}
        self.base = {}

        def row(r, label, key, widget, value):
            tk.Label(self, text=label).grid(row=r, column=0, sticky="w", padx=14, pady=4)
            var = tk.StringVar(value=value)
            self.v[key], self.base[key] = var, value
            if widget == "entry":
                ttk.Entry(self, textvariable=var, width=46).grid(row=r, column=1, sticky="w", padx=6)
            elif widget == "source":
                ttk.Combobox(self, textvariable=var, values=lu.distinct_sources(parent.items), width=44).grid(row=r, column=1, sticky="w", padx=6)
            else:
                ttk.Combobox(self, textvariable=var, values=widget, state="readonly", width=24).grid(row=r, column=1, sticky="w", padx=6)
        g = lambda f: (one[f] if one else "")  # noqa: E731
        row(1, "Category", "category", [KEEP] + core.CATEGORY_ORDER, one["category"] if one else KEEP)
        row(2, "Default version (Named / Unnamed)", "version", [KEEP, "Named", "Unnamed"], one["version"] if one else KEEP)
        row(3, "Ticked by default in the list", "include", [KEEP, "Yes", "No"], ("Yes" if one["include"] else "No") if one else KEEP)
        row(4, "Country", "country", "entry", g("country"))
        row(5, "Sector", "sector", ([KEEP] if not one else []) + sectors.SECTORS, one["sector"] if one else KEEP)
        row(6, "Region (for unnamed)", "region", "entry", g("region"))
        row(7, "Model", "model", "entry", g("model"))
        if one:
            row(8, "Index name (named)", "name", "entry", g("name"))
            row(9, "Index name (unnamed)", "unnamed_name", "entry", g("unnamed_name"))
        row(10, "Source(s) - separate with  /", "source", "source", g("source"))
        if one:
            row(11, "Source notes", "source_notes", "entry", g("source_notes"))
        else:
            row(11, "Source: what to do", "source_mode", ["add to existing", "remove from existing", "replace existing"], "add to existing")
        self.sum = tk.Label(self, fg="#1565C0", font=("Segoe UI", 9, "bold"), anchor="w", padx=14)
        self.sum.grid(row=20, column=0, columnspan=2, sticky="w", pady=6)
        for var in self.v.values():
            var.trace_add("write", lambda *a: self._sum())
        f = tk.Frame(self, pady=8)
        f.grid(row=21, column=0, columnspan=2, sticky="e")
        ttk.Button(f, text="Cancel", command=self.destroy).pack(side="right", padx=10)
        ttk.Button(f, text="Apply", command=self.apply).pack(side="right")
        self._sum()

    def _changes(self) -> dict:
        ch = {}
        for k, var in self.v.items():
            val = var.get().strip()
            if val == self.base[k] or val == KEEP or (val == "" and k not in ("country", "region", "model", "source", "source_notes")):
                continue
            ch[k] = val
        return ch

    def _sum(self):
        ch = self._changes()
        ch.pop("source_mode", None)
        multi = len(self.keys) > 1
        txt = ", ".join((f"source ({self.v['source_mode'].get().split()[0]})" if (k == "source" and multi) else k) + f" → {v}" for k, v in ch.items())
        self.sum.configure(text=("Will change: " + txt) if ch else "Nothing changed yet.")

    def apply(self):
        ch = self._changes()
        mode = ({"add": "add", "remove": "remove", "replace": "replace"}[self.v["source_mode"].get().split()[0]]
                if "source_mode" in self.v else "replace")
        ch.pop("source_mode", None)
        if not ch:
            messagebox.showinfo("Nothing to change", "You have not changed anything.", parent=self)
            return
        if "source" in ch and len(self.keys) > 1:  # several projects: add / remove / replace, not blindly overwrite
            import sourcesheet
            srcs = sourcesheet.split_sources(ch.pop("source"))
            res0 = self.p._run(srcmgr.set_project_sources, self.p.aud, self.keys, srcs, mode)
            if res0 is None:
                return
            if not ch:
                self.p._after(f"Source ({mode}) applied to {res0} project(s).", self.keys)
                self.destroy()
                return
        if len(self.keys) > 1 and not messagebox.askyesno(
                "Apply?", f"Apply to {len(self.keys)} projects:" + NL + NL + NL.join(f"   {k} → {v}" for k, v in ch.items()) + NL + NL + "Everything else stays unchanged.", parent=self):
            return
        res = self.p._run(pm.update_fields, self.p.aud, self.keys, ch)
        if res is not None:
            self.p._after(f"Updated {', '.join(ch)} on {res} project(s).", self.keys)
            self.destroy()


class BackupDialog(tk.Toplevel):
    def __init__(self, parent: ManageDialog):
        super().__init__(parent)
        self.p = parent
        self.title("Undo / backups of the base deck")
        self.geometry("820x480")
        self.transient(parent)
        self.grab_set()
        tk.Label(self, anchor="w", justify="left", padx=12, pady=6, wraplength=780, text=(
            "Every change saved a copy of the deck as it was BEFORE the change. Select one and press Restore to go back to that state "
            "(the current deck is backed up first, so you can also undo the undo).")).pack(fill="x")
        cols = ("when", "what", "size")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("when", "Saved", 150), ("what", "Deck as it was before...", 520), ("size", "MB", 60)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=12)
        self.files = {}
        for b in pm.list_backups(parent.aud):
            iid = self.tree.insert("", "end", values=(b["when"].strftime("%d %b %Y  %H:%M:%S"), b["what"], f"{b['size'] / 1e6:.1f}"))
            self.files[iid] = b["file"]
        f = tk.Frame(self, pady=8)
        f.pack(fill="x", padx=12)
        ttk.Button(f, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(f, text="Restore the selected state", command=self.restore).pack(side="right", padx=8)

    def restore(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select one", "Select a backup first.", parent=self)
            return
        if not messagebox.askyesno("Restore?", "Put the base deck back to the selected state?" + NL + NL + "The current deck is backed up first.", parent=self):
            return
        try:
            pm.restore_backup(self.p.aud, self.files[sel[0]])
        except core.DeckError as exc:
            messagebox.showerror("Not restored", str(exc), parent=self)
            return
        self.p._after("Base deck restored from a backup.")
        self.destroy()
