#!/usr/bin/env python3
"""Add-new-project wizard: asks Named / Unnamed / Both, then builds the slide(s) from a form (or duplicates / tags)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import deckcore as core
import projmgr as pm
import sectors

NL = chr(10)
VERSION_CHOICES = [
    ("both", "Named + Unnamed slides  (recommended - the unnamed one is generated from the same text)"),
    ("named", "Named slide only"),
    ("unnamed", "Unnamed slide only"),
    ("single", "ONE slide used for both versions  (nothing identifying on it)"),
]
CATS = ["(system default)"] + core.CATEGORY_ORDER
END = "(at the end of the projects)"
SECT = ["(decide automatically)"] + sectors.SECTORS


class Counter:
    """An entry with a live 'n / limit' counter that turns red when the text would not fit the slide."""

    def __init__(self, parent, row, label, limit=None, width=70, col=0):
        self.var = tk.StringVar()
        self.limit = limit
        tk.Label(parent, text=label, anchor="w").grid(row=row, column=col, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=self.var, width=width).grid(row=row, column=col + 1, sticky="w", padx=6)
        self.lbl = tk.Label(parent, text="", fg="#78909C", width=9, anchor="w")
        self.lbl.grid(row=row, column=col + 2, sticky="w")
        if limit:
            self.var.trace_add("write", lambda *a: self._upd())
            self._upd()

    def _upd(self):
        n = len(self.var.get())
        self.lbl.configure(text=f"{n}/{self.limit}", fg="#C62828" if n > self.limit else "#78909C")

    def get(self):
        return self.var.get().strip()


class AddProjectDialog(tk.Toplevel):
    def __init__(self, app, audience: str, projects: list, on_done=None):
        super().__init__(app)
        self.app, self.aud, self.projects, self.on_done = app, audience, projects, on_done
        import listutil
        self.sources_known = listutil.distinct_sources(projects)
        self.title("Add new project")
        self.geometry("980x720")
        self.transient(app)
        self.grab_set()

        top = tk.LabelFrame(self, text=" 1. Which slides do you want to add? ", padx=10, pady=6)
        top.pack(fill="x", padx=12, pady=(10, 4))
        self.versions = tk.StringVar(value="both")
        for val, txt in VERSION_CHOICES:
            tk.Radiobutton(top, text=txt, value=val, variable=self.versions, anchor="w").pack(anchor="w")

        meth = tk.LabelFrame(self, text=" 2. How? ", padx=10, pady=6)
        meth.pack(fill="x", padx=12, pady=4)
        self.method = tk.StringVar(value="form")
        for val, txt in (("form", "Fill in a form - the tool builds the slide(s) in the standard layout"),
                         ("dup", "Duplicate an existing project's slides (then edit the text in PowerPoint)"),
                         ("tag", "I already added slides in PowerPoint - tag them")):
            tk.Radiobutton(meth, text=txt, value=val, variable=self.method, anchor="w", command=self._method).pack(anchor="w")

        self.body = tk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=12, pady=4)
        self._build_form()
        self._build_dup()
        btn = tk.Frame(self, pady=8)
        btn.pack(fill="x", padx=12)
        self.msg = tk.Label(btn, text="", fg="#C62828", anchor="w")
        self.msg.pack(side="left", fill="x", expand=True)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="right")
        self.go = ttk.Button(btn, text="Create slides", command=self.create)
        self.go.pack(side="right", padx=8)
        self.prev = ttk.Button(btn, text="Preview both versions", command=self.preview)
        self.prev.pack(side="right")
        # buttons must stay visible on short screens: pin them to the bottom, the form takes the leftover space
        btn.pack_forget()
        self.body.pack_forget()
        btn.pack(side="bottom", fill="x", padx=12)
        self.body.pack(fill="both", expand=True, padx=12, pady=4)
        self.geometry(f"980x{min(720, max(520, self.winfo_screenheight() - 100))}+10+5")
        self._method()

    # ------------------------------------------------------------------ form
    def _build_form(self):
        self.form = ttk.Notebook(self.body)
        # tab 1
        t1 = tk.Frame(self.form, padx=10, pady=8)
        self.form.add(t1, text=" Basics ")
        self.f_title = Counter(t1, 0, "Title (slide heading) - REQUIRED:", pm.LIMITS["title"])
        self.f_sub = Counter(t1, 1, "Subtitle (optional):", pm.LIMITS["sub"])
        self.f_key = Counter(t1, 2, "Project key (short, no spaces):", None, width=36)
        tk.Label(t1, text="(auto-filled from the title)", fg="#78909C").grid(row=2, column=2, sticky="w")
        self.f_country = Counter(t1, 3, "Country (real name):", None, width=30)
        self.f_region = Counter(t1, 4, "Region for the UNNAMED slide:", None, width=30)
        self.f_model = Counter(t1, 5, "Model (e.g. EPC+F, PPP, IPP):", None, width=30)
        tk.Label(t1, text="Category:").grid(row=6, column=0, sticky="w", pady=3)
        self.f_cat = tk.StringVar(value=CATS[0])
        ttk.Combobox(t1, textvariable=self.f_cat, values=CATS, state="readonly", width=20).grid(row=6, column=1, sticky="w", padx=6)
        tk.Label(t1, text="Sector:").grid(row=6, column=2, sticky="w", padx=(14, 2))
        self.f_sector = tk.StringVar(value=SECT[0])
        ttk.Combobox(t1, textvariable=self.f_sector, values=SECT, state="readonly", width=22).grid(row=6, column=3, sticky="w")
        tk.Label(t1, text="Place it after:").grid(row=7, column=0, sticky="w", pady=3)
        self.f_after = tk.StringVar(value=END)
        ttk.Combobox(t1, textvariable=self.f_after, values=[END] + [p["name"][:70] + "  [" + p["id"] + "]" for p in self.projects],
                     state="readonly", width=68).grid(row=7, column=1, sticky="w", padx=6)
        self.f_value = Counter(t1, 8, "Indicative value (optional):", pm.LIMITS["value"])
        tk.Label(t1, text="Source / origination (optional):").grid(row=11, column=0, sticky="w", pady=(10, 0))
        self.f_source = tk.StringVar()
        ttk.Combobox(t1, textvariable=self.f_source, values=self.sources_known, width=48).grid(row=11, column=1, sticky="w", padx=6, pady=(10, 0))
        tk.Label(t1, text="who brought it - separate several with /", fg="#78909C").grid(row=11, column=2, sticky="w", pady=(10, 0))
        tk.Label(t1, text="Shown only when you tick 'Value' for this project in the main list.", fg="#78909C").grid(row=9, column=1, sticky="w", padx=6)
        tk.Label(t1, text="Only the TITLE is required. Anything you leave empty (here or on the other tabs) is simply left off the slide.",
                 fg="#2E7D32", font=("Segoe UI", 10, "bold")).grid(row=10, column=0, columnspan=3, sticky="w", pady=(14, 0))
        self.f_title.var.trace_add("write", lambda *a: self._autokey())
        # tabs 2 / 3
        self.cards = {}
        for key, label in (("A", " Card A (left) "), ("B", " Card B (right) ")):
            t = tk.Frame(self.form, padx=10, pady=8)
            self.form.add(t, text=label)
            c = {"head": Counter(t, 0, "Heading:", pm.LIMITS["head"], width=50),
                 "sub": Counter(t, 1, "Sub-heading:", pm.LIMITS["csub"], width=70)}
            tk.Label(t, text="Bullets (one per line,\n'Label: text'; max 4):", anchor="w", justify="left").grid(row=2, column=0, sticky="nw", pady=3)
            c["bullets"] = tk.Text(t, width=78, height=7, wrap="word", font=("Segoe UI", 10))
            c["bullets"].grid(row=2, column=1, columnspan=2, sticky="w", padx=6)
            c["chip"] = Counter(t, 3, "Dark chip text:", pm.LIMITS["chip"], width=50)
            c["hl"] = Counter(t, 4, "White highlight line:", pm.LIMITS["hl"], width=60)
            self.cards[key] = c
        # tab 4
        t4 = tk.Frame(self.form, padx=10, pady=8)
        self.form.add(t4, text=" Snapshot & footer ")
        tk.Label(t4, text="Snapshot boxes - use 0 to 4 (big text | small text):", anchor="w").grid(row=0, column=0, columnspan=3, sticky="w")
        self.steps = []
        for i in range(4):
            a = Counter(t4, 1 + i, f"Box {i + 1}:  big", pm.LIMITS["step"], width=34)
            b = tk.StringVar()
            tk.Label(t4, text="small").grid(row=1 + i, column=3, padx=(10, 2))
            ttk.Entry(t4, textvariable=b, width=34).grid(row=1 + i, column=4, sticky="w")
            self.steps.append((a, b))
        self.f_strip = Counter(t4, 6, "Strip label (optional):", pm.LIMITS["strip"], width=50)
        self.f_footer = Counter(t4, 7, "Footer line (optional):", pm.LIMITS["footer"], width=70)
        tk.Label(t4, text="Leave anything empty and it is left off the slide (fewer than 4 boxes re-space themselves).", fg="#78909C").grid(row=8, column=1, sticky="w", padx=6)
        # tab 5
        t5 = tk.Frame(self.form, padx=10, pady=8)
        self.form.add(t5, text=" Words to hide (unnamed) ")
        tk.Label(t5, justify="left", anchor="w", text=(
            "The unnamed slide is generated from the SAME text, with these replacements." + NL +
            "The country is replaced by the region automatically. List anything else that identifies the project," + NL +
            "one per line as   word = replacement   (e.g.  Lake Turkana = remote northern site,  KenGen = the state utility)." + NL +
            "A word with no replacement ( word = ) is simply removed.")).pack(anchor="w")
        self.f_hide = tk.Text(t5, width=80, height=10, font=("Segoe UI", 10))
        self.f_hide.pack(anchor="w", pady=6)

    def _build_dup(self):
        self.dup = tk.Frame(self.body)
        tk.Label(self.dup, text="Copy this project:").grid(row=0, column=0, sticky="w", pady=6)
        self.d_src = tk.StringVar()
        ttk.Combobox(self.dup, textvariable=self.d_src, values=[p["name"][:70] + "  [" + p["id"] + "]" for p in self.projects],
                     state="readonly", width=80).grid(row=0, column=1, sticky="w", padx=6)
        tk.Label(self.dup, text="New project key:").grid(row=1, column=0, sticky="w", pady=6)
        self.d_key = tk.StringVar()
        ttk.Entry(self.dup, textvariable=self.d_key, width=36).grid(row=1, column=1, sticky="w", padx=6)
        tk.Label(self.dup, justify="left", fg="#546E7A", text=(
            NL + "The slides are copied right after the original and tagged with the new key. Afterwards open the base deck in PowerPoint" + NL +
            "and edit the text (and anonymise the unnamed copy). Which versions are copied follows choice 1 above" + NL +
            "('Named + Unnamed' copies every version the original has).")).grid(row=2, column=0, columnspan=2, sticky="w")

    def _method(self):
        for w in (self.form, self.dup):
            w.pack_forget()
        m = self.method.get()
        if m == "form":
            self.form.pack(fill="both", expand=True)
        elif m == "dup":
            self.dup.pack(fill="both", expand=True)
        self.prev.configure(state="normal" if m == "form" else "disabled")
        self.go.configure(text={"form": "Create slides", "dup": "Duplicate", "tag": "Open the tag window"}[m])

    def _autokey(self):
        """Keep the key in step with the title until the user types their own key."""
        if getattr(self, "_keyauto", True):
            k = core.norm_id(self.f_title.get())  # keep the country in the key: readable and unique
            self._autoval = k if len(k) <= 36 else k[:36].rsplit("_", 1)[0]
            self.f_key.var.set(self._autoval)
            if not getattr(self, "_traced", False):
                self._traced = True
                self.f_key.var.trace_add("write", lambda *a: setattr(
                    self, "_keyauto", self.f_key.var.get() == getattr(self, "_autoval", "")))

    # ------------------------------------------------------------------ spec
    def _spec(self) -> dict:
        def card(c):
            return {"head": c["head"].get(), "sub": c["sub"].get(), "bullets": c["bullets"].get("1.0", "end").strip(),
                    "chip": c["chip"].get(), "hl": c["hl"].get()}
        hide = []
        for ln in self.f_hide.get("1.0", "end").splitlines():
            if "=" in ln:
                a, b = ln.split("=", 1)
                if a.strip():
                    hide.append((a.strip(), b.strip()))
        country = self.f_country.get()
        title = self.f_title.get()
        footer = self.f_footer.get()  # optional: empty = no footer bar on the slide
        after = self.f_after.get()
        after_key = None if after == END else after.rsplit("[", 1)[-1].rstrip("]")
        return {"key": self.f_key.get(), "country": country, "region": self.f_region.get(), "model": self.f_model.get(),
                "sector": "" if self.f_sector.get() == SECT[0] else self.f_sector.get(), "source": self.f_source.get().strip(),
                "category": None if self.f_cat.get() == CATS[0] else self.f_cat.get(), "hide": hide, "title": title,
                "sub": self.f_sub.get(), "A": card(self.cards["A"]), "B": card(self.cards["B"]),
                "steps": [(a.get(), b.get().strip()) for a, b in self.steps],
                "strip": self.f_strip.get(), "footer": footer,
                "value": self.f_value.get(), "_after": after_key}

    def _problems(self, spec):
        errs, warns = [], []
        if not spec["key"]:
            errs.append("Project key is empty.")
        if self.versions.get() in ("both", "unnamed") and not (spec["country"] and spec["region"]) and not spec["hide"]:
            warns.append("No country/region given: nothing will be replaced on the unnamed slide.")
        if not spec["title"].strip():
            errs.append("The title (slide heading) is required - everything else is optional.")
        d = pm.build_data(spec)
        e2, w2 = pm.validate(d, self.versions.get())
        errors = [e for e in dict.fromkeys(errs + e2) if not (not spec["title"].strip() and e.startswith(("Project key", "The title (heading)")))]
        return d, errors, list(dict.fromkeys(warns + w2))

    def preview(self):
        spec = self._spec()
        d, errs, warns = self._problems(spec)
        import build_new_slides as bns
        terms = core.load_config()["sensitive_terms"] + ([spec["country"]] if spec["country"] else [])
        win = tk.Toplevel(self)
        win.title("Preview")
        win.geometry("1000x640")
        txt = tk.Text(win, wrap="word", font=("Consolas", 10))
        txt.pack(fill="both", expand=True)
        out = []
        if errs:
            out.append("PROBLEMS (must fix):" + NL + NL.join("  - " + e for e in errs) + NL)
        if warns:
            out.append("NOTES:" + NL + NL.join("  - " + w for w in warns) + NL)
        for v in (["named", "unnamed"] if self.versions.get() == "both" else ["named" if self.versions.get() in ("named", "single") else "unnamed"]):
            R = lambda t: bns.render(t, v)  # noqa: E731
            lines = [f"==== {v.upper()} ====", "Title:    " + R(d["title"]), "Subtitle: " + R(d["sub"])]
            for nm in ("A", "B"):
                c = d[nm]
                lines += [f"-- Card {nm}: {R(c[0])}  ({R(c[1])})"] + [f"     • {R(a)}{R(b)}" for a, b in c[2]] + [f"     chip: {R(c[3])}   highlight: {R(c[4])}"]
            lines += ["Snapshot: " + "  |  ".join((R(a) + " / " + R(b)) for a, b in d["steps"]), "Footer:   " + R(d["footer"]),
                      "Value:    " + (R(d["value"]) if d.get("value") else "(none)")]
            blob = " ".join(lines)
            if v == "unnamed" or self.versions.get() == "single":
                hits = core.find_leaks(blob, terms)
                lines.append("LEAK CHECK: " + ("clean" if not hits else "FOUND " + ", ".join(hits)))
            out.append(NL.join(lines) + NL)
        txt.insert("1.0", NL.join(out))
        txt.configure(state="disabled")

    def create(self):
        m = self.method.get()
        if m == "tag":
            self.destroy()
            from tag_dialog import TagDialog
            TagDialog(self.app, self.aud)
            return
        vers = self.versions.get()
        try:
            if m == "dup":
                src = self.d_src.get().rsplit("[", 1)[-1].rstrip("]") if self.d_src.get() else ""
                if not src or not self.d_key.get().strip():
                    self.msg.configure(text="Choose the project to copy and enter a new key.")
                    return
                want = None if vers == "both" else (["named", "single"] if vers in ("named", "single") else ["unnamed"])
                pm.duplicate_project(self.aud, src, self.d_key.get(), want)
                done = f"Copied into '{core.norm_id(self.d_key.get())}'. Open the base deck in PowerPoint to edit the text."
            else:
                spec = self._spec()
                d, errs, warns = self._problems(spec)
                if errs:
                    messagebox.showerror("Fix these first", NL.join("- " + e for e in errs), parent=self)
                    return
                if warns and not messagebox.askyesno("Continue?", NL.join("- " + w for w in warns) + NL + NL + "Create anyway?", parent=self):
                    return
                lab = dict(VERSION_CHOICES)[vers].split("(")[0].strip()
                if not messagebox.askyesno("Create slides?", f"Create '{spec['title']}'" + NL + f"Slides: {lab}" + NL + NL +
                                           "The base deck is backed up first.", parent=self):
                    return
                self.configure(cursor="watch")
                self.update_idletasks()
                pm.add_project(self.aud, spec, vers, spec["_after"])
                done = f"Created '{d['key']}'."
        except core.DeckError as exc:
            self.configure(cursor="")
            messagebox.showerror("Not created", str(exc), parent=self)
            return
        self.configure(cursor="")
        messagebox.showinfo("Done", done + NL + NL + "It appears in the project list unticked and marked NEW.", parent=self)
        if self.on_done:
            self.on_done()
        self.destroy()
