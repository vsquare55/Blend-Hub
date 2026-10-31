#!/usr/bin/env python3
"""
EPC / Investor deck generator.

    generate_client_deck.py                      -> opens the selection window (default)
    generate_client_deck.py --console            -> text-mode questions
    generate_client_deck.py --audience EPC --client "Acme" --from-excel
    generate_client_deck.py --audience Investor --client "Fund X" --ids togo_161kv,guinea_water --version unnamed
    generate_client_deck.py --list --audience EPC
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deckcore as core  # noqa: E402


def _utf8():
    for s in (sys.stdout, sys.stderr, sys.stdin):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def list_projects(audience: str) -> None:
    data = core.load_projects(audience)
    print(f"\n{audience}: {len(data['projects'])} projects\n")
    print("{:<3} {:<5} {:<22} {:<8} {:<8} {}".format("#", "Show", "ID", "Category", "Version", "Name"))
    print("-" * 100)
    for i, p in enumerate(data["projects"], 1):
        avail = ("N" if p["has_named"] else "-") + ("U" if p["has_unnamed"] else "-")
        print("{:<3} {:<5} {:<22} {:<8} {:<8} {}  [{}]".format(
            i, "YES" if p["include"] else "no", p["id"], p["category"], p["version"], p["name"][:60], avail))
    for w in data["warnings"]:
        print("  !", w)
    print()


def console_flow() -> None:
    names = core.audience_names()
    print("\nWho is this presentation for?")
    for i, n in enumerate(names, 1):
        print(f"  {i}. {core.audience_cfg(n)['label']}  ({n})")
    aud = None
    while aud is None:
        a = input("Choose: ").strip()
        if a.isdigit() and 1 <= int(a) <= len(names):
            aud = names[int(a) - 1]
        elif a in names:
            aud = a
    client = input("Client / recipient name: ").strip() or "Client"
    data = core.load_projects(aud)
    projs = data["projects"]
    list_projects(aud)
    print("Select projects: numbers / ranges (1,3,5-8) / all / default (Excel Include column)")
    choice = input("Selection: ").strip().lower() or "default"
    if choice == "default":
        sel = core.default_selection(projs)
    else:
        idx = set()
        for part in choice.replace(" ", "").split(","):
            if part == "all":
                idx.update(range(1, len(projs) + 1))
            elif "-" in part:
                a, _, b = part.partition("-")
                if a.isdigit() and b.isdigit():
                    idx.update(range(int(a), int(b) + 1))
            elif part.isdigit():
                idx.add(int(part))
        sel = [{"id": projs[i - 1]["id"], "category": projs[i - 1]["category"], "version": projs[i - 1]["version"]}
               for i in sorted(idx) if 1 <= i <= len(projs)]
    v = input("Version for ALL selected: [N]amed / [U]nnamed / [K]eep each project's default: ").strip().lower()[:1]
    if v in ("n", "u"):
        for s in sel:
            s["version"] = "Named" if v == "n" else "Unnamed"
    core.generate(aud, client, sel)


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--audience", "-a", help="EPC or Investor")
    ap.add_argument("--client", "-c")
    ap.add_argument("--ids", help="comma-separated project IDs")
    ap.add_argument("--version", choices=["named", "unnamed", "registry"], default="registry",
                    help="override Named/Unnamed for every selected project (default: use the registry)")
    ap.add_argument("--show-value", action="store_true", help="show the optional 'Indicative value' box (default: hidden)")
    ap.add_argument("--from-excel", action="store_true", help="use the Include/Category/Version columns of the registry")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--console", action="store_true")
    args = ap.parse_args()
    try:
        if args.list:
            list_projects(args.audience or core.audience_names()[0])
            return 0
        if args.from_excel or args.ids:
            aud = args.audience or core.audience_names()[0]
            data = core.load_projects(aud)
            if args.ids:
                want = [core.norm_id(x) for x in args.ids.split(",") if x.strip()]
                by_id = {p["id"]: p for p in data["projects"]}
                sel = [{"id": i, "category": by_id[i]["category"], "version": by_id[i]["version"]} for i in want if i in by_id]
                for i in want:
                    if i not in by_id:
                        print(f"  ! unknown project id '{i}'")
            else:
                sel = core.default_selection(data["projects"])
            if args.version != "registry":
                for s in sel:
                    s["version"] = args.version.capitalize()
            for s_ in sel:
                s_["show_value"] = args.show_value
            core.generate(aud, args.client or "Client", sel)
            return 0
        if args.console:
            console_flow()
            return 0
        try:
            import deck_gui
        except Exception as exc:
            print(f"(window not available: {exc}) - using text mode")
            console_flow()
            return 0
        deck_gui.main(args.audience)
        return 0
    except core.DeckError as exc:
        print("\n*** PROBLEM ***\n" + str(exc))
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        import traceback
        print("\n*** UNEXPECTED ERROR ***\n", exc)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
