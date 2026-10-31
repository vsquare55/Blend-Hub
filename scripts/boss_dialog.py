#!/usr/bin/env python3
"""Change the boss (RB / JT / SS): for a whole country (the geography distribution) or only for selected projects."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

import deckcore as core
import tracker as T

NAVY = "#1B3A5F"
LEAD_COL = {"RB": "#00796B", "JT": "#5E35B1", "SS": "#E65100"}


class BossDialog(tk.Toplevel):
    def __init__(self, parent, projects: List[dict], on_done: Optional[Callable] = None):
        super().__init__(parent)
        self.projects, self.on_done = projects, on_done
        self.title("Change boss")
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.configure(bg="#FFFFFF")
        geo = {g["country"].lower(): g["lead"] for g in T.geo_list()}
        ov = T.overview()
        self.countries = sorted({p.get("country") or "" for p in projects if p.get("country")})

        hd = tk.Frame(self, bg=NAVY, padx=14, pady=8)
        hd.pack(fill="x")
        tk.Label(hd, text="Change boss", bg=NAVY, fg="white", font=("Segoe UI Semibold", 14)).pack(side="left")
        body = tk.Frame(self, bg="#FFFFFF", padx=16, pady=10)
        body.pack(fill="both", expand=True)
        lines = []
        for p in projects[:7]:
            own = ov.get(p["id"], {}).get("lead")
            geo_lead = geo.get(T.canonical(p.get("country", "")).lower(), "")
            lines.append(f"• {p['name'][:58]}   [{p.get('country') or 'no country'}]   boss: {own or geo_lead or 'unassigned'}"
                         + ("  (set for this project)" if own else ""))
        if len(projects) > 7:
            lines.append(f"• … and {len(projects) - 7} more")
        tk.Label(body, text="\n".join(lines), bg="#FFFFFF", justify="left", anchor="w", fg="#37474F").pack(anchor="w")

        tk.Label(body, text="New boss", bg="#FFFFFF", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 2))
        self.lead = tk.StringVar(value="")
        row = tk.Frame(body, bg="#FFFFFF")
        row.pack(anchor="w")
        for v in T.LEADS:
            tk.Radiobutton(row, text=v, value=v, variable=self.lead, indicatoron=False, padx=18, pady=4, bg="#ECEFF4", selectcolor=LEAD_COL[v],
                           activeforeground="white", font=("Segoe UI", 11, "bold"), relief="flat", bd=0, cursor="hand2",
                           command=self._recolor).pack(side="left", padx=(0, 6))
        self.btns = [w for w in row.winfo_children()]

        tk.Label(body, text="Apply to", bg="#FFFFFF", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 2))
        self.mode = tk.StringVar(value="country" if self.countries else "projects")
        cn = ", ".join(self.countries) or "(no country on these projects)"
        opts = [("country", f"The whole country: {cn} - every project there moves to the new boss (updates the geography distribution)"),
                ("projects", "Only the selected project(s) - the country stays with its boss"),
                ("reset", "Remove the special boss from the selected project(s) - they follow their country again")]
        for v, t in opts:
            tk.Radiobutton(body, text=t, value=v, variable=self.mode, bg="#FFFFFF", anchor="w", justify="left", wraplength=560,
                           state="normal" if (v != "country" or self.countries) else "disabled").pack(anchor="w")
        self.msg = tk.Label(body, text="", bg="#FFFFFF", fg="#C62828", anchor="w")
        self.msg.pack(fill="x", pady=(8, 0))
        f = tk.Frame(self, bg="#FFFFFF", padx=14, pady=10)
        f.pack(fill="x")
        tk.Button(f, text="Apply", command=self.apply, bg="#1565C0", fg="white", relief="flat", padx=18, pady=4, font=("Segoe UI", 10, "bold")).pack(side="right")
        ttk.Button(f, text="Cancel", command=self.destroy).pack(side="right", padx=8)

    def _recolor(self):
        for b, v in zip(self.btns, T.LEADS):
            b.configure(fg="white" if self.lead.get() == v else "#22293A")

    def apply(self):
        mode, lead = self.mode.get(), self.lead.get()
        if mode != "reset" and not lead:
            self.msg.configure(text="Choose the new boss (RB, JT or SS) first.")
            return
        try:
            if mode == "country":
                for c in self.countries:
                    T.set_geo(c, lead)
                done = f"{', '.join(self.countries)} now belongs to {lead}."
            elif mode == "projects":
                for p in self.projects:
                    T.set_proj(p["id"], lead=lead)
                done = f"{len(self.projects)} project(s) now have {lead} as boss."
            else:
                for p in self.projects:
                    T.set_proj(p["id"], lead="")
                done = f"{len(self.projects)} project(s) follow their country's boss again."
        except core.DeckError as exc:
            self.msg.configure(text=str(exc))
            return
        parent = self.master
        self.destroy()
        if self.on_done:
            self.on_done()
        messagebox.showinfo("Boss changed", done, parent=parent)
