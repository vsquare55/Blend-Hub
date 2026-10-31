#!/usr/bin/env python3
"""
Optional 'internal status' layer of the Project Desk: shows what the team's Excel file says about each project
(stage, next steps, partners, banks), only after you import that file. Mixed into DeskDialog.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import deckcore as core
import statusfile as sf
import tracker as T

KIND_ORDER = ["Bank / lender", "Investor", "Local partner", "EPC contractor", "Consultant", "Partner"]


class StatusMixin:
    # ------------------------------------------------------------------ data plumbing
    def _ov(self) -> dict:
        """The Desk overview, plus (when a status file is loaded) the stage the file gives for each matched project."""
        ov = T.overview()
        for k, m in getattr(self, "ext", {}).items():
            g = sf.group_rows(m)
            if not g:
                continue
            row = g[0]["main"]["row"]
            f = row["fields"]
            o = ov.setdefault(k, {})
            st = sf.field_text(f.get("stage") or f.get("class") or f.get("status") or "").split("\n")[0]
            o["ext_stage"] = st[:16] or "in file"
            o["ext_conf"] = m["conf"]
        return ov

    def _fstage(self, o: dict) -> str:
        if "ext_conf" not in o:
            return "—" if self.ext_batch else ""
        return o["ext_stage"] + (" ?" if o["ext_conf"] == "possible" else "")

    def _load_ext(self):
        self.ext_batch = T.ext_batch()
        sig = (self.ext_batch["id"] if self.ext_batch else 0, tuple(sorted(p["id"] + p["name"] for p in self.projects)), repr(sorted(T.ext_links().items())))
        if sig != getattr(self, "_ext_sig", None):
            self.ext = sf.current_matches(self.projects) if self.ext_batch else {}
            self._ext_sig = sig
        cols = [c for c in self.heads if c != "fstage" or self.ext_batch]
        self.tree.configure(displaycolumns=cols)
        self._file_label()

    def _show_file_chips(self, on: bool):
        if on == getattr(self, "_chips_on", None):
            return
        self._chips_on = on
        for code in ("infile", "nofile"):
            b = self.view_btns[code]
            if on:
                b.pack(side="left", padx=(5, 0), pady=(0, 6))
            else:
                b.pack_forget()

    def _file_label(self):
        b = self.ext_batch
        if not b:
            self.file_lbl.configure(text="No status file loaded (optional) • header: Status file", fg="#78909C")
            return
        txt, fg = f"Status file: {b['fname']} · imported {b['ts'][:16]}", "#455A64"
        try:
            p = Path(b["path"])
            if p.exists() and p.stat().st_mtime > (b["mtime"] or 0) + 1:
                txt += "   • a newer version of the file is available - Status file > Re-import"
                fg = "#E65100"
        except Exception:
            pass
        self.file_lbl.configure(text=txt, fg=fg)

    def after_ext(self):
        self._load_ext()
        self.ov = self._ov()
        self._file_label()
        self.render()
        self.render_status()

    # ------------------------------------------------------------------ header menu
    def build_status_menu(self, parent):
        mb = tk.Menubutton(parent, text="Status file ▾", bg="#27507F", fg="white", relief="flat", padx=10, cursor="hand2",
                           activebackground="#1E4068", activeforeground="white")
        m = tk.Menu(mb, tearoff=0, postcommand=self._menu_state)
        m.add_command(label="Import status file…", command=self.import_status)
        m.add_command(label="Re-import the last file", command=self.reimport_last)
        m.add_separator()
        m.add_command(label="Last import summary…", command=self.show_last_summary)
        m.add_command(label="Rows in the file that are not in the deck…", command=self.show_unmatched)
        m.add_separator()
        m.add_checkbutton(label="Include hidden sheets when importing", variable=self.inc_hidden)
        m.add_separator()
        m.add_command(label="Remove the imported status data", command=self.clear_status)
        mb.configure(menu=m)
        self._status_menu = m
        mb.pack(side="right", padx=(0, 8))
        return mb

    def _menu_state(self):
        st = "normal" if self.ext_batch else "disabled"
        for i in (1, 3, 4, 8):
            self._status_menu.entryconfigure(i, state=st)

    # ------------------------------------------------------------------ import
    def import_status(self, path: Optional[str] = None):
        if not path:
            b = self.ext_batch
            init = Path.home() / "Downloads"
            if b and Path(b["path"]).parent.exists():
                init = Path(b["path"]).parent
            path = filedialog.askopenfilename(parent=self, title="Choose the team's status file", initialdir=str(init),
                                              filetypes=[("Excel workbook", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if not path:
            return
        self.configure(cursor="watch")
        self.set_status("Reading the status file ...")
        self.update_idletasks()
        try:
            summary = sf.import_file(Path(path), self.projects, bool(self.inc_hidden.get()))
        except core.DeckError as exc:
            messagebox.showinfo("Status file", str(exc), parent=self)
            return
        except PermissionError:
            messagebox.showinfo("Status file", "The file is locked. Close it in Excel (or save a copy) and try again.", parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Status file", f"That file could not be read:\n{exc}", parent=self)
            return
        finally:
            self.configure(cursor="")
        self.reload()
        self.show_import_summary(summary)

    def reimport_last(self):
        b = self.ext_batch
        if not b:
            return
        if not Path(b["path"]).exists():
            messagebox.showinfo("Status file", f"The file is no longer at:\n{b['path']}\n\nChoose it again with 'Import status file'.", parent=self)
            return self.import_status()
        self.import_status(b["path"])

    def clear_status(self):
        if messagebox.askyesno("Remove status data", "Remove the imported status data from the Desk?\n(Your comments, needs and actions are not affected; "
                               "you can import the file again any time.)", parent=self):
            T.ext_clear()
            if self.f_view.get() in ("infile", "nofile"):
                self.f_view.set("all")
            self.reload()

    def _names(self) -> dict:
        return {p["id"]: p["name"] for p in self.all_projects}

    def show_last_summary(self):
        b = self.ext_batch
        if b:
            self.show_import_summary(b["summary"], when=b["ts"][:16], fname=b["fname"])

    def show_import_summary(self, s: dict, when: str = "", fname: str = ""):
        names = self._names()
        dlg = tk.Toplevel(self)
        dlg.title("Status file - import summary")
        dlg.geometry("720x520")
        dlg.transient(self)
        t = tk.Text(dlg, wrap="word", font=("Segoe UI", 10), padx=12, pady=10, relief="flat")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", font=("Segoe UI", 12, "bold"), foreground="#1B3A5F")
        t.tag_configure("k", font=("Segoe UI", 10, "bold"))
        t.tag_configure("m", foreground="#78909C")
        t.insert("end", (f"{fname}  ·  {when}\n" if fname else "Import finished\n"), "h")
        t.insert("end", f"\n{s.get('n_rows', 0)} project rows read from {len(s.get('sheets_used', []))} sheets.\n")
        t.insert("end", f"{s.get('matched', 0)} of {s.get('n_projects', 0)} deck projects found in the file", "k")
        t.insert("end", f"  ({s.get('high', 0)} confident, {s.get('possible', 0)} possible - check these).\n")
        t.insert("end", f"{s.get('n_projects', 0) - s.get('matched', 0)} deck projects are not in the file and show 'no data'.\n")
        if s.get("first"):
            t.insert("end", "\nFirst import - changes will be reported from the next upload onwards.\n", "m")
        for key, title in (("changed", "Status changed since the previous upload"), ("appeared", "New in the file"), ("gone", "No longer in the file")):
            ks = s.get(key) or []
            if ks:
                t.insert("end", f"\n{title} ({len(ks)})\n", "k")
                for k in ks:
                    t.insert("end", f"  • {names.get(k, k)}\n")
        if s.get("sheets_skipped"):
            t.insert("end", "\nSheets not read: " + "; ".join(s["sheets_skipped"]) + "\n", "m")
        t.insert("end", "\nSheets read: " + "; ".join(s.get("sheets_used", [])) + "\n", "m")
        t.configure(state="disabled")
        bt = tk.Frame(dlg, pady=8)
        bt.pack(fill="x")
        ttk.Button(bt, text="Close", command=dlg.destroy).pack(side="right", padx=10)
        ttk.Button(bt, text="Show only projects found in the file", command=lambda: (self.f_view.set("infile"), self.render(), dlg.destroy())).pack(side="right")

    def show_unmatched(self):
        if not self.ext_batch:
            return
        rows = sf.unmatched_rows(self.projects)
        dlg = tk.Toplevel(self)
        dlg.title("Rows in the status file that are not in the deck")
        dlg.geometry("900x520")
        dlg.transient(self)
        tk.Label(dlg, text=f"{len(rows)} rows of the file did not match any project in the deck (they may be projects you do not track here, "
                           "or ones missing from the deck).", anchor="w", wraplength=860, justify="left", padx=10, pady=8).pack(fill="x")
        cols = (("country", "Country", 110), ("name", "Project in the file", 430), ("sheet", "Sheet", 130), ("stage", "Stage", 150))
        fr = tk.Frame(dlg)
        fr.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        tv = ttk.Treeview(fr, columns=[c for c, _, _ in cols], show="headings", style="Small.Treeview")
        for c, h, w in cols:
            tv.heading(c, text=h)
            tv.column(c, width=w)
        sb = ttk.Scrollbar(fr, command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        for r in sorted(rows, key=lambda r: (r["country"] or "~", r["name"])):
            tv.insert("", "end", values=(r["country"], r["name"], r["sheet"], sf.field_text(r["fields"].get("stage", "")).split("\n")[0]))

    # ------------------------------------------------------------------ the Status tab
    def _tab_ext(self):
        p = self.t_ext
        top = tk.Frame(p, bg="#FFFFFF")
        top.pack(fill="x")
        self.ext_info = tk.Label(top, text="", bg="#FFFFFF", fg="#546E7A", anchor="w", font=("Segoe UI", 9))
        self.ext_info.pack(side="left")
        ttk.Button(top, text="Reset", width=6, command=self.reset_link).pack(side="right")
        ttk.Button(top, text="No data for this project", command=self.mark_no_data).pack(side="right", padx=4)
        ttk.Button(top, text="Link to another row…", command=self.link_dialog).pack(side="right")
        fr = tk.Frame(p, bg="#FFFFFF")
        fr.pack(fill="both", expand=True, pady=(6, 0))
        t = tk.Text(fr, wrap="word", font=("Segoe UI", 10), relief="flat", bg="#FFFFFF", padx=4, pady=2, state="disabled", cursor="arrow",
                    highlightthickness=0)
        sb = ttk.Scrollbar(fr, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("h1", font=("Segoe UI Semibold", 12), foreground="#1B3A5F", spacing1=2, spacing3=2)
        t.tag_configure("h2", font=("Segoe UI", 8, "bold"), foreground="#546E7A", spacing1=8, spacing3=2)
        t.tag_configure("muted", foreground="#78909C")
        t.tag_configure("muted2", foreground="#607D8B", font=("Segoe UI", 9), lmargin1=16, lmargin2=16)
        t.tag_configure("warn", foreground="#E65100", font=("Segoe UI", 9, "bold"))
        t.tag_configure("key", font=("Segoe UI", 10, "bold"), foreground="#37474F")
        t.tag_configure("body", foreground="#22293A")
        t.tag_configure("chip", background="#E3EAF3", foreground="#1B3A5F", font=("Segoe UI", 9, "bold"))
        t.tag_configure("next", background="#FFF4C2", foreground="#3E2F00", lmargin1=6, lmargin2=6, spacing1=3, spacing3=3, rmargin=6)
        t.tag_configure("bank", background="#FDE3E1", foreground="#B71C1C", font=("Segoe UI", 9, "bold"))
        t.tag_configure("party", background="#DCEBFB", foreground="#0D47A1", font=("Segoe UI", 9, "bold"))
        t.tag_configure("pname", font=("Segoe UI", 10, "bold"), foreground="#22293A")
        t.tag_configure("chg", background="#E8F5E9", foreground="#1B5E20", font=("Segoe UI", 9, "bold"))
        t.tag_configure("chgtxt", foreground="#1B5E20")
        self.st_text = t

    def render_status(self):
        t = self.st_text
        t.configure(state="normal")
        t.delete("1.0", "end")

        def w(s, *tags):
            t.insert("end", s, tags)
        b = self.ext_batch
        if not b:
            self.ext_info.configure(text="")
            w("Internal status from the team's Excel file\n", "h1")
            w("Optional. Use  Status file ▾ → Import status file…  in the header and choose the team's workbook. "
              "What it says about each project - stage, next steps, partners and banks - then shows here. "
              "Nothing is needed if you do not use it, and it is only read when you import.", "muted")
        else:
            m = self.ext.get(self.cur) if self.cur else None
            self.ext_info.configure(text=f"{b['fname']} · imported {b['ts'][:16]}")
            if not self.cur:
                w("Select a project.", "muted")
            elif not m:
                lk = T.ext_links().get(self.cur)
                w("No data on this project\n", "h1")
                if lk is not None and not lk["norm"]:
                    w("You marked this project as having no data in the file.", "muted")
                else:
                    w(f"It was not found in {b['fname']} - not even a partial name match in its country.\n\n"
                      "If the team lists it under a different name, press  Link to another row…  and pick it.", "muted")
            else:
                chg = next((h for h in T.history(self.cur, 120) if h["action"] == "Status updated from file"), None)
                if chg:
                    w(f" Updated in the file {chg['ts'][:10]} ", "chg")
                    w("  " + chg["note"] + "\n\n", "chgtxt")
                for gi, g in enumerate(sf.group_rows(m)[:5]):
                    self._status_block(w, g, m["conf"], gi)
        t.configure(state="disabled")
        t.yview_moveto(0)

    def _status_block(self, w, g: dict, conf: str, gi: int):
        x = g["main"]
        r, f = x["row"], x["row"]["fields"]
        if gi:
            w("\n" + "─" * 56 + "\n", "muted")
        label = {"high": "confident match", "possible": "POSSIBLE match - check it is the same project", "linked": "linked by you"}[conf]
        w(f"{r['name']}\n", "h1")
        w(f"{r['sheet']} · row {r['row']} · {label} ({int(round(x['score'] * 100))}%)\n", "warn" if conf == "possible" else "muted")
        for key in ("stage", "class", "priority"):
            if f.get(key):
                w(" " + sf.field_text(f[key]).split("\n")[0] + " ", "chip")
                w("  ")
        w("\n")
        nx = f.get("next")
        if nx:
            w("NEXT STEPS\n", "h2")
            w(sf.field_text(nx) + "\n", "next")
        for a in g["also"]:
            an = a["row"]["fields"].get("next")
            if an and sf.field_text(an).strip() != sf.field_text(nx or "").strip():
                w(f"Next steps in sheet {a['row']['sheet']}\n", "h2")
                w(sf.field_text(an) + "\n", "next")
        parties = r["parties"]
        for a in g["also"]:  # parties named only in the other listing
            have = {p["name"].lower() for p in parties}
            parties = parties + [p for p in a["row"]["parties"] if p["name"].lower() not in have]
        banks = r["banks"]
        if parties or banks:
            w("PARTNERS & BANKS\n", "h2")
        for kind in KIND_ORDER:
            for p in [p for p in parties if p["kind"] == kind]:
                w(f" {p['role']} ", "bank" if kind == "Bank / lender" else "party")
                w("  " + p["name"], "pname")
                extra = " · ".join(v for v in (p.get("status"), ("commission: " + p["commission"]) if p.get("commission") else "", p.get("date"), p.get("notes")) if v)
                if extra:
                    w("\n" + extra, "muted2")
                w("\n")
        known = " ".join(p["name"].lower() for p in parties)
        extra_b = [b for b in banks if b.lower() not in known]
        if extra_b:
            w(" Financiers mentioned ", "bank")
            w("  " + ", ".join(extra_b) + "\n", "pname")
        shown = False
        for key in sf.SHOW_ORDER:
            if key in ("stage", "class", "priority"):
                continue
            v = f.get(key)
            if not v:
                continue
            if not shown:
                w("STATUS DETAILS\n", "h2")
                shown = True
            w(sf.LABELS.get(key, key) + ":  ", "key")
            w(sf.field_text(v) + "\n", "body")
        if g["also"]:
            w("\nAlso listed in: " + "; ".join(f"{a['row']['sheet']} row {a['row']['row']}" for a in g["also"]) + "\n", "muted")

    # ------------------------------------------------------------------ manual links
    def mark_no_data(self):
        if self.need_project() and messagebox.askyesno("No data", "Mark this project as having no data in the status file?\n"
                                                       "(It stays that way after future uploads until you press Reset.)", parent=self):
            T.ext_set_link(self.cur, "", "")
            self.after_ext()

    def reset_link(self):
        if self.need_project():
            T.ext_set_link(self.cur, None)
            self.after_ext()

    def link_dialog(self):
        if not self.need_project():
            return
        if not self.ext_batch:
            messagebox.showinfo("Status file", "Import the status file first (header: Status file).", parent=self)
            return
        rows = T.ext_rows()
        p = self.project()
        pc = sf._ccountry(p.get("country", ""))
        rows.sort(key=lambda r: (sf._ccountry(r["country"]) != pc, r["country"] or "~", r["name"]))
        dlg = tk.Toplevel(self)
        dlg.title("Link to a row in the status file")
        dlg.geometry("720x480")
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text=f"Which row of the file is  '{p['name']}' ?", anchor="w", padx=10, pady=8, font=("Segoe UI", 10, "bold")).pack(fill="x")
        q = tk.StringVar()
        e = ttk.Entry(dlg, textvariable=q)
        e.pack(fill="x", padx=10)
        lb = tk.Listbox(dlg, font=("Segoe UI", 10), activestyle="none")
        lb.pack(fill="both", expand=True, padx=10, pady=8)
        shown = []

        def fill(*a):
            lb.delete(0, "end")
            shown.clear()
            qq = q.get().strip().lower()
            for r in rows:
                line = f"{r['country'] or '-'}  ·  {r['name']}   ({r['sheet']})"
                if not qq or qq in line.lower():
                    shown.append(r)
                    lb.insert("end", line[:120])
        q.trace_add("write", fill)
        fill()

        def ok():
            s = lb.curselection()
            if s:
                r = shown[s[0]]
                T.ext_set_link(self.cur, sf.norm_name(r["name"]), r["country"])
                dlg.destroy()
                self.after_ext()
        ttk.Button(dlg, text="Link this row", command=ok).pack(pady=(0, 10))
        lb.bind("<Double-1>", lambda e: ok())
        e.focus_set()

    # ------------------------------------------------------------------ for printouts
    def _ext_summary(self, key: str) -> dict:
        m = self.ext.get(key)
        if not m:
            return {"none": True}
        g = sf.group_rows(m)
        if not g:
            return {"none": True}
        x = g[0]["main"]
        r, f = x["row"], x["row"]["fields"]
        more = [{"file": y["main"]["row"]["name"], "sheet": y["main"]["row"]["sheet"],
                 "stage": sf.field_text(y["main"]["row"]["fields"].get("stage", "")).split("\n")[0],
                 "next": sf.field_text(y["main"]["row"]["fields"].get("next", ""))} for y in g[1:6]]
        return {"none": False, "conf": m["conf"], "file": r["name"], "sheet": r["sheet"], "score": x["score"], "more": more,
                "stage": sf.field_text(f.get("stage", "")), "class": sf.field_text(f.get("class", "")), "next": sf.field_text(f.get("next", "")),
                "status": sf.field_text(f.get("status", "")), "parties": r["parties"], "banks": r["banks"]}
