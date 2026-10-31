#!/usr/bin/env python3
"""
Project Desk window - the internal discussion and review board.

Daily:  open it, look at the red chips (overdue actions, reviews due), tick off actions, add comments.
Weekly: filter to one lead, go project by project with  "Reviewed & next",  then print the Weekly review.
Everything is saved the moment you press Add (nothing to 'save'), logged, and never really deleted.
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional

import deckcore as core
import listutil as lu
import printing as pr
import tracker as T
import modelnames
from multipick import MultiPick, selected
from desk_report import ReportDialog
from desk_actions import ActionsMixin
from desk_status import StatusMixin

NAVY, BLUE, INK, MUTE = "#1B3A5F", "#1565C0", "#22293A", "#78909C"
LEAD_COL = {"RB": "#00796B", "JT": "#5E35B1", "SS": "#E65100", "": "#78909C"}
PEOPLE = ["RB", "JT", "SS", "Vishnu", "Vijayraj", "Other"]
UNASSIGNED = "Unassigned"
ANY = "(any)"
NO_SOURCE = "(no source)"
NO_MODEL = "(no model)"
NEEDS_CHOICES = [ANY, "Anything open", "Nothing recorded"] + T.KINDS
# (code, label, colour when it has items)
VIEWS = [("all", "All", NAVY), ("overdue", "⚠ Overdue", "#C62828"), ("due7", "Due ≤ 7d", "#E65100"),
         ("review", "Review due", "#E65100"), ("stale", "Idle 14d", "#6D4C41"), ("changed", "Changed 7d", "#2E7D32"),
         ("never", "Not discussed", "#546E7A"), ("noneeds", "No needs", "#546E7A"),
         ("infile", "In file", "#1565C0"), ("nofile", "Not in file", "#546E7A")]
REVIEW_DAYS = 7


class DeskPanel(ActionsMixin, StatusMixin, tk.Frame):
    """The whole Project Desk as a panel: shown inside the first screen ('Review & discuss'), or in its own window (DeskDialog)."""

    def __init__(self, master, app, audience: str):
        super().__init__(master)
        self.app, self.aud = app, audience
        self.configure(bg="#F4F6FA")
        self.sort_keys: list = [("lead", False), ("country", False), ("sr", False)]
        self.rows: List[dict] = []
        self.cur: Optional[str] = None
        self._busy = False
        self._sum_job = None
        self._by_manual = False
        ui = T.ui_get()
        self.f_lead = tk.StringVar(value=ui.get("lead", "All"))
        self.f_country, self.f_cat = tk.StringVar(value=ANY), tk.StringVar(value=ANY)
        self.f_needs, self.f_stage = tk.StringVar(value=ANY), tk.StringVar(value=ANY)
        self.f_source = tk.StringVar(value=ANY)
        self.f_model = tk.StringVar(value=ANY)
        self.f_view = tk.StringVar(value=ui.get("view", "all"))
        self.f_text = tk.StringVar()
        self.f_open = tk.BooleanVar(value=False)
        self.show_retired = tk.BooleanVar(value=False)
        self.inc_hidden = tk.BooleanVar(value=False)
        self.ext_batch, self.ext = None, {}
        self._saved_country = ui.get("country", ANY)
        self._style()
        if not T.user_is_set():
            import getpass
            n = simpledialog.askstring("Who are you?", "Your name (shown in the change log next to everything you do):",
                                       initialvalue=getpass.getuser().replace(".", " ").title(), parent=self)
            T.set_user(n or getpass.getuser())
        self._build()
        self.reload(first=True)
        top = self.winfo_toplevel()
        for seq, fn in (("<Control-f>", lambda: self.search_entry.focus_set()), ("<Alt-Right>", lambda: self.step(1)),
                        ("<Alt-Left>", lambda: self.step(-1)), ("<Control-r>", lambda: self.reviewed(False)), ("<F5>", self.reload)):
            top.bind(seq, lambda e, fn=fn: fn() if self.winfo_ismapped() else None, add="+")

    # ------------------------------------------------------------------ look
    def _style(self):
        st = ttk.Style(self)
        st.configure("Desk.Treeview", rowheight=27, font=("Segoe UI", 10), borderwidth=0)
        st.configure("Desk.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        st.configure("Small.Treeview", rowheight=24, font=("Segoe UI", 10))
        st.configure("Small.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        st.configure("Desk.TNotebook.Tab", padding=(14, 6), font=("Segoe UI", 10, "bold"))

    def _build(self):
        hd = tk.Frame(self, bg=NAVY, padx=16, pady=4)
        hd.pack(fill="x")
        tk.Label(hd, text="Review & discuss", bg=NAVY, fg="white", font=("Segoe UI Semibold", 13)).pack(side="left")
        tk.Label(hd, text=" INTERNAL ", bg="#C62828", fg="white", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(10, 0), pady=(8, 0))
        self.team_lbl = tk.Label(hd, text="", bg=NAVY, fg="#FFFFFF", font=("Segoe UI", 10, "bold"))
        self.team_lbl.pack(side="left", padx=(24, 0), pady=(6, 0))
        self.user_btn = tk.Button(hd, text="", command=self.change_user, bg="#27507F", fg="white", relief="flat", padx=10, cursor="hand2")
        self.user_btn.pack(side="right")
        for txt, fn in (("Geography & leads…", self.geo_dialog), ("Write to registry Excel", self.to_registry), ("Refresh  F5", self.reload)):
            tk.Button(hd, text=txt, command=fn, bg="#27507F", fg="white", relief="flat", padx=10, cursor="hand2").pack(side="right", padx=(0, 8))
        self.build_status_menu(hd)
        tk.Button(hd, text="Print / PDF / Excel…", command=self.report, bg="#FFFFFF", fg=NAVY, relief="flat", padx=12,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="right", padx=(0, 14))

        fb = tk.Frame(self, bg="#FFFFFF", padx=14, pady=8, highlightbackground="#DDE3EC", highlightthickness=1)
        fb.pack(fill="x")
        tk.Label(fb, text="Lead:", bg="#FFFFFF", fg=MUTE).pack(side="left")
        self.lead_btns = {}
        for v in ("All", "RB", "JT", "SS", UNASSIGNED):
            b = tk.Radiobutton(fb, text=v, value=v, variable=self.f_lead, indicatoron=False, command=self.lead_clicked, padx=12, pady=3,
                               bg="#ECEFF4", selectcolor=LEAD_COL.get(v, NAVY) if v != "All" else NAVY, fg=INK, activeforeground="white",
                               font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2")
            b.pack(side="left", padx=(6, 0))
            self.lead_btns[v] = b
        self.f_lead.trace_add("write", lambda *a: self._recolor())
        for lbl, var, w, attr in (("Country", self.f_country, 11, "cb_country"), ("Category", self.f_cat, 7, "cb_cat"),
                                  ("Needs", self.f_needs, 11, "cb_needs"), ("Stage", self.f_stage, 10, "cb_stage"),
                                  ("Source", self.f_source, 10, "cb_source"), ("Model", self.f_model, 9, "cb_model")):
            tk.Label(fb, text="  " + lbl + ":", bg="#FFFFFF", fg=MUTE).pack(side="left")
            cb = MultiPick(fb, var, width=w)
            cb.pack(side="left", padx=(2, 0))
            setattr(self, attr, cb)
        self.cb_cat.set_values(["Active", "BIP", "Hold", "Closed"])
        self.cb_needs.set_values(NEEDS_CHOICES[1:])
        self.cb_stage.set_values(T.STAGES)
        self.cb_model.set_values(modelnames.ORDER)

        fv = tk.Frame(self, bg="#FFFFFF", padx=14, highlightbackground="#DDE3EC", highlightthickness=0)
        fv.pack(fill="x")
        tk.Label(fv, text="Show:", bg="#FFFFFF", fg=MUTE).pack(side="left")
        self.view_btns = {}
        for code, label, col in VIEWS:
            b = tk.Radiobutton(fv, text=label, value=code, variable=self.f_view, indicatoron=False, padx=9, pady=2, relief="flat", bd=0,
                               bg="#F1F4F8", fg=INK, selectcolor=NAVY, activeforeground="white", font=("Segoe UI", 9), cursor="hand2",
                               command=self.render)
            b.pack(side="left", padx=(5, 0), pady=(0, 6))
            self.view_btns[code] = b
        ttk.Button(fv, text="Clear", width=6, command=self.clear).pack(side="right", pady=(0, 6))
        ttk.Checkbutton(fv, text="retired", variable=self.show_retired, command=self.reload).pack(side="right", padx=8, pady=(0, 6))
        ttk.Checkbutton(fv, text="has actions", variable=self.f_open, command=self.render).pack(side="right", padx=4, pady=(0, 6))
        self.search_entry = ttk.Entry(fv, textvariable=self.f_text, width=18)
        self.search_entry.pack(side="right", padx=(6, 6), pady=(0, 6))
        tk.Label(fv, text="Search:", bg="#FFFFFF", fg=MUTE).pack(side="right", pady=(0, 6))
        for v in (self.f_country, self.f_cat, self.f_needs, self.f_stage, self.f_source, self.f_model, self.f_text):
            v.trace_add("write", lambda *a: self.render())

        body = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bg="#F4F6FA", sashrelief="flat")
        body.pack(fill="both", expand=True, padx=10, pady=8)
        left = tk.Frame(body, bg="#F4F6FA")
        body.add(left, minsize=430, width=max(600, int(self.winfo_screenwidth() * 0.46)))
        self.build_actions_bar(left)
        cols = (("sr", "Sr.", 32), ("name", "Project", 150), ("country", "Country", 70), ("lead", "Lead", 34), ("cat", "Category", 54),
                ("source", "Source", 84), ("model", "Model", 70), ("needs", "Needs", 62), ("stage", "Stage", 76), ("fstage", "In file", 92), ("acts", "Act.", 38), ("review", "Review", 62))
        self.tree = ttk.Treeview(left, columns=[c for c, _, _ in cols], show="headings", selectmode="browse", style="Desk.Treeview")
        self.heads = {c: t for c, t, _ in cols}
        for c, t, w in cols:
            self.tree.heading(c, text=t, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, minwidth=34, anchor="center" if c in ("sr", "lead", "acts", "review") else "w", stretch=(c == "name"))
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for cat, col in pr.CAT_COLOR.items():
            self.tree.tag_configure("cat_" + cat, foreground=col)
        self.tree.tag_configure("retired", foreground="#B0BEC5")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.right = tk.Frame(body, bg="#FFFFFF", highlightbackground="#DDE3EC", highlightthickness=1)
        body.add(self.right, minsize=480)
        self._build_detail()
        sbar = tk.Frame(self, bg="#ECEFF4")
        sbar.pack(fill="x", side="bottom")
        self.file_lbl = tk.Label(sbar, anchor="e", bg="#ECEFF4", fg="#78909C", padx=12, pady=4, font=("Segoe UI", 9))
        self.file_lbl.pack(side="right")
        self.status = tk.Label(sbar, anchor="w", bg="#ECEFF4", fg="#455A64", padx=12, pady=4, font=("Segoe UI", 9))
        self.status.pack(side="left", fill="x", expand=True)

    def _recolor(self):
        for v, b in self.lead_btns.items():
            on = self.f_lead.get() == v
            b.configure(fg="white" if on else INK, bg=(LEAD_COL.get(v, NAVY) if v != "All" else NAVY) if on else "#ECEFF4")

    # ------------------------------------------------------------------ detail panel
    def _build_detail(self):
        r = self.right
        top = tk.Frame(r, bg="#FFFFFF", padx=14, pady=6)
        top.pack(fill="x")
        nav = tk.Frame(top, bg="#FFFFFF")
        nav.pack(side="right", anchor="n")
        tk.Button(nav, text="◀", command=lambda: self.step(-1), relief="flat", bg="#ECEFF4", padx=8).pack(side="left", padx=2)
        tk.Button(nav, text="▶", command=lambda: self.step(1), relief="flat", bg="#ECEFF4", padx=8).pack(side="left", padx=2)
        self.d_name = tk.Label(top, text="Select a project on the left", bg="#FFFFFF", fg=NAVY, font=("Segoe UI Semibold", 14), anchor="w", justify="left", wraplength=560)
        self.d_name.pack(anchor="w")
        self.d_sub = tk.Label(top, text="", bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 10), anchor="w", justify="left", wraplength=560)
        self.d_sub.pack(anchor="w")
        fr = tk.Frame(r, bg="#FFFFFF", padx=14)
        fr.pack(fill="x")
        self.v_lead, self.v_stage, self.v_pri, self.v_next = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        for i, (lbl, var, vals) in enumerate((("Lead", self.v_lead, ["(from geography)"] + T.LEADS), ("Stage", self.v_stage, T.STAGES),
                                              ("Priority", self.v_pri, T.PRIORITIES))):
            tk.Label(fr, text=lbl, bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8)).grid(row=0, column=i, sticky="w", padx=(0 if i == 0 else 8, 0))
            cb = ttk.Combobox(fr, textvariable=var, values=vals, state="readonly", width=14)
            cb.grid(row=1, column=i, sticky="w", padx=(0 if i == 0 else 8, 0))
            cb.bind("<<ComboboxSelected>>", lambda e: self.save_fields())
        tk.Label(fr, text="Next review", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8)).grid(row=0, column=3, sticky="w", padx=(8, 0))
        ne = ttk.Entry(fr, textvariable=self.v_next, width=11)
        ne.grid(row=1, column=3, sticky="w", padx=(8, 0))
        ne.bind("<Return>", lambda e: self.save_fields())
        ne.bind("<FocusOut>", lambda e: self.save_fields())
        bar = tk.Frame(r, bg="#FFFFFF", padx=14)
        bar.pack(fill="x", pady=(8, 0))
        tk.Button(bar, text="✔  Reviewed & next ▶", command=lambda: self.reviewed(True), bg="#2E7D32", fg="white", relief="flat", padx=12,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="left")
        tk.Button(bar, text="✔ Reviewed", command=lambda: self.reviewed(False), bg="#E8F5E9", fg="#1B5E20", relief="flat", padx=10, cursor="hand2").pack(side="left", padx=6)
        tk.Label(bar, text=f"logs the review and sets the next one {REVIEW_DAYS} days ahead   (Ctrl+R)", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8)).pack(side="left", padx=4)
        tk.Label(r, text="Internal summary / background (saved as you type)", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(8, 0))
        self.d_sum = tk.Text(r, height=2, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=0, undo=True)
        self.d_sum.pack(fill="x", padx=14, pady=(2, 6))
        self.d_sum.bind("<KeyRelease>", self._sum_typed)
        self.d_sum.bind("<FocusOut>", lambda e: self.save_summary())
        nb = ttk.Notebook(r, style="Desk.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.nb = nb
        self.t_req, self.t_cmt, self.t_act, self.t_ext, self.t_log = (tk.Frame(nb, bg="#FFFFFF", padx=8, pady=8) for _ in range(5))
        for f, t in ((self.t_cmt, "Comments"), (self.t_req, "Needs"), (self.t_act, "Actions"), (self.t_ext, "Status"), (self.t_log, "History")):
            nb.add(f, text=t)
        self._tab_req()
        self._tab_cmt()
        self._tab_act()
        self._tab_ext()
        self._tab_log()

    def _tree(self, parent, cols, height=7):
        fr = tk.Frame(parent, bg="#FFFFFF")
        t = ttk.Treeview(fr, columns=[c for c, _, _ in cols], show="headings", height=height, selectmode="browse", style="Small.Treeview")
        for c, h, w in cols:
            t.heading(c, text=h)
            t.column(c, width=w, minwidth=30, stretch=(w >= 200))
        sb = ttk.Scrollbar(fr, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        return fr, t

    def _tab_req(self):
        p = self.t_req
        a = tk.Frame(p, bg="#FFFFFF")
        a.pack(fill="x", pady=(0, 6))
        self.r_kind, self.r_detail = tk.StringVar(value=T.KINDS[0]), tk.StringVar()
        self.r_kind.set(T.KINDS[0])
        MultiPick(a, self.r_kind, T.KINDS, width=16, empty=T.KINDS[0]).pack(side="left")
        e = ttk.Entry(a, textvariable=self.r_detail)
        e.pack(side="left", fill="x", expand=True, padx=6)
        e.bind("<Return>", lambda ev: self.add_req())
        tk.Button(a, text="Add need", command=self.add_req, bg=BLUE, fg="white", relief="flat", padx=12).pack(side="left")
        tk.Label(p, text="what is needed (investor, EPC, ...) and detail, e.g. 'USD 120 Mn senior debt'", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8), anchor="w").pack(fill="x")
        fr, self.req_tree = self._tree(p, (("kind", "Needed", 130), ("detail", "Detail", 260), ("status", "Status", 80)), 6)
        fr.pack(fill="both", expand=True, pady=(4, 0))
        self.req_tree.bind("<<TreeviewSelect>>", self._req_sel)
        self.req_tree.bind("<Double-1>", lambda e: self.edit_req())
        b = tk.Frame(p, bg="#FFFFFF")
        b.pack(fill="x", pady=(6, 0))
        tk.Label(b, text="Status of selected:", bg="#FFFFFF").pack(side="left")
        self.r_status = tk.StringVar()
        cb = ttk.Combobox(b, textvariable=self.r_status, values=T.REQ_STATUS, state="readonly", width=12)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.set_req_status())
        ttk.Button(b, text="Edit detail…", command=self.edit_req).pack(side="left", padx=4)
        ttk.Button(b, text="Delete", command=self.del_req).pack(side="left")

    def _tab_cmt(self):
        p = self.t_cmt
        a = tk.Frame(p, bg="#F7F9FC", padx=8, pady=8, highlightbackground="#DDE3EC", highlightthickness=1)
        a.pack(fill="x")
        r1 = tk.Frame(a, bg="#F7F9FC")
        r1.pack(fill="x")
        tk.Label(r1, text="Comment by", bg="#F7F9FC").pack(side="left")
        self.c_by, self.c_day = tk.StringVar(), tk.StringVar(value=T.today())
        cb = ttk.Combobox(r1, textvariable=self.c_by, values=PEOPLE, width=11)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: setattr(self, "_by_manual", True))
        tk.Label(r1, text="discussion date", bg="#F7F9FC").pack(side="left", padx=(8, 0))
        ttk.Entry(r1, textvariable=self.c_day, width=11).pack(side="left", padx=6)
        ttk.Button(r1, text="today", width=6, command=lambda: self.c_day.set(T.today())).pack(side="left")
        self.c_text = tk.Text(a, height=3, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=0, undo=True)
        self.c_text.pack(fill="x", pady=6)
        self.c_text.bind("<Control-Return>", lambda e: (self.add_comment(), "break")[1])
        r2 = tk.Frame(a, bg="#F7F9FC")
        r2.pack(fill="x")
        tk.Button(r2, text="Add comment  (Ctrl+Enter)", command=self.add_comment, bg=BLUE, fg="white", relief="flat", padx=14).pack(side="left")
        tk.Label(r2, text="saved instantly, kept forever", bg="#F7F9FC", fg=MUTE, font=("Segoe UI", 8)).pack(side="left", padx=10)
        fr, self.cmt_tree = self._tree(p, (("day", "Date", 78), ("by", "By", 64), ("text", "Comment", 330)), 4)
        fr.pack(fill="both", expand=True, pady=(8, 0))
        self.cmt_tree.bind("<<TreeviewSelect>>", self._cmt_sel)
        self.c_full = tk.Text(p, height=3, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=0, state="disabled", bg="#FAFAFA")
        self.c_full.pack(fill="x", pady=(6, 0))
        b = tk.Frame(p, bg="#FFFFFF")
        b.pack(fill="x", pady=(4, 0))
        ttk.Button(b, text="Save edit", command=self.save_comment_edit).pack(side="left")
        ttk.Button(b, text="Delete comment", command=self.del_comment).pack(side="left", padx=6)
        tk.Label(b, text="(select a comment above to read / edit it in full)", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8)).pack(side="left", padx=6)

    def _tab_act(self):
        p = self.t_act
        a = tk.Frame(p, bg="#FFFFFF")
        a.pack(fill="x")
        self.a_text, self.a_owner, self.a_due = tk.StringVar(), tk.StringVar(), tk.StringVar()
        e = ttk.Entry(a, textvariable=self.a_text)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.add_action())
        ttk.Combobox(a, textvariable=self.a_owner, values=PEOPLE, width=9).pack(side="left", padx=4)
        ttk.Entry(a, textvariable=self.a_due, width=11).pack(side="left")
        tk.Button(a, text="Add", command=self.add_action, bg=BLUE, fg="white", relief="flat", padx=14).pack(side="left", padx=6)
        qk = tk.Frame(p, bg="#FFFFFF")
        qk.pack(fill="x", pady=(2, 4))
        tk.Label(qk, text="action · owner · due.   Quick due:", bg="#FFFFFF", fg=MUTE, font=("Segoe UI", 8)).pack(side="left")
        for lbl, d in (("tomorrow", 1), ("+1 week", 7), ("+2 weeks", 14), ("+1 month", 30)):
            tk.Button(qk, text=lbl, relief="flat", bg="#F1F4F8", font=("Segoe UI", 8), padx=6, cursor="hand2",
                      command=lambda d=d: self.a_due.set((datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d"))).pack(side="left", padx=2)
        fr, self.act_tree = self._tree(p, (("done", "✔", 28), ("text", "Action", 270), ("owner", "Owner", 70), ("due", "Due", 80)), 9)
        fr.pack(fill="both", expand=True)
        self.act_tree.tag_configure("done", foreground="#90A4AE")
        self.act_tree.tag_configure("over", foreground="#C62828")
        self.act_tree.bind("<Double-1>", lambda e: self.toggle_action())
        b = tk.Frame(p, bg="#FFFFFF")
        b.pack(fill="x", pady=(6, 0))
        ttk.Button(b, text="Tick / untick  (double-click)", command=self.toggle_action).pack(side="left")
        ttk.Button(b, text="Edit…", command=self.edit_action).pack(side="left", padx=6)
        ttk.Button(b, text="Delete", command=self.del_action).pack(side="left")

    def _tab_log(self):
        top = tk.Frame(self.t_log, bg="#FFFFFF")
        top.pack(fill="x")
        tk.Label(top, text="Every addition, change and deletion for this project - who and when.", bg="#FFFFFF", fg="#546E7A", anchor="w").pack(side="left")
        ttk.Button(top, text="Restore deleted…", command=self.restore_dialog).pack(side="right")
        fr, self.log_tree = self._tree(self.t_log, (("ts", "When", 118), ("user", "Who", 70), ("what", "What", 300)), 14)
        fr.pack(fill="both", expand=True, pady=(4, 0))

    # ------------------------------------------------------------------ data
    def reload(self, first=False):
        try:
            L = core.load_projects(self.aud, include_retired=True)["projects"]
        except Exception as exc:
            messagebox.showerror("Project Desk", f"Could not read the deck: {exc}", parent=self)
            L = []
        self.all_projects = L
        msgs = T.note_deck(L)
        self.projects = [p for p in L if self.show_retired.get() or not p.get("retired")]
        self._load_ext()
        self.ov = self._ov()
        self.geo = {g["country"].lower(): g["lead"] for g in T.geo_list()}
        self.user_btn.configure(text="✎  " + T.get_user())
        self._all_countries = sorted({p.get("country") or "" for p in self.projects if p.get("country")})
        self.lead_changed(render=False)
        self.cb_model.set_values(sorted({m for p in self.projects for m in modelnames.parts(p.get("model"))},
                                        key=lambda x: (modelnames.ORDER.index(x) if x in modelnames.ORDER else 99, x)) + [NO_MODEL])
        self._all_sources = sorted({s for p in self.projects for s in (p.get("sources") or [])}, key=str.lower)
        self.cb_source.set_values([NO_SOURCE] + self._all_sources)
        if first and self._saved_country != ANY:
            ok = [c for c in self._saved_country.split("|") if c in self.cb_country.values()]
            if ok:
                self.f_country.set("|".join(ok))
        self.render()
        if first:
            if msgs:
                self.set_status("Since last time: " + "; ".join(msgs[:4]))
            if not self.cur and self.tree.get_children():
                self.tree.selection_set(self.tree.get_children()[0])

    def lead_of(self, p: dict) -> str:
        o = self.ov.get(p["id"], {})
        return o.get("lead") or self.geo.get(T.canonical(p.get("country", "")).lower(), "")

    def lead_clicked(self):
        self._by_manual = False
        self.lead_changed()

    def lead_changed(self, render=True):
        lead = self.f_lead.get()
        cs = [c for c in self._all_countries if lead == "All" or (self.geo.get(T.canonical(c).lower(), "") or UNASSIGNED) == lead]
        self.cb_country.set_values(cs)
        tm = T.team()
        self.team_lbl.configure(text=(f"{lead} team: {', '.join(tm.get(lead, [])) or '-'}   ·   PMs: {T.PMS}" if lead in T.LEADS else f"PMs: {T.PMS}"))
        if lead in T.LEADS and not self._by_manual:
            self.c_by.set(lead)
        if render:
            self.render()

    def clear(self):
        self._by_manual = False
        self.f_lead.set("All")
        self.f_view.set("all")
        for v in (self.f_country, self.f_cat, self.f_needs, self.f_stage, self.f_source, self.f_model):
            v.set(ANY)
        self.f_text.set("")
        self.f_open.set(False)

    def _row(self, p: dict) -> dict:
        return {"p": p, "lead": self.lead_of(p), "o": self.ov.get(p["id"], {})}

    @staticmethod
    def _in_view(view: str, o: dict) -> bool:
        td = T.today()
        d14 = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        d7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        last = (o.get("last_activity") or "")[:10]
        return {"all": True, "overdue": o.get("overdue", 0) > 0, "due7": o.get("due7", 0) > 0,
                "review": bool(o.get("next_review")) and o["next_review"] <= td,
                "stale": last < d14, "changed": bool(last) and last >= d7,
                "never": o.get("n_cmts", 0) == 0, "noneeds": o.get("n_reqs", 0) == 0,
                "infile": "ext_conf" in o, "nofile": "ext_conf" not in o}[view]

    def _match(self, r: dict, skip=()) -> bool:
        p, o, lead = r["p"], r["o"], self.f_lead.get()
        if "lead" not in skip:
            if lead == UNASSIGNED and r["lead"]:
                return False
            if lead in T.LEADS and r["lead"] != lead:
                return False
        sc, sk, ss = selected(self.f_country), selected(self.f_cat), selected(self.f_stage)
        if sc and p.get("country") not in sc:
            return False
        if sk and p.get("category") not in sk:
            return False
        if ss and o.get("stage", "To discuss") not in ss:
            return False
        nf = selected(self.f_needs)
        if nf:
            have = [x.strip() for x in o.get("needs", "").split(",") if x.strip()]
            hit = ("Anything open" in nf and o.get("open_reqs")) or ("Nothing recorded" in nf and not o.get("n_reqs")) or \
                any(k in have for k in nf if k in T.KINDS)
            if not hit:
                return False
        mf = selected(self.f_model)
        if mf:
            mine = {m.lower() for m in modelnames.parts(p.get("model"))}
            if not (({m.lower() for m in mf if m != NO_MODEL} & mine) or (NO_MODEL in mf and not mine)):
                return False
        src = selected(self.f_source)
        if src:
            mine = {s.lower() for s in (p.get("sources") or [])}
            if not (({s.lower() for s in src if s != NO_SOURCE} & mine) or (NO_SOURCE in src and not mine)):
                return False
        if self.f_open.get() and not o.get("open_actions"):
            return False
        q = self.f_text.get().strip().lower()
        if q and q not in " ".join([p["name"], p.get("country", ""), p.get("sector", ""), p["id"], o.get("last_comment", ""), o.get("summary", ""), o.get("needs", "")]).lower():
            return False
        if "view" not in skip and not self._in_view(self.f_view.get(), o):
            return False
        return True

    def visible(self) -> List[dict]:
        return lu.sort_items([r for r in map(self._row, self.projects) if self._match(r)], self.sort_keys, self._get)

    def _get(self, r: dict, col: str):
        p, o = r["p"], r["o"]
        return {"sr": f"{int(p.get('sr') or 0):05d}", "name": p["name"], "country": p.get("country", ""), "lead": r["lead"], "cat": p.get("category", ""), "source": (p.get("source") or "").lower(), "model": (p.get("model") or "").lower(),
                "needs": o.get("needs", ""), "stage": o.get("stage", "To discuss"), "fstage": o.get("ext_stage", ""), "acts": f"{99 - o.get('open_actions', 0):03d}",
                "review": o.get("next_review", ""), "last": o.get("last_comment", "")}[col]

    def sort_by(self, col):
        self.sort_keys = lu.toggle_sort(self.sort_keys, col)
        self.render()

    def _counts(self):
        self._show_file_chips(bool(self.ext_batch))
        allrows = [self._row(p) for p in self.projects]
        base = [r for r in allrows if self._match(r, skip=("view",))]
        for code, label, col in VIEWS:
            n = sum(1 for r in base if self._in_view(code, r["o"]))
            b = self.view_btns[code]
            b.configure(text=f"{label}  {n}", fg=(col if (n and code != "all") else INK))
        by_lead = [r for r in allrows if self._match(r, skip=("lead",))]
        for v, b in self.lead_btns.items():
            n = len(by_lead) if v == "All" else sum(1 for r in by_lead if (r["lead"] == v if v in T.LEADS else not r["lead"]))
            b.configure(text=f"{v}  {n}")
        self._recolor()
        for code, b in self.view_btns.items():
            if self.f_view.get() == code:
                b.configure(bg=NAVY, fg="white")
            else:
                b.configure(bg="#F1F4F8")

    def render(self):
        if self._busy:
            return
        self._counts()
        self.rows = self.visible()
        sel, td = self.cur, T.today()
        self._busy = True
        self.tree.delete(*self.tree.get_children())
        for r in self.rows:
            p, o = r["p"], r["o"]
            oa, ov = o.get("open_actions", 0), o.get("overdue", 0)
            nr = o.get("next_review", "")
            tags = ["cat_" + p.get("category", "")] + (["retired"] if p.get("retired") else [])
            self.tree.insert("", "end", iid=p["id"], tags=tags, values=(
                p.get("sr", ""), p["name"], p.get("country", ""), r["lead"] or "—", p.get("category", ""), p.get("source") or "—", p.get("model") or "—", o.get("needs", "") or "—",
                o.get("stage", "To discuss"), self._fstage(o), (f"{oa}" + (f" ⚠{ov}" if ov else "")) if oa else "",
                (nr[5:] + (" ⚠" if nr <= td else "")) if nr else ""))
        for c, t in self.heads.items():
            arrow = ""
            for k, rev in self.sort_keys[:1]:
                if k == c:
                    arrow = " ▼" if rev else " ▲"
            self.tree.heading(c, text=t + arrow)
        if sel and self.tree.exists(sel):
            self.tree.selection_set(sel)
        self._busy = False
        n_open = sum(r["o"].get("open_reqs", 0) for r in self.rows)
        self.set_status(f"{len(self.rows)} of {len(self.projects)} projects shown  ·  {n_open} open needs  ·  saved automatically, every change is logged  ·  daily backup in data\\backups")

    def set_status(self, t: str):
        self.status.configure(text=t)

    def step(self, d: int):
        ids = self.tree.get_children()
        if not ids:
            return
        i = ids.index(self.cur) + d if self.cur in ids else 0
        i = max(0, min(len(ids) - 1, i))
        self.tree.selection_set(ids[i])
        self.tree.see(ids[i])

    # ------------------------------------------------------------------ selection / detail refresh
    def on_select(self, e=None):
        if self._busy:
            return
        s = self.tree.selection()
        if not s:
            return
        self.save_summary()
        self.cur = s[0]
        self.show_detail()

    def project(self) -> Optional[dict]:
        return next((p for p in self.projects if p["id"] == self.cur), None)

    def show_detail(self):
        p = self.project()
        if not p:
            return
        pj = T.get_proj(p["id"], p.get("country", ""))
        lead = pj["lead"] or pj["geo_lead"]
        self.d_name.configure(text=f"{p.get('sr', '')}.  {p['name']}")
        self.d_sub.configure(text="  ·  ".join(x for x in (p.get("country"), p.get("sector"), p.get("category"),
                                                              f"lead {lead}" if lead else "no lead assigned", "PMs " + pj["pm_eff"]) if x))
        self._busy = True
        self.v_lead.set(pj["lead"] or "(from geography)")
        self.v_stage.set(pj["stage"])
        self.v_pri.set(pj["priority"])
        self.v_next.set(pj["next_review"])
        self.d_sum.delete("1.0", "end")
        self.d_sum.insert("1.0", pj["summary"])
        if not self._by_manual or not self.c_by.get():
            self.c_by.set(lead or "")
        self._busy = False
        self.fill_lists()

    def fill_lists(self):
        k = self.cur
        if not k:
            return
        self.req_tree.delete(*self.req_tree.get_children())
        for r in T.reqs(k):
            self.req_tree.insert("", "end", iid=str(r["id"]), values=(r["kind"], r["detail"], r["status"]))
        self.cmt_tree.delete(*self.cmt_tree.get_children())
        for c in T.comments(k):
            self.cmt_tree.insert("", "end", iid=str(c["id"]), values=(c["day"], c["by"], c["text"].replace("\n", " ↵ ")))
        self._show_full("")
        td = T.today()
        self.act_tree.delete(*self.act_tree.get_children())
        for a in T.actions(k):
            tag = "done" if a["done"] else ("over" if a["due"] and a["due"] < td else "")
            self.act_tree.insert("", "end", iid=str(a["id"]), tags=(tag,), values=("✔" if a["done"] else "☐", a["text"], a["owner"], a["due"]))
        self.log_tree.delete(*self.log_tree.get_children())
        from desk_report import fmt_event
        for h in T.history(k, 300):
            self.log_tree.insert("", "end", values=(h["ts"][:16], h["user"], fmt_event(h)))
        self.render_status()

    def after_change(self):
        self.ov = self._ov()
        self.render()
        self.fill_lists()

    def guard(self, fn):
        try:
            fn()
        except core.DeckError as exc:
            messagebox.showinfo("Project Desk", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Project Desk", f"Something went wrong, nothing was lost:\n{exc}", parent=self)

    # ------------------------------------------------------------------ edits (every one is saved + logged immediately)
    def save_fields(self):
        if self._busy or not self.cur:
            return
        lead = self.v_lead.get()
        self.guard(lambda: T.set_proj(self.cur, lead="" if lead.startswith("(") else lead, stage=self.v_stage.get(), priority=self.v_pri.get(),
                                      next_review=self.v_next.get()))
        self.ov = self._ov()
        self.render()
        self.show_detail()

    def reviewed(self, advance: bool):
        if not self.need_project():
            return
        self.save_summary()
        k = self.cur
        self.guard(lambda: T.mark_reviewed(k, REVIEW_DAYS))
        self.ov = self._ov()
        self.render()
        if advance:
            ids = self.tree.get_children()
            if k in ids and ids.index(k) + 1 < len(ids):
                self.tree.selection_set(ids[ids.index(k) + 1])
                self.tree.see(ids[ids.index(k) + 1])
                self.set_status("Reviewed. Next project.")
            else:
                self.show_detail()
                self.set_status("Reviewed - that was the last project in this view.")
        else:
            self.show_detail()
            self.set_status("Reviewed.")

    def _sum_typed(self, e=None):
        if self._sum_job:
            self.after_cancel(self._sum_job)
        self._sum_job = self.after(900, self.save_summary)

    def save_summary(self):
        if self._sum_job:
            try:
                self.after_cancel(self._sum_job)
            except Exception:
                pass
            self._sum_job = None
        if self._busy or not self.cur:
            return
        txt = self.d_sum.get("1.0", "end").strip()
        if txt != (T.get_proj(self.cur)["summary"] or ""):
            self.guard(lambda: T.set_proj(self.cur, summary=txt))
            self.set_status("Summary saved.")

    def need_project(self) -> bool:
        if not self.cur:
            messagebox.showinfo("Project Desk", "Select a project on the left first.", parent=self)
            return False
        return True

    def add_req(self):
        if not self.need_project():
            return
        kinds = selected(self.r_kind) or [T.KINDS[0]]  # several can be ticked: one need row is added for each (EPC + Lender / DFI ...)
        self.guard(lambda: ([T.add_req(self.cur, k, self.r_detail.get()) for k in kinds], self.r_detail.set(""), self.after_change()))

    def _req_sel(self, e=None):
        s = self.req_tree.selection()
        if s:
            self.r_status.set(self.req_tree.item(s[0], "values")[2])

    def set_req_status(self):
        s = self.req_tree.selection()
        if s:
            self.guard(lambda: (T.update_req(int(s[0]), status=self.r_status.get()), self.after_change()))

    def edit_req(self):
        s = self.req_tree.selection()
        if not s:
            return
        v = self.req_tree.item(s[0], "values")
        n = simpledialog.askstring("Edit need", f"{v[0]} - detail:", initialvalue=v[1], parent=self)
        if n is not None:
            self.guard(lambda: (T.update_req(int(s[0]), detail=n), self.after_change()))

    def del_req(self):
        s = self.req_tree.selection()
        if s and messagebox.askyesno("Delete need", "Delete this need?\n(It can be restored from the History tab.)", parent=self):
            self.guard(lambda: (T.delete_req(int(s[0])), self.after_change()))

    def add_comment(self):
        if not self.need_project():
            return
        txt = self.c_text.get("1.0", "end").strip()

        def go():
            T.add_comment(self.cur, self.c_by.get() or T.get_user(), txt, self.c_day.get().strip())
            self.c_text.delete("1.0", "end")
            self.after_change()
            self.set_status("Comment saved.")
        self.guard(go)

    def _show_full(self, text: str, editable=False):
        self.c_full.configure(state="normal")
        self.c_full.delete("1.0", "end")
        self.c_full.insert("1.0", text)
        self.c_full.configure(state="normal" if editable else "disabled", bg="#FFFFFF" if editable else "#FAFAFA")

    def _cmt_sel(self, e=None):
        s = self.cmt_tree.selection()
        if s:
            c = next((x for x in T.comments(self.cur) if x["id"] == int(s[0])), None)
            self._show_full(c["text"] if c else "", editable=True)

    def save_comment_edit(self):
        s = self.cmt_tree.selection()
        if s:
            self.guard(lambda: (T.update_comment(int(s[0]), self.c_full.get("1.0", "end").strip()), self.after_change()))

    def del_comment(self):
        s = self.cmt_tree.selection()
        if s and messagebox.askyesno("Delete comment", "Delete this comment?\n(It can be restored from the History tab.)", parent=self):
            self.guard(lambda: (T.delete_comment(int(s[0])), self.after_change()))

    def add_action(self):
        if not self.need_project():
            return
        self.guard(lambda: (T.add_action(self.cur, self.a_text.get(), self.a_owner.get(), self.a_due.get()),
                            self.a_text.set(""), self.a_due.set(""), self.after_change()))

    def toggle_action(self):
        s = self.act_tree.selection()
        if s:
            done = self.act_tree.item(s[0], "values")[0] != "✔"
            self.guard(lambda: (T.set_action_done(int(s[0]), done), self.after_change()))

    def edit_action(self):
        s = self.act_tree.selection()
        if not s:
            return
        v = self.act_tree.item(s[0], "values")
        n = simpledialog.askstring("Edit action", "Action:", initialvalue=v[1], parent=self)
        if n is not None:
            d = simpledialog.askstring("Edit action", "Due date (YYYY-MM-DD, blank for none):", initialvalue=v[3], parent=self)
            self.guard(lambda: (T.update_action(int(s[0]), text=n, due=d if d is not None else v[3]), self.after_change()))

    def del_action(self):
        s = self.act_tree.selection()
        if s and messagebox.askyesno("Delete action", "Delete this action?\n(It can be restored from the History tab.)", parent=self):
            self.guard(lambda: (T.delete_action(int(s[0])), self.after_change()))

    def restore_dialog(self):
        if not self.need_project():
            return
        items = T.deleted_items(self.cur)
        if not items:
            messagebox.showinfo("Restore deleted", "Nothing has been deleted on this project.", parent=self)
            return
        dlg = tk.Toplevel(self)
        dlg.title("Restore deleted items")
        dlg.geometry("620x320")
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="Select an item and press Restore - it comes back exactly as it was.", anchor="w", padx=10, pady=8).pack(fill="x")
        lb = tk.Listbox(dlg, font=("Segoe UI", 10), activestyle="none")
        lb.pack(fill="both", expand=True, padx=10)
        for it in items:
            lb.insert("end", it["text"][:110])

        def go():
            s = lb.curselection()
            if s:
                it = items[s[0]]
                self.guard(lambda: (T.restore_item(it["type"], it["id"]), self.after_change()))
                dlg.destroy()
        ttk.Button(dlg, text="Restore", command=go).pack(pady=8)

    # ------------------------------------------------------------------ header actions
    def change_user(self):
        n = simpledialog.askstring("Who are you?", "Your name (shown in the change log):", initialvalue=T.get_user(), parent=self)
        if n and n.strip():
            T.set_user(n)
            self.user_btn.configure(text="✎  " + n.strip())

    def _filter_text(self) -> List[str]:
        bits = []
        if self.f_lead.get() != "All":
            bits.append("Lead: " + self.f_lead.get())
        for lbl, v in (("Country", self.f_country), ("Category", self.f_cat), ("Needs", self.f_needs), ("Stage", self.f_stage),
                       ("Source", self.f_source), ("Model", self.f_model)):
            if selected(v):
                bits.append(f"{lbl}: {', '.join(selected(v))}")
        if self.f_view.get() != "all":
            bits.append("Show: " + next(l for c, l, _ in VIEWS if c == self.f_view.get()))
        if self.f_text.get().strip():
            bits.append(f"Search: {self.f_text.get().strip()}")
        return ["Filters - " + ("  ·  ".join(bits) if bits else "all projects")]

    def report(self):
        self.save_summary()

        def provider():
            items = []
            for r in self.rows:
                k = r["p"]["id"]
                items.append({"p": r["p"], "lead": r["lead"], "o": r["o"], "proj": T.get_proj(k, r["p"].get("country", "")),
                              "reqs": T.reqs(k), "cmts": T.comments(k), "acts": T.actions(k),
                              "ext": self._ext_summary(k) if self.ext_batch else None})
            items.sort(key=lambda it: ((it["lead"] or "~"), it["p"].get("country") or "~", int(it["p"].get("sr") or 0)))
            return items, [r["p"] for r in self.rows], self._filter_text()
        ReportDialog(self, provider, self.f_lead.get() if self.f_lead.get() in T.LEADS else "", has_ext=bool(self.ext_batch))

    def to_registry(self):
        try:
            p = T.mirror_to_registry(self.all_projects)
            messagebox.showinfo("Registry Excel updated", "The Desk sheets (summary, needs, comments, actions, change log, geography) "
                                f"were written into:\n{p}\n\nA backup of the previous file was made first.", parent=self)
        except core.DeckError as exc:
            messagebox.showinfo("Registry Excel", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Registry Excel", str(exc), parent=self)

    def geo_dialog(self):
        GeoDialog(self)

    def flush(self):
        """Called when the Desk is left / the app closes: keep the summary, remember the filters, refresh the safety copy."""
        try:
            self.save_summary()
            d = T.ui_get()
            d.update({"lead": self.f_lead.get(), "country": self.f_country.get(), "view": self.f_view.get()})
            T.ui_set(d)
            T.snapshot(self.all_projects)  # a plain-Excel safety copy of everything
        except Exception:
            pass


class DeskDialog(tk.Toplevel):
    """The Desk in a window of its own (e.g. for a second monitor)."""

    def __init__(self, app, audience: str):
        super().__init__(app)
        self.title("Project Desk - internal")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1360, sw - 40), min(820, sh - 110)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+10")
        self.panel = DeskPanel(self, app, audience)
        self.panel.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        self.panel.flush()
        self.destroy()


class GeoDialog(tk.Toplevel):
    """Who looks after which country. Changing it re-files the projects of that country under the new lead."""

    def __init__(self, desk: DeskDialog):
        super().__init__(desk)
        self.desk = desk
        self.title("Geography & leads")
        self.geometry("460x600")
        self.transient(desk)
        self.grab_set()
        tk.Label(self, text="Country → lead.  Select a country and choose its lead.", anchor="w", padx=12, pady=8, font=("Segoe UI", 10, "bold")).pack(fill="x")
        fr = tk.Frame(self)
        fr.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(fr, columns=("country", "lead"), show="headings", selectmode="browse", style="Desk.Treeview")
        self.tree.heading("country", text="Country")
        self.tree.heading("lead", text="Lead")
        self.tree.column("country", width=260)
        self.tree.column("lead", width=80, anchor="center")
        sb = ttk.Scrollbar(fr, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        b = tk.Frame(self, padx=12, pady=10)
        b.pack(fill="x")
        for lead in T.LEADS + ["(none)"]:
            tk.Button(b, text=lead, width=7, relief="flat", bg=LEAD_COL.get(lead, "#78909C"), fg="white", cursor="hand2",
                      command=lambda l=lead: self.assign(l)).pack(side="left", padx=3)
        ttk.Button(b, text="Add country…", command=self.add).pack(side="right")
        tk.Label(self, anchor="w", padx=12, pady=6, fg="#546E7A", justify="left", wraplength=430,
                 text="Countries used in the deck but not listed here show as 'Unassigned' in the Desk - add them here.").pack(fill="x")
        self.fill()

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        have = {g["country"].lower() for g in T.geo_list()}
        rows = [(g["country"], g["lead"]) for g in T.geo_list()]
        for p in self.desk.all_projects:
            c = p.get("country") or ""
            if c and T.canonical(c).lower() not in have:
                rows.append((T.canonical(c), ""))
                have.add(T.canonical(c).lower())
        for c, l in sorted(rows, key=lambda r: (r[1] or "~", r[0])):
            self.tree.insert("", "end", iid=c, values=(c, l or "— unassigned"))

    def assign(self, lead):
        s = self.tree.selection()
        if not s:
            messagebox.showinfo("Geography", "Select a country first.", parent=self)
            return
        try:
            T.set_geo(s[0], "" if lead == "(none)" else lead)
        except core.DeckError as exc:
            messagebox.showinfo("Geography", str(exc), parent=self)
            return
        self.fill()
        self.desk.reload()

    def add(self):
        c = simpledialog.askstring("Add country", "Country name:", parent=self)
        if c and c.strip():
            l = simpledialog.askstring("Add country", "Lead (RB / JT / SS):", parent=self)
            if l and l.strip().upper() in T.LEADS:
                T.set_geo(c.strip(), l.strip().upper())
                self.fill()
                self.desk.reload()
