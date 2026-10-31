#!/usr/bin/env python3
"""
Project actions inside the Review & discuss screen: add, edit, duplicate, retire / restore, delete, rename, move, undo - the same
operations as 'Manage projects', for the project selected in the Desk. (Mixed into DeskPanel; it also gives the existing
EditDialog / BackupDialog the small interface they expect from their parent.)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional

import deckcore as core
import projmgr as pm

NL = chr(10)


class ActionsMixin:
    # ---- interface used by manage_dialog.EditDialog / BackupDialog
    @property
    def items(self) -> List[dict]:
        return self.all_projects

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

    def _after(self, text: str, keys: Optional[List[str]] = None):
        """A deck change was made: refresh the generate list and this Desk, keep the project selected."""
        try:
            self.app.load_audience(preserve=True)
        except Exception:
            pass
        self.reload()
        if keys and keys[0] in self.tree.get_children():
            self.tree.selection_set(keys[0])
            self.tree.see(keys[0])
        self.set_status(text)

    # ---- toolbar
    def build_actions_bar(self, parent):
        tb = tk.Frame(parent, bg="#F4F6FA")
        tb.pack(fill="x", pady=(0, 5))
        tk.Button(tb, text="+ Add project", command=self.add_project, bg="#1565C0", fg="white", relief="flat", padx=12, pady=2,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="left")
        for txt, fn in (("Edit", self.edit_project), ("Boss", self.change_boss), ("Duplicate", self.duplicate_project), ("Retire / Restore", self.retire_project),
                        ("Delete", self.delete_project)):
            b = tk.Button(tb, text=txt, command=fn, bg="#FFFFFF", fg="#B71C1C" if txt == "Delete" else "#22293A", relief="groove", bd=1,
                          padx=9, pady=1, cursor="hand2", font=("Segoe UI", 9))
            b.pack(side="left", padx=(5, 0))
        mb = tk.Menubutton(tb, text="More ▾", bg="#FFFFFF", relief="groove", bd=1, padx=9, pady=1, cursor="hand2", font=("Segoe UI", 9))
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Rename the project key…", command=self.rename_project)
        m.add_separator()
        for lbl, w in (("Move up in the deck", "up"), ("Move down in the deck", "down"), ("Move to the start", "top"), ("Move to the end", "bottom")):
            m.add_command(label=lbl, command=lambda w=w: self.move_project(w))
        m.add_separator()
        m.add_command(label="Undo / restore an earlier deck…", command=self.undo_deck)
        m.add_command(label="Open the full 'Manage projects' window (bulk edit)…", command=self.open_full_manage)
        mb.configure(menu=m)
        mb.pack(side="left", padx=(5, 0))

    def _one(self) -> Optional[dict]:
        p = self.project()
        if not p:
            messagebox.showinfo("Select a project", "Select a project in the list first.", parent=self)
        return p

    # ---- actions
    def add_project(self):
        from add_project_dialog import AddProjectDialog
        before = {p["id"] for p in self.all_projects}

        def done():
            self.app.load_audience(preserve=True)
            self.reload()
            new = [p["id"] for p in self.all_projects if p["id"] not in before]
            if new:
                self.f_view.set("all")
                self.f_lead.set("All")
                self.f_text.set("")
                self.render()
                if new[0] in self.tree.get_children():
                    self.tree.selection_set(new[0])
                    self.tree.see(new[0])
            self.set_status("New project added to the deck - it is in this list now; add its needs and comments here.")
        AddProjectDialog(self.app, self.aud, [p for p in self.all_projects if not p["retired"]], on_done=done)

    def edit_project(self):
        p = self._one()
        if p:
            from manage_dialog import EditDialog
            EditDialog(self, [p["id"]])

    def change_boss(self):
        p = self._one()
        if p:
            from boss_dialog import BossDialog
            BossDialog(self, [p], on_done=self.reload)

    def duplicate_project(self):
        p = self._one()
        if not p:
            return
        new = simpledialog.askstring("Duplicate", "Key for the copy of '" + p["id"] + "':", initialvalue=p["id"] + "_copy", parent=self)
        if new and self._run(pm.duplicate_project, self.aud, p["id"], new) is not None:
            self._after("Copied. Open the base deck in PowerPoint to edit the copy's text.", [core.norm_id(new)])

    def retire_project(self):
        p = self._one()
        if not p:
            return
        restore = bool(p.get("retired"))
        if not restore and not messagebox.askyesno(
                "Retire?", f"Retire '{p['name']}'?" + NL + NL + "It disappears from the lists and is never put in a deck, but its slides and all "
                "your Desk notes stay. Restore it any time (tick 'retired' to see it).", parent=self):
            return
        if self._run(pm.set_retired, self.aud, [p["id"]], not restore) is not None:
            self._after(("Restored " if restore else "Retired ") + f"'{p['name']}'.", [p["id"]] if (restore or self.show_retired.get()) else None)

    def delete_project(self):
        p = self._one()
        if not p:
            return
        win = tk.Toplevel(self)
        win.title("Delete from the deck")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        tk.Label(win, justify="left", padx=14, pady=10, font=("Segoe UI", 10, "bold"), text=f"Delete  '{p['name'][:70]}'  from the base deck?").pack(anchor="w")
        what = tk.StringVar(value="all")
        for v, t in (("all", "The WHOLE project (named + unnamed slides)"), ("named", "Only the NAMED slide(s)"), ("unnamed", "Only the UNNAMED slide(s)")):
            tk.Radiobutton(win, text=t, value=v, variable=what, anchor="w").pack(anchor="w", padx=20)
        tk.Label(win, fg="#546E7A", justify="left", padx=14, pady=8,
                 text="The slides are removed from the base deck (a backup is kept: More > Undo brings them back)." + NL +
                      "Your Desk notes (needs, comments, actions, history) are NOT deleted." + NL +
                      "Tip: 'Retire' is gentler if you may need the project again.").pack(anchor="w")

        def go():
            versions = None if what.get() == "all" else [what.get()]
            win.destroy()
            res = self._run(pm.delete_projects, self.aud, [p["id"]], versions, lambda m: None)
            if res:
                self.cur = None
                self._after(f"Deleted {len(res['slides'])} slide(s) of '{p['name']}'.")
        f = tk.Frame(win, pady=8)
        f.pack(fill="x")
        tk.Button(f, text="Delete", command=go, bg="#C62828", fg="white", relief="flat", padx=14).pack(side="right", padx=10)
        ttk.Button(f, text="Cancel", command=win.destroy).pack(side="right")

    def rename_project(self):
        p = self._one()
        if not p:
            return
        new = simpledialog.askstring("Rename key", "New project key for '" + p["id"] + "':" + NL + "(its Excel details and your Desk notes are carried over)",
                                     initialvalue=p["id"], parent=self)
        if new and core.norm_id(new) != p["id"]:
            if self._run(lambda: (pm.rename_project(self.aud, p["id"], new), True)[1]):
                self.cur = core.norm_id(new)
                self._after("Renamed to '" + core.norm_id(new) + "'.", [core.norm_id(new)])

    def move_project(self, where: str):
        p = self._one()
        if p:
            res = self._run(pm.move_projects, self.aud, [p["id"]], where)
            if res is not None:
                self._after("Moved in the deck order." if res.get("moved") else "Already there.", [p["id"]])

    def undo_deck(self):
        from manage_dialog import BackupDialog
        BackupDialog(self)

    def open_full_manage(self):
        from manage_dialog import ManageDialog
        dlg = ManageDialog(self.app, self.aud)
        dlg.bind("<Destroy>", lambda e: self.after(200, self.reload) if e.widget is dlg else None)
