#!/usr/bin/env python3
"""Sources window: who brought which projects - view, filter the main list by source, edit, rename / merge, report."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, List, Optional

import deckcore as core
import listutil as lu
import sourcesheet as ss
import srcmgr

NL = chr(10)


class SourcesDialog(tk.Toplevel):
    def __init__(self, app, audience: str, on_show: Optional[Callable[[List[str]], None]] = None):
        super().__init__(app)
        self.app, self.aud, self.on_show = app, audience, on_show
        self.title("Sources / Origination - who brought which projects")
        self.geometry("1240x760")
        self.transient(app)
        self.rows: List[dict] = []
        self.projects: List[dict] = []
        tk.Label(self, anchor="w", justify="left", padx=12, pady=6, fg="#37474F", font=("Segoe UI", 10), wraplength=1200, text=(
            "A source is the person, minister, partner or influential contact who brought a project. Select one or SEVERAL sources "
            "to see their projects below, or press 'Show in main list' to filter the main project list by them. Sources are for your "
            "decisions only - they never appear in a generated deck.")).pack(fill="x")

        bar = tk.Frame(self, padx=12)
        bar.pack(fill="x")
        B = lambda t, c: ttk.Button(bar, text=t, command=c)  # noqa: E731
        B("Show in main list", self.show_in_main).pack(side="left", padx=(0, 6))
        B("Edit details…", self.edit_details).pack(side="left", padx=3)
        B("Rename / merge…", self.rename).pack(side="left", padx=3)
        B("＋ Add source…", self.add_source).pack(side="left", padx=3)
        B("Export report (Excel)", self.export).pack(side="left", padx=3)
        B("Print / PDF\u2026", self.print_list).pack(side="left", padx=3)
        tk.Label(bar, text="   Search").pack(side="left")
        self.q = tk.StringVar()
        ttk.Entry(bar, textvariable=self.q, width=22).pack(side="left", padx=4)
        self.q.trace_add("write", lambda *a: self.fill())
        self.count = tk.Label(bar, text="", fg="#546E7A")
        self.count.pack(side="right")

        cols = ("name", "type", "country", "n", "active", "bip", "hold", "closed", "role")
        top = tk.Frame(self, padx=12)
        top.pack(fill="both", expand=True, pady=4)
        self.tree = ttk.Treeview(top, columns=cols, show="headings", selectmode="extended", height=11)
        for c, t, w in (("name", "Source", 210), ("type", "Type", 140), ("country", "Country", 95), ("n", "Projects", 62),
                        ("active", "Active", 50), ("bip", "BIP", 45), ("hold", "Hold", 45), ("closed", "Closed", 50),
                        ("role", "Role / description", 520)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w", stretch=(c == "role"))
        sb = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("none", foreground="#C62828")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.fill_projects())

        mid = tk.Frame(self, padx=12)
        mid.pack(fill="x")
        self.ptitle = tk.Label(mid, text="Projects of the selected source(s)", font=("Segoe UI", 10, "bold"), anchor="w")
        self.ptitle.pack(side="left")
        ttk.Button(mid, text="Edit source(s) of selected projects…", command=self.edit_project_sources).pack(side="right")

        bot = tk.Frame(self, padx=12)
        bot.pack(fill="both", expand=True, pady=4)
        pc = ("sr", "name", "country", "sector", "cat", "src")
        self.ptree = ttk.Treeview(bot, columns=pc, show="headings", selectmode="extended", height=9)
        for c, t, w in (("sr", "Sr.", 45), ("name", "Project", 430), ("country", "Country", 110), ("sector", "Sector", 150),
                        ("cat", "Category", 70), ("src", "All sources of this project", 330)):
            self.ptree.heading(c, text=t)
            self.ptree.column(c, width=w, anchor="w", stretch=(c == "name"))
        sb2 = ttk.Scrollbar(bot, orient="vertical", command=self.ptree.yview)
        self.ptree.configure(yscrollcommand=sb2.set)
        self.ptree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.msg = tk.Label(self, text="", anchor="w", padx=12, fg="#2E7D32", font=("Segoe UI", 9, "bold"))
        self.msg.pack(fill="x")
        self.fill()

    # ------------------------------------------------------------------
    def load(self):
        data = core.load_projects(self.aud)
        self.projects = data["projects"]
        self.rows = srcmgr.breakdown(self.projects, data.get("sources_info", []))

    def fill(self, reselect: Optional[List[str]] = None):
        keep = reselect if reselect is not None else list(self.tree.selection())
        try:
            self.load()
        except core.DeckError as exc:
            messagebox.showerror("Cannot read the data", str(exc), parent=self)
            self.destroy()
            return
        self.tree.delete(*self.tree.get_children())
        no_src = [p for p in self.projects if not p["sources"]]
        cats = {c: sum(1 for p in no_src if p["category"] == c) for c in core.CATEGORY_ORDER}
        self.tree.insert("", 0, iid=lu.NO_SOURCE, tags=("none",), values=(
            lu.NO_SOURCE, "", "", len(no_src), cats["Active"], cats["BIP"], cats["Hold"], cats["Closed"],
            "Projects where no source is recorded - fill these in to make better decisions"))
        t = self.q.get().strip().lower()
        shown = 0
        for r in self.rows:
            if t and t not in (r["name"] + " " + r["role"] + " " + r["country"] + " " + r["type"]).lower():
                continue
            self.tree.insert("", "end", iid=r["name"], values=(r["name"], r["type"], r["country"], r["count"], r["cats"]["Active"],
                                                                  r["cats"]["BIP"], r["cats"]["Hold"], r["cats"]["Closed"], r["role"]))
            shown += 1
        with_src = len(self.projects) - len(no_src)
        self.count.configure(text=f"{len(self.rows)} sources  ·  {with_src} of {len(self.projects)} projects have a source  ·  {len(no_src)} without")
        sel = [k for k in keep if self.tree.exists(k)]
        if sel:
            self.tree.selection_set(sel)
        self.fill_projects()

    def selected(self) -> List[str]:
        return [s for s in self.tree.selection()]

    def selected_names(self) -> List[str]:
        return [s for s in self.selected() if s != lu.NO_SOURCE]

    def fill_projects(self):
        self.ptree.delete(*self.ptree.get_children())
        sel = self.selected()
        if not sel:
            self.ptitle.configure(text="Projects of the selected source(s)  -  select a source above")
            return
        ps = [p for p in self.projects if lu.matches(p, lu.ALL, lu.ALL, lu.ALL, "", sel)]
        for p in ps:
            self.ptree.insert("", "end", iid=p["id"], values=(p["sr"], p["name"], p["country"], p["sector"], p["category"], " / ".join(p["sources"])))
        self.ptitle.configure(text=f"{len(ps)} project(s) of: " + ", ".join(sel[:4]) + ("…" if len(sel) > 4 else ""))

    # ------------------------------------------------------------------ actions
    def show_in_main(self):
        sel = self.selected()
        if not sel:
            messagebox.showinfo("Select sources", "Select one or more sources first.", parent=self)
            return
        if self.on_show:
            self.on_show(sel)
        self.msg.configure(text="The main project list is now filtered to: " + ", ".join(sel[:5]))

    def _run(self, fn, *a, **k):
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            return fn(*a, **k)
        except core.DeckError as exc:
            messagebox.showerror("Not done", str(exc), parent=self)
            return None
        finally:
            self.configure(cursor="")

    def edit_details(self):
        names = self.selected_names()
        if len(names) != 1:
            messagebox.showinfo("One source", "Select exactly one source to edit its role, type and country.", parent=self)
            return
        r = next((x for x in self.rows if x["name"] == names[0]), None) or {"name": names[0], "role": "", "type": "", "country": ""}
        win = tk.Toplevel(self)
        win.title("Edit source - " + r["name"])
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Who is this person / partner? What influence do they have?", anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 2))
        role = tk.Text(win, width=70, height=5, wrap="word", font=("Segoe UI", 10))
        role.grid(row=1, column=0, columnspan=2, padx=12)
        role.insert("1.0", r["role"])
        typ, ctry = tk.StringVar(value=r["type"]), tk.StringVar(value=r["country"])
        tk.Label(win, text="Type").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(win, textvariable=typ, values=[""] + ss.TYPES, state="readonly", width=30).grid(row=2, column=1, sticky="w")
        tk.Label(win, text="Country").grid(row=3, column=0, sticky="w", padx=12)
        ttk.Entry(win, textvariable=ctry, width=33).grid(row=3, column=1, sticky="w", pady=2)

        def save():
            ch = {}
            if role.get("1.0", "end").strip() != r["role"]:
                ch["role"] = role.get("1.0", "end").strip()
            if typ.get() != r["type"]:
                ch["type"] = typ.get()
            if ctry.get().strip() != r["country"]:
                ch["country"] = ctry.get().strip()
            if ch and not self._run(srcmgr.update_source_info, r["name"], **ch):
                return
            win.destroy()
            self.msg.configure(text="Saved details of " + r["name"] + ("." if ch else " (nothing changed)."))
            self.fill(reselect=[r["name"]])
            self.app.load_audience(preserve=True)
        f = tk.Frame(win, pady=10)
        f.grid(row=4, column=0, columnspan=2, sticky="e", padx=12)
        ttk.Button(f, text="Cancel", command=win.destroy).pack(side="right", padx=6)
        ttk.Button(f, text="Save", command=save).pack(side="right")

    def rename(self):
        names = self.selected_names()
        if len(names) != 1:
            messagebox.showinfo("One source", "Select exactly one source to rename or merge.", parent=self)
            return
        new = simpledialog.askstring("Rename / merge", "New name for '" + names[0] + "':" + NL + NL +
                                     "If the new name is an existing source, the two are MERGED into one.",
                                     initialvalue=names[0], parent=self)
        new = " ".join((new or "").split())
        if not new or new == names[0]:
            return
        exists = any(r["name"].lower() == new.lower() and r["name"] != names[0] for r in self.rows)
        if exists and not messagebox.askyesno("Merge?", f"'{new}' already exists. Merge '{names[0]}' into it?" + NL + NL +
                                              "Every project of both will then show '" + new + "'.", parent=self):
            return
        n = self._run(srcmgr.rename_source, names[0], new)
        if n is not None:
            self.msg.configure(text=f"'{names[0]}' is now '{new}' on {n} project(s).")
            self.fill(reselect=[new])
            self.app.load_audience(preserve=True)

    def add_source(self):
        name = simpledialog.askstring("Add source", "Name of the new source (person / minister / partner):", parent=self)
        if name and name.strip():
            if self._run(srcmgr.update_source_info, name.strip()):
                self.msg.configure(text="Added '" + name.strip() + "'. Use 'Edit details' to describe them, then assign projects.")
                self.fill(reselect=[" ".join(name.split())])

    def edit_project_sources(self):
        pids = list(self.ptree.selection())
        if not pids:
            messagebox.showinfo("Select projects", "Select one or more projects in the lower list first.", parent=self)
            return
        win = tk.Toplevel(self)
        win.title("Edit the source(s) of " + str(len(pids)) + " project(s)")
        win.transient(self)
        win.grab_set()
        mode = tk.StringVar(value="add")
        for v, t in (("add", "ADD these source(s) to the project(s)"), ("remove", "REMOVE these source(s) from the project(s)"),
                     ("replace", "REPLACE all sources of the project(s) with these")):
            tk.Radiobutton(win, text=t, value=v, variable=mode, anchor="w").pack(anchor="w", padx=14, pady=1)
        tk.Label(win, text="Source name(s) - separate several with  /  :", anchor="w").pack(anchor="w", padx=14, pady=(8, 0))
        names = tk.StringVar()
        ttk.Combobox(win, textvariable=names, values=[r["name"] for r in self.rows], width=60).pack(padx=14, pady=4)

        def go():
            srcs = ss.split_sources(names.get())
            if not srcs and mode.get() != "replace":
                messagebox.showinfo("Name needed", "Type or choose at least one source.", parent=win)
                return
            if mode.get() == "replace" and not srcs and not messagebox.askyesno("Clear sources?", "This will leave the project(s) with NO source. Continue?", parent=win):
                return
            win.destroy()
            n = self._run(srcmgr.set_project_sources, self.aud, pids, srcs, mode.get())
            if n is not None:
                self.msg.configure(text=f"Updated the source(s) of {n} project(s).")
                self.fill()
                self.app.load_audience(preserve=True)
        f = tk.Frame(win, pady=10)
        f.pack(fill="x", padx=14)
        ttk.Button(f, text="Cancel", command=win.destroy).pack(side="right", padx=6)
        ttk.Button(f, text="Apply", command=go).pack(side="right")

    def print_list(self):
        from printing import PrintDialog

        def rows(only):
            ids = [i for i in self.tree.get_children() if (not only) or i in set(self.tree.selection())]
            return [{"name": self.tree.set(i, "name"), "type": self.tree.set(i, "type"), "country": self.tree.set(i, "country"),
                     "count": self.tree.set(i, "n"), "active": self.tree.set(i, "active"), "bip": self.tree.set(i, "bip"),
                     "hold": self.tree.set(i, "hold"), "closed": self.tree.set(i, "closed"), "role": self.tree.set(i, "role")} for i in ids]
        PrintDialog(self, {
            "title": "Sources / origination", "name": "Sources", "meta": lambda: [self.count.cget("text")], "rows": rows,
            "only_label": "Only the sources I have selected",
            "columns": [("name", "Source", True), ("type", "Type", True), ("country", "Country", True), ("count", "Projects", True),
                        ("active", "Active", True), ("bip", "BIP", True), ("hold", "Hold", True), ("closed", "Closed", False),
                        ("role", "Role / description", True)],
            "groups": {"Type": "type", "Country": "country"}})

    def export(self):
        out = self._run(srcmgr.export_summary, self.aud)
        if out:
            self.msg.configure(text="Report saved: " + str(out))
            try:
                core.os_open(out)
            except Exception:
                pass
