#!/usr/bin/env python3
"""A drop-down where several items can be ticked (filters and 'Add need').

The ticked items live in a tk.StringVar joined by SEP, so existing code that traces / reads a StringVar keeps working.
An empty selection (or ANY) means 'everything'."""
from __future__ import annotations

import tkinter as tk
from typing import Iterable, List

SEP = "|"
ANY = "(any)"


def selected(var: tk.StringVar) -> List[str]:
    """Items ticked in a MultiPick variable ([] = no restriction)."""
    v = var.get().strip()
    return [] if (not v or v in (ANY, "(all)")) else [x for x in v.split(SEP) if x]


class MultiPick(tk.Frame):
    def __init__(self, master, var: tk.StringVar, values: Iterable[str] = (), width: int = 14, empty: str = ANY, bg="#FFFFFF"):
        super().__init__(master, bg=bg)
        self.var, self.empty, self._values, self._pop = var, empty, list(values), None
        self.btn = tk.Button(self, text="", anchor="w", relief="solid", bd=1, bg="#FFFFFF", fg="#22293A", padx=6, pady=1,
                             font=("Segoe UI", 9), width=width, cursor="hand2", command=self.toggle)
        self.btn.pack(side="left")
        tk.Label(self, text="▾", bg="#FFFFFF", fg="#78909C", font=("Segoe UI", 8)).pack(side="left", padx=(0, 0))
        var.trace_add("write", lambda *a: self._label())
        self._label()

    # ------------------------------------------------------------------ values (same call style as ttk.Combobox)
    def set_values(self, values: Iterable[str]):
        self._values = [v for v in values if v != ANY]
        keep = [x for x in selected(self.var) if x in self._values]
        if keep != selected(self.var):
            self.var.set(SEP.join(keep) if keep else ANY)

    def values(self) -> List[str]:
        return list(self._values)

    def _label(self):
        sel = selected(self.var)
        self.btn.configure(text=self.empty if not sel else (sel[0] if len(sel) == 1 else f"{sel[0]} +{len(sel) - 1}"),
                           fg="#22293A" if not sel else "#1565C0")

    # ------------------------------------------------------------------ pop-up
    def toggle(self):
        if self._pop is not None:
            self._close()
            return
        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg="#B0BEC5")
        inner = tk.Frame(pop, bg="#FFFFFF", padx=6, pady=4)
        inner.pack(padx=1, pady=1)
        self._vars, self._btns = {}, {}
        cur = set(selected(self.var))
        self._q = tk.StringVar()
        sr = tk.Frame(inner, bg="#FFFFFF")
        sr.pack(fill="x", pady=(0, 4))
        tk.Label(sr, text="Search:", bg="#FFFFFF", fg="#78909C", font=("Segoe UI", 9)).pack(side="left")
        ent = tk.Entry(sr, textvariable=self._q, relief="solid", bd=1, font=("Segoe UI", 9))
        ent.pack(side="left", fill="x", expand=True, padx=(4, 0))
        wrap = tk.Frame(inner, bg="#FFFFFF")
        wrap.pack(fill="both", expand=True)
        rows = min(len(self._values), 14)
        cv = tk.Canvas(wrap, bg="#FFFFFF", highlightthickness=0, width=max(190, 9 * max([len(v) for v in self._values] + [12])),
                       height=max(rows, 3) * 25)
        sb = tk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        lst = tk.Frame(cv, bg="#FFFFFF")
        cv.create_window((0, 0), window=lst, anchor="nw")
        cv.pack(side="left", fill="both", expand=True)
        if len(self._values) > 14:
            sb.pack(side="right", fill="y")
        for v in self._values:
            bv = tk.BooleanVar(value=v in cur)
            self._vars[v] = bv
            self._btns[v] = tk.Checkbutton(lst, text=v, variable=bv, anchor="w", bg="#FFFFFF", activebackground="#E3F2FD",
                                           font=("Segoe UI", 9), command=self._apply)
        self._cv, self._lst = cv, lst

        def relayout(*_):
            q = self._q.get().strip().lower()
            for v, b in self._btns.items():
                b.pack_forget()
                if not q or q in v.lower():
                    b.pack(fill="x")
            lst.update_idletasks()
            cv.configure(scrollregion=(0, 0, lst.winfo_reqwidth(), lst.winfo_reqheight()))
            cv.yview_moveto(0)

        def wheel(e):
            if lst.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(-1 if e.delta > 0 else 1, "units")
        pop.bind_all("<MouseWheel>", wheel)
        self._q.trace_add("write", relayout)
        relayout()
        foot = tk.Frame(inner, bg="#FFFFFF")
        foot.pack(fill="x", pady=(4, 0))
        tk.Button(foot, text="Clear", relief="flat", bg="#ECEFF4", command=self._clear, padx=8).pack(side="left")
        tk.Button(foot, text="Done", relief="flat", bg="#1565C0", fg="white", command=self._close, padx=10).pack(side="right")
        pop.update_idletasks()
        x, y = self.btn.winfo_rootx(), self.btn.winfo_rooty() + self.btn.winfo_height()
        h = pop.winfo_reqheight()
        if y + h > self.winfo_screenheight() - 40:  # not enough room below: open upwards
            y = max(0, self.btn.winfo_rooty() - h)
        pop.geometry(f"+{x}+{y}")
        pop.bind("<Escape>", lambda e: self._close())
        pop.focus_force()
        ent.focus_set()
        pop.bind("<FocusOut>", self._lost_focus)
        self._pop = pop

    def _lost_focus(self, _e=None):
        # close when the focus leaves the pop-up (but not when it moves between its own checkbuttons)
        self.after(120, self._check_focus)

    def _check_focus(self):
        if self._pop is None:
            return
        f = self._pop.focus_get()
        if f is None or not str(f).startswith(str(self._pop)):
            self._close()

    def _apply(self):
        on = [v for v in self._values if self._vars[v].get()]
        self.var.set(SEP.join(on) if on else ANY)

    def _clear(self):
        for bv in self._vars.values():
            bv.set(False)
        self._apply()

    def _close(self):
        if self._pop is not None:
            try:
                self._pop.unbind_all("<MouseWheel>")
                self._pop.destroy()
            except tk.TclError:
                pass
        self._pop = None
