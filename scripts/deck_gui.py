#!/usr/bin/env python3
"""Selection window: audience -> client -> projects (show / category / named-unnamed) -> Generate."""
from __future__ import annotations

import os
import sys
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deckcore as core  # noqa: E402
import modelnames
from multipick import MultiPick, selected
import listutil as lu  # noqa: E402
import tracker as T  # noqa: E402
from tag_dialog import TagDialog  # noqa: E402

CAT_COLORS = {"Closed": "#2E7D32", "Active": "#1565C0", "BIP": "#B07800", "Hold": "#C62828"}
NAVY = "#1B3A5F"
APP_NAME = "DealDeck Studio"
APP_TAGLINE = "Partner & investor decks, built from one master"
ASSETS = Path(__file__).resolve().parent.parent / "assets"


class Row:
    """One project line in the table."""

    def __init__(self, app: "App", parent: tk.Widget, r: int, p: dict):
        self.p = p
        self.app = app
        self.flag = ""
        self.show = tk.BooleanVar(value=p["include"])
        self.cat = tk.StringVar(value=p["category"])
        versions = []
        if p["has_named"]:
            versions.append("Named")
        if p["has_unnamed"]:
            versions.append("Unnamed")
        self.versions = versions or ["Named"]
        v = p["version"] if p["version"] in self.versions else self.versions[0]
        self.ver = tk.StringVar(value=v)
        self.val = tk.BooleanVar(value=False)  # show indicative value? default NO

        bg = "#FFFFFF"
        self.widgets = []
        chk = tk.Checkbutton(parent, variable=self.show, bg=bg, command=app.update_counts, activebackground=bg)
        lbl = tk.Label(parent, text=p["name"], anchor="w", justify="left", bg=bg, wraplength=400, font=("Segoe UI", 10))
        cb_cat = ttk.Combobox(parent, textvariable=self.cat, values=core.CATEGORY_ORDER, state="readonly", width=8)
        cb_ver = ttk.Combobox(parent, textvariable=self.ver, values=self.versions, state="readonly", width=9)
        self.chk_val = tk.Checkbutton(parent, variable=self.val, bg=bg, activebackground=bg,
                                      state="normal" if p.get("has_value") else "disabled")
        self.country = tk.Label(parent, anchor="w", bg=bg, fg="#37474F", font=("Segoe UI", 9), width=15)
        self.sector = tk.Label(parent, anchor="w", bg=bg, fg="#546E7A", font=("Segoe UI", 9), width=20, text=p.get("sector", ""))
        self.warn = tk.Label(parent, anchor="w", bg=bg, fg="#C62828", font=("Segoe UI", 9, "bold"), width=22, justify="left")
        self.sr = tk.Label(parent, anchor="e", bg=bg, fg="#78909C", font=("Segoe UI", 9), width=4, text=str(p.get("sr", "")))
        self.source = tk.Label(parent, anchor="w", bg=bg, fg="#1B3A5F", font=("Segoe UI", 9), width=24,
                               text=p.get("source", ""))
        self.widgets = [self.sr, chk, lbl, cb_cat, cb_ver, self.chk_val, self.country, self.sector, self.source, self.warn]
        cb_cat.bind("<<ComboboxSelected>>", lambda e: app.update_counts())
        cb_ver.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        if len(self.versions) == 1:
            cb_ver.configure(state="disabled")
        self.refresh()

    def place(self, r: int):
        """Show this row at position r (alternating stripe colours)."""
        bg = "#F4F7FB" if r % 2 == 0 else "#FFFFFF"
        for c, w in enumerate(self.widgets):
            if not isinstance(w, ttk.Combobox):
                w.configure(bg=bg)
                if isinstance(w, tk.Checkbutton):
                    w.configure(activebackground=bg)
            w.grid(row=r, column=c, sticky="nsew", padx=(6 if c == 0 else 3, 3), pady=0, ipady=3)

    def hide(self):
        for w in self.widgets:
            w.grid_remove()

    def refresh(self):
        p = self.p
        unnamed = self.ver.get() == "Unnamed" and bool(p["slides"]["unnamed"])
        loc = (p["region"] if unnamed else p["country"])
        self.country.configure(text="" if (loc or "").upper() == "TBD" else (loc or ""))
        warn = ""
        if not p["has_unnamed"]:
            warn = "⚠ named version only"
        elif not p["has_named"]:
            warn = "unnamed version only"
        elif unnamed and p["leaks"]:
            warn = "⚠ contains: " + ", ".join(p["leaks"][:2])
        if self.flag:
            warn = self.flag + ("  " + warn if warn else "")
        self.warn.configure(text=warn)
        self.app.update_counts()

    def get(self) -> dict:
        return {"id": self.p["id"], "category": self.cat.get(), "version": self.ver.get(),
                "show_value": bool(self.val.get() and self.p.get("has_value"))}


class App(tk.Tk):
    def __init__(self, preselect: Optional[str] = None):
        try:  # own taskbar identity (otherwise Windows shows the generic Python icon)
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DealDeckStudio.App")
        except Exception:
            pass
        super().__init__()
        self.title(APP_NAME)
        try:  # window + taskbar icon (also inherited by every dialog)
            self.iconbitmap(default=str(ASSETS / "app_icon.ico"))
        except Exception:
            pass
        self.geometry(f"{min(1360, self.winfo_screenwidth() - 40)}x{min(820, max(560, self.winfo_screenheight() - 110))}+10+10")
        self.minsize(980, 560)
        self.rows: List[Row] = []
        self.audience = tk.StringVar(value="")
        self.client = tk.StringVar()
        self.save_defaults = tk.BooleanVar(value=False)
        self._state = None
        self.data: Optional[dict] = None
        self._busy = False
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass

        # ---- brand header
        hdr = tk.Frame(self, bg=NAVY, padx=14, pady=8)
        hdr.pack(fill="x")
        try:
            self._logo = tk.PhotoImage(file=str(ASSETS / "app_icon_48.png"))
            tk.Label(hdr, image=self._logo, bg=NAVY).pack(side="left", padx=(0, 12))
        except Exception:
            pass
        tk.Label(hdr, text=APP_NAME, bg=NAVY, fg="white", font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(hdr, text=APP_TAGLINE, bg=NAVY, fg="#B0BEC5", font=("Segoe UI", 10)).pack(side="left", padx=16, pady=(6, 0))
        # the two things this window does
        self.mode = tk.StringVar(value="gen")
        self.mode_btns = {}
        mbox = tk.Frame(hdr, bg="#27507F", padx=3, pady=3)
        mbox.pack(side="right")
        for val, txt in (("gen", "Generate decks"), ("review", "Review & discuss")):
            b = tk.Radiobutton(mbox, text=txt, value=val, variable=self.mode, indicatoron=False, command=self.set_mode, padx=18, pady=5,
                               font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2", selectcolor="#FFFFFF",
                               activebackground="#FFFFFF", activeforeground=NAVY)
            b.pack(side="left", padx=1)
            self.mode_btns[val] = b
        self._recolor_mode()

        # ---- step 1: audience
        s1 = tk.Frame(self, padx=14, pady=10)
        s1.pack(fill="x")
        self.s1, self.hdr = s1, hdr
        tk.Label(s1, text="1.  This presentation is for:", font=("Segoe UI", 11, "bold")).pack(side="left")
        cfg = core.load_config()["audiences"]
        for name, a in cfg.items():
            tk.Radiobutton(s1, text=a["label"], value=name, variable=self.audience, font=("Segoe UI", 11),
                           indicatoron=False, padx=18, pady=5, selectcolor="#BBDEFB", command=self.load_audience
                           ).pack(side="left", padx=(12, 0))
        ttk.Button(s1, text="Replace base deck…", command=self.replace_base).pack(side="right")
        tk.Button(s1, text="Manage projects…", command=self.open_manager, relief="raised", padx=10, pady=1,
                  bg="#E3F2FD", font=("Segoe UI", 9, "bold")).pack(side="right", padx=(8, 0))
        self.tag_btn = tk.Button(s1, text="Tag new slides…", command=self.open_tagger, relief="groove", padx=8)
        self.tag_btn.pack(side="right", padx=8)
        ttk.Button(s1, text="Refresh", command=self.refresh).pack(side="right")

        self.gen_view = tk.Frame(self)  # 'Generate decks' (steps 2-3, list, footer)
        self.gen_view.pack(fill="both", expand=True)
        self.desk_view = tk.Frame(self)  # 'Review & discuss' (the Project Desk)
        self.desk_panel = None
        self._leadmap = None

        # ---- step 2: client
        s2 = tk.Frame(self.gen_view, padx=14, pady=2)
        s2.pack(fill="x")
        tk.Label(s2, text="2.  Client / recipient name:", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Entry(s2, textvariable=self.client, width=36, font=("Segoe UI", 11)).pack(side="left", padx=10)
        ttk.Button(s2, text="Load saved selection", command=self.load_saved).pack(side="left")

        # ---- step 3: projects
        s3 = tk.Frame(self.gen_view, padx=14, pady=6)
        s3.pack(fill="x")
        tk.Label(s3, text="3.  Choose projects", font=("Segoe UI", 11, "bold")).pack(side="left")
        for txt, fn in (("Select all", lambda: self.set_all_show(True)), ("Select none", lambda: self.set_all_show(False)),
                        ("All Named", lambda: self.set_all_version("Named")), ("All Unnamed", lambda: self.set_all_version("Unnamed")),
                        ("Value on", lambda: self.set_all_value(True)), ("Value off", lambda: self.set_all_value(False)),
                        ("Reset to Excel defaults", self.reset_defaults)):
            ttk.Button(s3, text=txt, command=fn).pack(side="left", padx=(8, 0))

        # ---- filter bar
        self.sort_keys: list = []
        self.f_sector, self.f_country = tk.StringVar(value=lu.ALL), tk.StringVar(value=lu.ALL)
        self.f_cat, self.f_text = tk.StringVar(value=lu.ALL), tk.StringVar()
        self.f_source, self.source_filter = tk.StringVar(value=lu.ALL), []
        self.f_lead = tk.StringVar(value=lu.ALL)
        self.f_model = tk.StringVar(value=lu.ALL)
        fb = tk.Frame(self.gen_view, padx=14, pady=2)
        fb.pack(fill="x")
        tk.Label(fb, text="Find:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.cb_sector = ttk.Combobox(fb, textvariable=self.f_sector, state="readonly", width=17)
        self.cb_country = ttk.Combobox(fb, textvariable=self.f_country, state="readonly", width=13)
        cb_cat = ttk.Combobox(fb, textvariable=self.f_cat, values=[lu.ALL] + core.CATEGORY_ORDER, state="readonly", width=8)
        self.cb_source = ttk.Combobox(fb, textvariable=self.f_source, state="readonly", width=19)
        cb_lead = ttk.Combobox(fb, textvariable=self.f_lead, values=[lu.ALL, "RB", "JT", "SS", "Unassigned"], state="readonly", width=9)
        for lbl, cb in (("Lead", cb_lead), ("Sector", self.cb_sector), ("Country", self.cb_country), ("Category", cb_cat), ("Source", self.cb_source)):
            tk.Label(fb, text=lbl).pack(side="left", padx=(10, 2))
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        self.cb_source.bind("<<ComboboxSelected>>", self._source_picked)
        tk.Label(fb, text="Model").pack(side="left", padx=(10, 2))
        self.cb_model = MultiPick(fb, self.f_model, modelnames.ORDER, width=10, empty=lu.ALL)
        self.cb_model.pack(side="left")
        self.f_model.trace_add("write", lambda *a: self.render())
        tk.Label(fb, text="Search").pack(side="left", padx=(10, 2))
        ttk.Entry(fb, textvariable=self.f_text, width=13).pack(side="left")
        self.f_text.trace_add("write", lambda *a: self.render())
        ttk.Button(fb, text="Clear", command=self.clear_filters).pack(side="left", padx=8)
        ttk.Button(fb, text="Deck order", command=self.reset_sort).pack(side="left")
        tk.Button(fb, text="Sources…", command=self.open_sources, relief="raised", padx=8, bg="#E3F2FD",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 0))
        self.shown_lbl = tk.Label(fb, text="", fg="#546E7A")
        self.shown_lbl.pack(side="right")
        tk.Label(self.gen_view, text=lu.HINT, anchor="w", padx=14, fg="#78909C", font=("Segoe UI", 9)).pack(fill="x")

        head = tk.Frame(self.gen_view, padx=14, bg=NAVY)
        head.pack(fill="x", padx=14)
        self.heads = {}
        for c, (col, t, w) in enumerate((("sr", "Sr.", 4), ("show", "Show", 5), ("name", "Project", 1), ("cat", "Category", 10),
                                          ("ver", "Version", 11), ("val", "Value", 6), ("country", "Country", 15),
                                          ("sector", "Sector", 20), ("source", "Source / Origination", 24), (None, "Check", 22))):
            lab = tk.Label(head, text=t, fg="white", bg=NAVY, font=("Segoe UI", 9, "bold"), anchor="w", width=w,
                           cursor="hand2" if col else "")
            lab.grid(row=0, column=c, sticky="nsew", padx=3, pady=4)
            if col:
                lab.bind("<Button-1>", lambda e, col=col: self.sort_by(col))
                self.heads[col] = (lab, t)
        head.grid_columnconfigure(2, weight=1)

        body = tk.Frame(self.gen_view)
        body.pack(fill="both", expand=True, padx=14)
        self.canvas = tk.Canvas(body, highlightthickness=0, bg="white")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="white")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.placeholder = tk.Label(self.inner, text="\n\nChoose who this presentation is for (step 1) to see the projects.",
                                    font=("Segoe UI", 12), fg="#78909C", bg="white")
        self.placeholder.pack(pady=40, padx=40)

        # ---- footer
        foot = tk.Frame(self.gen_view, padx=14, pady=8)
        foot.pack(fill="x")
        self.counts = tk.Label(foot, text="", font=("Segoe UI", 10, "bold"), anchor="w")
        self.counts.pack(side="left")
        self.gen = tk.Button(foot, text="Generate deck", font=("Segoe UI", 12, "bold"), bg="#1565C0", fg="white",
                             activebackground="#0D47A1", activeforeground="white", padx=24, pady=6, relief="flat",
                             command=self.generate, state="disabled")
        self.gen.pack(side="right")
        ttk.Button(foot, text="Open output folder", command=self.open_output).pack(side="right", padx=10)
        ttk.Button(foot, text="Print / PDF list…", command=self.print_list).pack(side="right")
        ttk.Checkbutton(foot, text="Remember these choices as the Excel defaults", variable=self.save_defaults).pack(side="right", padx=10)
        self.status = tk.Label(self.gen_view, text="", anchor="w", fg="#546E7A", padx=14, font=("Segoe UI", 9))
        self.status.pack(fill="x")

        # footer must stay visible on short screens: re-pack bottom-up, body last (it takes the leftover space)
        self.status.pack_forget(); foot.pack_forget(); body.pack_forget()
        self.status.pack(side="bottom", fill="x")
        foot.pack(side="bottom", fill="x")
        body.pack(fill="both", expand=True, padx=14)

        if preselect and preselect in cfg:
            self.audience.set(preselect)
            self.after(100, self.load_audience)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.audience.trace_add("write", lambda *a: self._aud_changed())
        if T.ui_get().get("mode") == "review":
            self.mode.set("review")
            self.after(250, self.set_mode)
        self.after(3000, self._poll)

    # ------------------------------------------------------------------ helpers
    def _aud_changed(self):
        self._leadmap = None
        if self.desk_panel is not None and self.audience.get():
            self.desk_panel.aud = self.audience.get()
            if self.mode.get() == "review":
                self.desk_panel.reload()

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def set_status(self, msg: str):
        self.status.configure(text=msg)
        self.update_idletasks()

    def busy(self, on: bool):
        self._busy = on
        self.configure(cursor="watch" if on else "")
        self.update_idletasks()

    def clear_rows(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = []

    def load_audience(self, preserve: bool = False):
        aud = self.audience.get()
        if not aud:
            return
        prev = {r.p["id"]: (r.show.get(), r.cat.get(), r.ver.get(), r.val.get()) for r in self.rows} if preserve else {}
        scroll = self.canvas.yview()[0] if preserve else 0
        self.busy(True)
        self.set_status(f"Reading {aud} base deck…")
        try:
            self.data = core.load_projects(aud)
        except core.DeckError as exc:
            self.busy(False)
            self.clear_rows()
            self.gen.configure(state="disabled")
            messagebox.showerror("Cannot load " + aud, str(exc))
            self.set_status("")
            return
        except Exception as exc:
            self.busy(False)
            messagebox.showerror("Unexpected error", f"{exc}\n\n{traceback.format_exc()[-800:]}")
            return
        self.clear_rows()
        for i, p in enumerate(self.data["projects"]):
            self.rows.append(Row(self, self.inner, i, p))
        self.cb_sector.configure(values=[lu.ALL] + lu.distinct(self.data["projects"], "sector"))
        self.cb_country.configure(values=[lu.ALL] + lu.distinct(self.data["projects"], "country"))
        self.cb_source.configure(values=[lu.ALL, lu.NO_SOURCE] + lu.distinct_sources(self.data["projects"]))
        for var, fld in ((self.f_sector, "sector"), (self.f_country, "country")):
            if var.get() not in [lu.ALL] + lu.distinct(self.data["projects"], fld):
                var.set(lu.ALL)
        added, kept = [], 0
        if preserve:  # keep what you had ticked / chosen; brand-new projects arrive UNticked and flagged
            for r in self.rows:
                if r.p["id"] in prev:
                    sh, ca, ve, va = prev[r.p["id"]]
                    r.show.set(sh)
                    r.cat.set(ca)
                    if ve in r.versions:
                        r.ver.set(ve)
                    r.val.set(va and bool(r.p.get("has_value")))
                    kept += 1
                else:
                    r.show.set(False)
                    r.flag = "★ NEW"
                    added.append(r.p["name"])
                r.refresh()
        removed = [i for i in prev if i not in {r.p["id"] for r in self.rows}]
        self.inner.grid_columnconfigure(2, weight=1)
        self.render()
        self.canvas.yview_moveto(scroll)
        self.gen.configure(state="normal")
        self.busy(False)
        self._state = core.base_state(aud)
        n_sus = len(self.data["scan"].get("suspect", []))
        self.tag_btn.configure(text=f"Tag new slides ({n_sus})" if n_sus else "Tag new slides…",
                               fg="#C62828" if n_sus else "black", font=("Segoe UI", 9, "bold" if n_sus else "normal"))
        n_w = len(self.data["warnings"])
        notes = " | ".join(self.data["notes"])
        msg = f"{len(self.rows)} projects loaded from {Path(self.data['scan']['path']).name}."
        if preserve:
            msg = f"Base deck changed - list refreshed ({len(self.rows)} projects). " + \
                  (f"NEW: {', '.join(added[:4])}{'…' if len(added) > 4 else ''} (unticked). " if added else "") + \
                  (f"REMOVED: {len(removed)}. " if removed else "")
        self.set_status(msg + (f"  {n_w} note(s) about the base deck - see 'Check' column." if n_w else "") + (f"  {notes}" if notes else ""))
        self.update_counts()

    # ------------------------------------------------------------------ sorting / filtering (ticks are never lost)
    def _val(self, r: Row, col: str):
        p = r.p
        return {"show": "0" if r.show.get() else "1", "name": p["name"], "cat": r.cat.get(), "ver": r.ver.get(),
                "val": "0" if r.val.get() else "1", "country": r.country.cget("text"), "sector": p.get("sector", ""),
                "sr": f"{int(p.get('sr') or 0):05d}", "source": p.get("source", "")}[col]

    def sort_by(self, col: str):
        if not self.rows:
            return
        self.sort_keys = lu.toggle_sort(self.sort_keys, col)
        self.render()

    def reset_sort(self):
        self.sort_keys = []
        self.render()

    def clear_filters(self):
        self.f_sector.set(lu.ALL)
        self.f_country.set(lu.ALL)
        self.f_cat.set(lu.ALL)
        self.f_lead.set(lu.ALL)
        self.f_model.set(lu.ALL)
        self.f_text.set("")
        self.set_source_filter([])
        self.render()

    def set_source_filter(self, sources):
        """Filter the list to projects of these sources (called by the Sources window or the Source box)."""
        self.source_filter = list(sources)
        self.f_source.set(lu.source_label(self.source_filter))
        self.render()

    def _source_picked(self, _e=None):
        v = self.f_source.get()
        self.set_source_filter([] if v == lu.ALL else [v])

    def print_list(self):
        """Print the project list exactly as shown (current sort + filters), landscape by default."""
        if not self.rows:
            messagebox.showinfo("Nothing to print", "Choose who the presentation is for (step 1) first.")
            return
        from printing import PrintDialog
        names = {"sr": "Sr.", "show": "Selected", "name": "Project", "cat": "Category", "ver": "Version", "val": "Value",
                 "country": "Country", "sector": "Sector", "source": "Source"}
        self._leadmap = None
        aud = self.audience.get()
        label = core.load_config()["audiences"][aud]["label"]

        def rows(only):
            out = []
            for r in getattr(self, "_vis", self.rows):
                if only and not r.show.get():
                    continue
                p = r.p
                boss = self._leads().get(p["id"]) or "Unassigned"
                out.append({"sr": p.get("sr", ""), "show": "\u2714" if r.show.get() else "", "name": p["name"], "category": r.cat.get(),
                            "version": r.ver.get(), "country": r.country.cget("text"), "lead": boss,
                            "lead_country": f"{boss} \u2014 {r.country.cget('text') or '(no country)'}", "sector": p.get("sector", ""),
                            "source": p.get("source", ""), "model": p.get("model", ""), "check": r.warn.cget("text"), "key": p["id"]})
            return out

        def meta():
            m = [f"Prepared for: {label}" + (f"  \u00b7  Client: {self.client.get().strip()}" if self.client.get().strip() else "")]
            if self.f_lead.get() != lu.ALL:
                m.append("Boss: " + self.f_lead.get())
            if selected(self.f_model):
                m.append("Model: " + ", ".join(selected(self.f_model)))
            m += lu.describe(self.f_sector.get(), self.f_country.get(), self.f_cat.get(), self.source_filter, self.f_text.get(),
                             self.sort_keys, names)
            sel = [r for r in self.rows if r.show.get()]
            m.append(f"{len(sel)} of {len(self.rows)} projects ticked for the deck")
            return m
        PrintDialog(self, {
            "title": "Project list - " + label, "name": "ProjectList_" + aud, "meta": meta, "rows": rows,
            "only_label": "Only the projects I have ticked (Show)",
            "columns": [("sr", "Sr.", True), ("show", "Selected", True), ("name", "Project", True), ("category", "Category", True),
                        ("version", "Version", True), ("country", "Country", True), ("lead", "Boss", True), ("sector", "Sector", True),
                        ("model", "Model", True), ("source", "Source / Origination", False), ("check", "Check", False), ("key", "Key", False)],
            "groups": {"Boss": "lead", "Boss, then Country": "lead_country", "Country": "country", "Sector": "sector",
                       "Category": "category", "Model": "model", "Source": "source"}})

    def open_sources(self):
        aud = self.audience.get()
        if not aud:
            messagebox.showinfo("Choose audience first", "Pick who the presentation is for (step 1) first.")
            return
        from sources_dialog import SourcesDialog
        SourcesDialog(self, aud, on_show=self.set_source_filter)

    def render(self):
        if not self.rows:
            return
        vis = [r for r in self.rows if lu.matches({**r.p, "category": r.cat.get()}, self.f_sector.get(), self.f_country.get(),
                                                  self.f_cat.get(), self.f_text.get(), self.source_filter,
                                                  selected(self.f_model)) and self._lead_ok(r.p)]
        vis = lu.sort_items(vis, self.sort_keys, self._val)
        for r in self.rows:
            r.hide()
        for i, r in enumerate(vis):
            r.place(i)
        for col, (lab, t) in self.heads.items():
            lab.configure(text=lu.heading_text(t, self.sort_keys, col))
        self._vis = vis  # rows in the order shown (used for printing)
        self.shown_lbl.configure(text=f"showing {len(vis)} of {len(self.rows)}")
        self.canvas.yview_moveto(0)
        self.update_counts()

    # ------------------------------------------------------------------ keep in step with the base deck
    def _poll(self):
        """Every 3 s: if the base deck was saved / replaced / tagged, reload the list (once PowerPoint has let go of it)."""
        try:
            aud = self.audience.get()
            if aud and not self._busy and self._state is not None and core.base_state(aud) != self._state:
                if core.base_readable(aud):
                    self.load_audience(preserve=True)
                else:
                    self.set_status("The base deck is being saved / is open - the list will refresh when it is released…")
        except Exception:
            pass
        self.after(3000, self._poll)

    def refresh(self):
        if not self.audience.get():
            return
        self.load_audience(preserve=True)

    def open_manager(self):
        aud = self.audience.get()
        if not aud:
            messagebox.showinfo("Choose audience first", "Pick who the presentation is for (step 1) first.")
            return
        from manage_dialog import ManageDialog
        ManageDialog(self, aud)

    # ------------------------------------------------------------------ Generate decks  <->  Review & discuss
    def _recolor_mode(self):
        for v, b in self.mode_btns.items():
            on = self.mode.get() == v
            b.configure(bg="#FFFFFF" if on else "#27507F", fg=NAVY if on else "#FFFFFF")

    def set_mode(self):
        mode = self.mode.get()
        if mode == "review":
            aud = self.audience.get() or next(iter(core.load_config()["audiences"]))
            if not self.audience.get():
                self.audience.set(aud)
                self.load_audience()
            self.gen_view.pack_forget()
            self.s1.pack_forget()  # the audience row is not needed while reviewing: more room for the Desk
            if self.desk_panel is None:
                from desk_dialog import DeskPanel
                self.desk_panel = DeskPanel(self.desk_view, self, aud)
                self.desk_panel.pack(fill="both", expand=True)
            else:
                self.desk_panel.aud = aud
                self.desk_panel.reload()
            self.desk_view.pack(fill="both", expand=True)
        else:
            if self.desk_panel is not None:
                self.desk_panel.flush()
            self.desk_view.pack_forget()
            self.s1.pack(fill="x", after=self.hdr)
            self.gen_view.pack(fill="both", expand=True)
            self._leadmap = None
            self.render()
        self._recolor_mode()
        d = T.ui_get()
        d["mode"] = mode
        T.ui_set(d)

    def _leads(self) -> dict:
        """project key -> boss (a boss set on the project, else the boss of its country)."""
        if self._leadmap is None:
            geo = {g["country"].lower(): g["lead"] for g in T.geo_list()}
            ov = T.overview()
            self._leadmap = {}
            for q in (self.data or {}).get("projects", []):
                self._leadmap[q["id"]] = ov.get(q["id"], {}).get("lead") or geo.get(T.canonical(q.get("country", "")).lower(), "")
        return self._leadmap

    def _lead_ok(self, p: dict) -> bool:
        want = self.f_lead.get()
        if want in ("", lu.ALL):
            return True
        lead = self._leads()
        lead = lead.get(p["id"], "")
        return (not lead) if want == "Unassigned" else lead == want

    def _on_close(self):
        if self.desk_panel is not None:
            self.desk_panel.flush()
        self.destroy()

    def open_tagger(self):
        aud = self.audience.get()
        if not aud:
            messagebox.showinfo("Choose audience first", "Pick who the presentation is for (step 1) first.")
            return
        TagDialog(self, aud)

    def update_counts(self):
        sel = [r for r in self.rows if r.show.get()]
        if not self.rows:
            self.counts.configure(text="")
            return
        parts = []
        for c in core.CATEGORY_ORDER:
            n = sum(1 for r in sel if r.cat.get() == c)
            if n:
                parts.append(f"{c} {n}")
        un = sum(1 for r in sel if r.ver.get() == "Unnamed")
        nval = sum(1 for r in sel if r.val.get() and r.p.get("has_value"))
        self.counts.configure(text=f"Selected {len(sel)}/{len(self.rows)}   ({' · '.join(parts) or 'none'})   ·   {un} unnamed, {len(sel) - un} named   ·   value shown on {nval}")

    def set_all_show(self, v: bool):
        for r in self.rows:
            r.show.set(v)
        self.update_counts()

    def set_all_version(self, v: str):
        stuck = []
        for r in self.rows:
            if v in r.versions:
                r.ver.set(v)
            else:
                stuck.append(r.p["name"])
            r.refresh()
        if stuck:
            messagebox.showinfo("Some projects have only one version",
                                f"These have no {v.lower()} slide and were left as they are:\n\n  • " + "\n  • ".join(stuck[:15]))

    def set_all_value(self, v: bool):
        for r in self.rows:
            r.val.set(v and bool(r.p.get("has_value")))

    def reset_defaults(self):
        for r in self.rows:
            r.show.set(r.p["include"])
            r.cat.set(r.p["category"])
            r.val.set(False)
            v = r.p["version"]
            r.ver.set(v if v in r.versions else r.versions[0])
            r.refresh()

    def selections(self) -> List[dict]:
        return [r.get() for r in self.rows if r.show.get()]

    def load_saved(self):
        aud = self.audience.get()
        if not aud:
            messagebox.showinfo("Choose audience first", "Pick who the presentation is for (step 1) first.")
            return
        pre = core.load_preset(aud, self.client.get().strip() or None) or core.load_preset(aud, None)
        if not pre:
            messagebox.showinfo("Nothing saved yet", "No saved selection found. One is stored automatically each time you generate a deck.")
            return
        chosen = {s["id"]: s for s in pre.get("selections", [])}
        for r in self.rows:
            s = chosen.get(r.p["id"])
            r.show.set(bool(s))
            if s:
                if core.norm_category(s.get("category")):
                    r.cat.set(core.norm_category(s["category"]))
                v = core.norm_version(s.get("version"))
                if v in r.versions:
                    r.ver.set(v)
                r.val.set(bool(s.get("show_value")) and bool(r.p.get("has_value")))
            r.refresh()
        if not self.client.get().strip() and pre.get("client"):
            self.client.set(pre["client"])
        self.set_status(f"Loaded selection saved {pre.get('saved', '')} for {pre.get('client', '')}")

    def replace_base(self):
        aud = self.audience.get()
        if not aud:
            messagebox.showinfo("Choose audience first", "Pick which audience's base deck you want to replace (step 1) first.")
            return
        f = filedialog.askopenfilename(title=f"Choose the new {aud} base deck", filetypes=[("PowerPoint", "*.pptx")])
        if not f:
            return
        try:
            scan = core.scan_base(Path(f))
            if not scan["projects"]:
                raise core.DeckError("This deck has no project slides tagged with 'ID: ...' in the speaker notes, so nothing "
                                     "could be selected from it.\nSee HOW_TO_TAG_IN_PPTX.txt.")
            n_pair = sum(1 for p in scan["projects"] if p["slides"]["named"] and p["slides"]["unnamed"])
            msg = (f"Replace the {aud} base deck with:\n{f}\n\n{len(scan['projects'])} projects "
                   f"({n_pair} with named + unnamed versions), {scan['n_slides']} slides.\n"
                   + (f"\n{len(scan['warnings'])} note(s):\n  • " + "\n  • ".join(scan["warnings"][:6]) + "\n" if scan["warnings"] else "")
                   + "\nThe current base deck is archived first. Continue?")
            if not messagebox.askyesno("Replace base deck", msg):
                return
            self.busy(True)
            core.replace_base(aud, f, log=lambda m: None)
        except core.DeckError as exc:
            self.busy(False)
            messagebox.showerror("Not replaced - nothing was changed", str(exc))
            return
        self.busy(False)
        messagebox.showinfo("Base deck replaced", "Done. The previous deck was archived in base\\_archive.\nThe project list has been refreshed.")
        self.load_audience()

    def open_output(self):
        core.OUTPUT_DIR.mkdir(exist_ok=True)
        try:
            core.os_open(core.OUTPUT_DIR)
        except Exception as exc:
            messagebox.showerror("Cannot open folder", str(exc))

    def generate(self):
        if self._busy:
            return
        aud = self.audience.get()
        client = " ".join(self.client.get().split())
        sel = self.selections()
        if not aud:
            messagebox.showwarning("Audience", "Choose who the presentation is for (step 1).")
            return
        if not client:
            messagebox.showwarning("Client name", "Please enter the client / recipient name (step 2).")
            return
        if not sel:
            messagebox.showwarning("No projects", "Tick at least one project.")
            return
        problems = []
        for r in self.rows:
            if r.show.get() and r.ver.get() == "Unnamed" and r.p["leaks"]:
                problems.append(f"{r.p['name']}  ->  {', '.join(r.p['leaks'])}")
        if problems and not messagebox.askyesno(
                "Possible name leak", "These UNNAMED slides still seem to contain identifying words:\n\n  • "
                + "\n  • ".join(problems[:10]) + "\n\nGenerate anyway?", icon="warning"):
            return
        self.busy(True)
        self.set_status("Building the deck…")
        try:
            res = core.generate(aud, client, sel, log=lambda m: None)
            if self.save_defaults.get():
                ok = core.save_defaults(aud, sel, [r.p["id"] for r in self.rows])
                if not ok:
                    res["warnings"].append("Excel defaults NOT saved (projects_registry.xlsx is open in Excel).")
        except core.DeckError as exc:
            self.busy(False)
            self.set_status("")
            messagebox.showerror("Could not build the deck", str(exc))
            return
        except Exception as exc:
            self.busy(False)
            self.set_status("")
            messagebox.showerror("Unexpected error", f"{exc}\n\n{traceback.format_exc()[-900:]}")
            return
        self.busy(False)
        self.set_status(f"Created {res['path']}")
        txt = f"Deck created ({res['n_slides']} slides):\n{res['path']}"
        if res["warnings"]:
            txt += "\n\nPlease note:\n  • " + "\n  • ".join(res["warnings"][:10])
        txt += "\n\nOpen it now?"
        if messagebox.askyesno("Done", txt):
            try:
                core.os_open(res["path"])
            except Exception as exc:
                messagebox.showerror("Cannot open", str(exc))


def main(preselect: Optional[str] = None):
    app = App(preselect)
    app.mainloop()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
