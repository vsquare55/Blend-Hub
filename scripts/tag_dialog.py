#!/usr/bin/env python3
"""
Tag editor: shows EVERY slide of the base deck with its tag; add, change or remove tags (saved into the .pptx).

Rule that keeps this safe: ONLY the fields you change are applied. With several slides selected the form starts
blank ("keep current"), so changing just the category never touches the project key, version or name.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import List

import deckcore as core

KEEP = "(keep current)"
VERS = [KEEP, "Named", "Unnamed", "Same slide for both versions", "Not a project - ignore", "Remove tag"]
CATS = [KEEP, "(none)"] + core.CATEGORY_ORDER
VMAP = {KEEP: "", "Named": "named", "Unnamed": "unnamed", "Same slide for both versions": "single",
        "Not a project - ignore": "ignore", "Remove tag": "remove"}
SHOW = {"named": "Named", "unnamed": "Unnamed", "single": "Both"}
VERLBL = {"named": "Named", "unnamed": "Unnamed", "single": "Same slide for both versions"}
FILTERS = ["All slides", "Untagged only", "Needs attention (★)"]
LAB = {"key": "Project key", "variant": "Version", "category": "Category", "name": "Index name"}
NL = chr(10)


class TagDialog(tk.Toplevel):
    def __init__(self, app, audience: str):
        super().__init__(app)
        self.app, self.aud = app, audience
        self.title("Tag slides  -  every slide of the base deck")
        self.geometry("1100x720")
        self.transient(app)
        self.items: List[dict] = []
        tk.Label(self, justify="left", anchor="w", padx=12, pady=6, wraplength=1060, font=("Segoe UI", 10), text=(
            "Every slide is listed with its current tag. Select slide(s), change ONLY what you want, press Apply - "
            "fields you leave on '(keep current)' / blank are never touched. Tags are written into each slide's speaker notes "
            "inside the base .pptx (permanent; the previous file is backed up in base" + chr(92) + "_archive). "
            "The named slide and the unnamed slide of one project share the SAME key. "
            "★ = looks like a new project slide that is still untagged.")).pack(fill="x")

        bar = tk.Frame(self, padx=12)
        bar.pack(fill="x")
        tk.Label(bar, text="Show:").pack(side="left")
        self.filter = tk.StringVar(value=FILTERS[0])
        cb = ttk.Combobox(bar, textvariable=self.filter, values=FILTERS, state="readonly", width=24)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        ttk.Button(bar, text="Reload from file", command=self.fill).pack(side="left", padx=6)
        self.count = tk.Label(bar, text="", fg="#546E7A")
        self.count.pack(side="left", padx=10)

        cols = ("slide", "status", "key", "version", "category", "title")
        frame = tk.Frame(self, padx=12)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for c, t, w in (("slide", "Slide", 60), ("status", "Status", 120), ("key", "Project key", 210),
                        ("version", "Version", 80), ("category", "Category", 80), ("title", "Title", 520)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w", stretch=(c == "title"))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("sus", foreground="#C62828")
        self.tree.tag_configure("plain", foreground="#78909C")
        self.tree.bind("<<TreeviewSelect>>", self._prefill)

        f = tk.Frame(self, padx=12, pady=8)
        f.pack(fill="x")
        self.key, self.ver = tk.StringVar(), tk.StringVar(value=KEEP)
        self.cat, self.name = tk.StringVar(value=KEEP), tk.StringVar()
        self._base = ("", KEEP, KEEP, "")  # what the form showed at selection time -> detects YOUR edits only
        tk.Label(f, text="Project key (blank = keep):").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.key, width=34).grid(row=0, column=1, padx=6)
        tk.Label(f, text="Version:").grid(row=0, column=2, sticky="w")
        ttk.Combobox(f, textvariable=self.ver, values=VERS, state="readonly", width=28).grid(row=0, column=3, padx=6)
        tk.Label(f, text="Category:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(f, textvariable=self.cat, values=CATS, state="readonly", width=16).grid(row=1, column=1, sticky="w", padx=6)
        tk.Label(f, text="Index name (blank = keep):").grid(row=1, column=2, sticky="w")
        ttk.Entry(f, textvariable=self.name, width=34).grid(row=1, column=3, padx=6, sticky="w")
        ttk.Button(f, text="Apply to selected slides", command=self.apply).grid(row=0, column=4, rowspan=2, padx=12)
        self.summary = tk.Label(self, text="", anchor="w", padx=12, fg="#1565C0", font=("Segoe UI", 9, "bold"))
        self.summary.pack(fill="x")
        self.msg = tk.Label(self, text="", anchor="w", padx=12, fg="#2E7D32", font=("Segoe UI", 9, "bold"))
        self.msg.pack(fill="x")
        for v in (self.key, self.ver, self.cat, self.name):
            v.trace_add("write", lambda *a: self._summary())
        self.fill()

    # ------------------------------------------------------------------
    def fill(self, reselect: List[int] | None = None):
        keep = reselect if reselect is not None else [int(i) for i in self.tree.selection()]
        self.tree.delete(*self.tree.get_children())
        try:
            self.items = core.all_slides(self.aud)
        except core.DeckError as exc:
            messagebox.showerror("Cannot read the base deck", str(exc), parent=self)
            self.destroy()
            return
        mode = self.filter.get()
        shown = 0
        for s in self.items:
            if mode == FILTERS[1] and s["tagged"]:
                continue
            if mode == FILTERS[2] and not s["suspect"]:
                continue
            if s["key"]:
                status = "Project"
            elif s["tagged"]:
                status = "Ignored"
            else:
                status = s["role"].replace(" (dropped)", "")
            tags = ("sus",) if s["suspect"] else (() if s["key"] else ("plain",))
            self.tree.insert("", "end", iid=str(s["num"]), tags=tags, values=(
                ("★ " if s["suspect"] else "") + str(s["num"]), status, s["key"], SHOW.get(s["variant"], ""),
                s["category"], s["title"]))
            shown += 1
        n_tag = sum(1 for s in self.items if s["key"])
        n_sus = sum(1 for s in self.items if s["suspect"])
        self.count.configure(text=f"{len(self.items)} slides  ·  {n_tag} tagged as projects  ·  {n_sus} need attention  ·  showing {shown}")
        sel = [str(n) for n in keep if self.tree.exists(str(n))]
        if sel:
            self.tree.selection_set(sel)
            self.tree.see(sel[0])
        else:
            self._prefill()

    def _prefill(self, _e=None):
        sel = self.tree.selection()
        s = next((x for x in self.items if len(sel) == 1 and str(x["num"]) == sel[0]), None)
        if s and s["key"]:  # one tagged slide: show its current tag (editing = changing these values)
            vals = (s["key"], VERLBL[s["variant"]], s["category"] or "(none)", s["name"])
            self._base = vals
        elif s:  # one untagged slide: suggest a key (counts as an edit), the rest must be chosen
            vals = (s["key_hint"], KEEP, KEEP, "")
            self._base = ("", KEEP, KEEP, "")
        else:  # several slides: blank form, ONLY what you type / choose is applied (to each slide)
            vals = ("", KEEP, KEEP, "")
            self._base = vals
        self.key.set(vals[0])
        self.ver.set(vals[1])
        self.cat.set(vals[2])
        self.name.set(vals[3])
        self._summary()

    def _changes(self) -> dict:
        """Only the fields YOU changed compared with what the form showed at selection time."""
        ch = {}
        k = self.key.get().strip()
        if k and k != self._base[0]:
            ch["key"] = k
        if self.ver.get() != self._base[1] and self.ver.get() != KEEP:
            ch["variant"] = VMAP[self.ver.get()]
        if self.cat.get() != self._base[2] and self.cat.get() != KEEP:
            ch["category"] = "-" if self.cat.get() == "(none)" else self.cat.get()
        nm = self.name.get().strip()
        if nm and nm != self._base[3]:
            ch["name"] = nm
        return ch

    def _summary(self):
        sel = self.tree.selection()
        ch = self._changes()
        if not sel:
            self.summary.configure(text="")
        elif not ch:
            self.summary.configure(text=f"{len(sel)} slide(s) selected - nothing to change yet.", fg="#78909C")
        else:
            txt = ", ".join(f"{LAB[k]} → {v}" for k, v in ch.items())
            self.summary.configure(text=f"Apply will change ONLY: {txt}  on {len(sel)} slide(s); everything else stays as it is.", fg="#1565C0")

    def apply(self):
        sel = [int(i) for i in self.tree.selection()]
        if not sel:
            messagebox.showinfo("Select slides", "Select one or more slides in the list first.", parent=self)
            return
        ch = self._changes()
        if not ch:
            messagebox.showinfo("Nothing to change", "You have not changed anything. Change the key, version, category or name first.", parent=self)
            return
        variant = ch.get("variant", "")
        by = {s["num"]: s for s in self.items}
        if len(sel) > 1 or "key" in ch:
            what = NL.join(f"   {LAB[k]}  →  {v}" for k, v in ch.items())
            keep = NL.join(f"   {LAB[k]}: unchanged" for k in LAB if k not in ch)
            if not messagebox.askyesno(
                    "Apply to " + str(len(sel)) + " slide(s)?",
                    "This will change on EACH of the " + str(len(sel)) + " selected slides:" + NL + what + NL + NL + keep + NL + NL + "Continue?",
                    parent=self):
                return
        if "key" in ch and variant not in ("ignore", "remove"):
            newkey = core.norm_id(ch["key"])
            renamed = sorted({by[n]["key"] for n in sel if by[n]["key"] and by[n]["key"] != newkey})
            if renamed and not messagebox.askyesno(
                    "Rename project?", "You are changing the key of an already-tagged project (" + ", ".join(renamed) + ")." + NL + NL +
                    "That makes it a different project in the app: its Excel details are not carried over. Tag the project's OTHER "
                    "version slide with the same new key too." + NL + NL + "Continue?", parent=self):
                return
        if variant == "remove" and any(by[n]["key"] for n in sel) and not messagebox.askyesno(
                "Remove tag?", "These slide(s) will stop being project slides." + NL + NL + "Continue?", parent=self):
            return
        assignments = [dict(num=n, **ch) for n in sel]
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            try:
                res = core.tag_slides(self.aud, assignments, log=lambda m: None)
            except core.NeedsConfirm as exc:
                self.configure(cursor="")
                if not messagebox.askyesno("Several slides on one project version?",
                                           str(exc) + NL + NL + "Continue anyway?", icon="warning", parent=self):
                    return
                self.configure(cursor="watch")
                res = core.tag_slides(self.aud, assignments, log=lambda m: None, confirm_multi=True)
        except core.DeckError as exc:
            self.configure(cursor="")
            messagebox.showerror("Not saved", str(exc), parent=self)
            return
        self.configure(cursor="")
        self.msg.configure(text="Saved into the base deck: " + ", ".join(f"{LAB[k]} -> {v}" for k, v in ch.items())
                                + f" on slide(s) {sel}.   Backup: {Path(res['archived']).name}")
        self.fill(reselect=sel)
        self.app.load_audience(preserve=True)
