# DealDeck Studio
*Partner & investor decks, built from one master.*

Builds a recipient-specific deck from a master base deck. Start it with `START_HERE.bat` (or run
`CREATE_DESKTOP_SHORTCUT.bat` once to get a "DealDeck Studio" icon on your Desktop). You choose:

1. **Who it is for** - EPC contractor or Investor (same project list and slides; only the output file name differs)
2. **Client name** - replaces the placeholder (e.g. "Omatapalo") throughout
3. **Which projects** - tick/untick, set **Category** (Closed / Active / BIP / Hold) and
   **Version** (Named / Unnamed) per project. One slide per project - never both versions.

The deck is assembled as: boilerplate -> auto Project Index -> category dividers with the chosen
projects -> closing slide. Speaker-note tags never reach the output.

## Everyday use

Double-click **START_HERE.bat**, then follow steps 1-2-3 in the window and press *Generate deck*.
Output lands in `output\`. Your selection is remembered (see *Load saved selection*).

## Folder map

| Item | Purpose |
|---|---|
| `START_HERE.bat` | the app |
| `REPLACE_BASE.bat` | safely swap in a new base deck (EPC or Investor) |
| `SYNC_FROM_PPTX.bat` | refresh the Excel from the base decks and print a health report |
| `MAKE_PORTABLE.bat` | builds a self-contained copy (with its own Python) in `dist\` to run on any PC |
| `base\EPC_Partnership_Base.pptx` | THE master deck - used for both EPC and Investor decks |
| `base\_archive\` | the deck as it was before each change - this is the **Undo** list in Manage projects |
| `dist\` | the latest portable package (zip) |
| `data\` | the **Project Desk** database (`desk.db`), a daily backup in `dataackups\` and `Desk_snapshot.xlsx` (plain-Excel copy of everything, refreshed every time you close the Desk). Internal - never goes into a deck and is not copied into the portable package |
| `projects_registry.xlsx` | one sheet per audience: names, default category/version/include, model, country |
| `config.json` | audiences, client placeholder text(s), footer text, words that must not appear in unnamed slides |
| `backups\`, `presets\`, `output\` | Excel backups, saved selections, generated decks |
| `scripts\` | the program itself (do not edit) |
| `_OLD_FILES_safe_to_ignore\` | everything old / unused, kept only in case you want it back - safe to delete |

## Replacing a base deck

Use **REPLACE_BASE.bat** (or the button in the app). It checks the new deck first (must contain
tagged project slides), archives the old deck, installs the new one and re-syncs Excel. Your Excel
names / categories / versions are kept for projects whose ID is unchanged. Simply overwriting the
file in `base\` also works - the tool re-syncs on every start.

Tagging rules for project slides: see `HOW_TO_TAG_IN_PPTX.txt`
(`ID: x_named` / `ID: x_unnamed` in the speaker notes).

## Safety nets

* **Never lets a named slide into an unnamed request** - a project with no unnamed slide is skipped (with a message).
* **Leak check** - unnamed slides are scanned for country / client words (`sensitive_terms` in `config.json`
  plus the project's Country in Excel); the app warns before you generate.
* **No duplicates** - each project appears once, in exactly one version.
* **Self-check** - the finished file is re-opened and verified (slide count, no leftover notes) before it replaces anything.
* **Locked files** - if Excel or the output deck is open, the tool carries on and tells you (e.g. saves with a time-stamped name).
* **Backups** - `projects_registry.xlsx` is backed up before every write; replaced base decks are archived.
* **No silent truncation** - the Project Index flows into extra columns/pages as needed.

## Requirements

Python 3 with `python-pptx` and `openpyxl` (installed automatically on first run).
Not checked automatically: names baked into images or charts on an unnamed slide - eyeball those.

## Indicative value (per project, off by default)

Any shape named `VALUE` on a slide is stripped from the generated deck unless **Value** is ticked
for that project in the window. All 39 slides added from the pipeline sheet carry one.

## Adding more projects from a sheet

`scripts/new_projects_data.py` holds the content of the 39 projects added on top of the original 21
(one entry per project, `{{named|unnamed}}` tokens for the two versions). `scripts/build_new_slides.py`
clones the BESS slide as a template, fills it by shape name, tags the speaker notes and refuses to
build if a named-side word appears on an unnamed slide.

## Adding / removing projects in the base deck (the app follows automatically)

* **Add:** put the project's slide(s) in the base deck (PowerPoint), save. The app notices within ~3 seconds and
  shows a red **Tag new slides (n)** button. Click it, select the slide, type a project key, choose Named /
  Unnamed / Same-for-both, press Apply (do the named and unnamed slide with the SAME key). The project then
  appears in the list, unticked and marked NEW. (Typing `ID: key_named` in the speaker notes works too.)
* **Delete:** delete its slides in PowerPoint and save - the project disappears from the list. Your Excel row is
  removed on the next sync; the old deck stays in `base\_archive`.
* Your ticks / categories / versions survive these refreshes. The **Refresh** button forces a reload.

## Portable copy

Double-click `MAKE_PORTABLE.bat` -> `dist\EPC_Deck_Manager_Portable_<date>.zip` (~32 MB). It contains the tool, the
current base deck + registry and a private Python, so it runs on any Windows 10/11 64-bit PC with no installation.
Unzip anywhere and double-click `START_HERE.bat`. Rebuild the zip after the base deck changes.

## Generated decks

File properties are cleaned: title "Partnership Opportunities - <client>", no subject/comments, the base deck's
preview thumbnail (which showed another client's name) is removed and slide counts are reset.

## Review & discuss (first screen, top right: "Generate decks | Review & discuss")  -  INTERNAL, never part of a deck

The first screen has two modes. **Generate decks** is the deck builder (it now also has a **Lead** filter RB / JT / SS). **Review & discuss** is the Project Desk: lead buttons, review chips, comments, needs, actions, status file - all inside the same window, no separate window to open. The app remembers which mode you used last.

The place to sit with RB / JT / SS and go through the projects.

* **Filter** by lead (RB / JT / SS / Unassigned), country, category, what is needed (Investor, EPC, ...), stage, text, "only with open actions".
  The lead of a project comes from its country (the geography distribution - change it under *Geography & leads*), or you can set a lead on one project.
* **Per project**: stage, priority, an internal summary, **Needs** (investor / EPC / developer / lender / other, each with a status),
  **Comments** (who said it, discussion date, full text), **Actions** (owner, due date, tick off) and **History**.
* Project managers are shown as Vishnu & Vijayraj on every project.
* **Nothing to save**: every Add / change is stored the moment you do it. Deleting a need, comment or action only hides it - its text stays in the change log.
* **Change log**: every addition, change and deletion, with who and when - including everything done to the decks (project added / deleted / retired,
  category or country changed, key renamed, deck restored). Changes made directly in PowerPoint show up as "project appeared / no longer in the deck".
* **Print / PDF / Excel** from the header prints exactly what is on screen (so filter to JT + Cameroon, then print): a discussion sheet per project, or an Excel workbook of those projects.
  **Update registry Excel** writes the Desk sheets (summary, needs, comments, actions, change log, geography) into `projects_registry.xlsx`.
* **Daily use** - the chips under the lead buttons show, for the current lead / country, how many projects are **Overdue**, **Due in 7 days**, **Review due**,
  **Untouched for 14 days**, **Changed in 7 days**, **Never discussed** or have **No needs yet**. Click one to see just those.
  The lead buttons carry live counts (RB 17 / JT 19 ...). Your last lead / country / view is remembered.
* **Weekly review** - filter to one lead, press **Reviewed & next** (Ctrl+R = reviewed, Alt+Right / Alt+Left = next / previous) on each project as you go through it:
  it is logged and the next review is set 7 days ahead (editable per project). Then **Print / PDF / Excel... -> Weekly review** gives, per lead:
  what changed since a date (comments, needs, actions, stage changes), needs still open and actions still open. **Action list** prints all actions by owner, overdue first.
* Meetings: the comment's "by" follows the lead you filtered to; the discussion date defaults to today (and can be back-dated).
* Mistakes: deleted needs / comments / actions can be brought back from **History -> Restore deleted**.
* **Internal status from the team's Excel file (optional)** - header **Status file > Import status file...**, choose the workbook the team keeps updated
  (e.g. `BIP - Captive Projects.xlsx`). Only when you import is it read; nothing is needed otherwise. It finds the project tables by their headings
  (so added / moved columns are fine), skips hidden sheets, and reads the stakeholder blocks of the ADVANCE sheet (investor, local partner, EPC, consultants, bank / lender).
  Each Desk project is matched to the file by name + country (**confident**, or **possible** = marked "?" - check it). A project that is not in the file,
  not even partly, shows **No data on this project**. The **Status** tab shows stage, **next steps** (highlighted), **partners and banks** (banks in red,
  also banks mentioned in the text), agreements and remarks; the list gets an **In file** column and the chips **In file / Not in file**.
  If the match is wrong: **Link to another row...**, or **No data for this project** (remembered across uploads).
  Re-importing the updated file reports what changed (stage / next steps / new in file) in the import summary, in the project's History and in the Weekly review.
  The discussion sheet can include the status block (tick "Status from file"). The footer shows when a newer version of the file exists.
  Status data is internal and is never written into a deck.
* **Add / edit / delete projects from the same screen** - above the list: **+ Add project**, **Edit**, **Duplicate**, **Retire / Restore**, **Delete**, and **More**
  (rename key, move in the deck, Undo / restore an earlier deck, the full Manage projects window for bulk edits). They are the same operations as in Manage projects:
  the deck is backed up first, and your Desk notes (needs, comments, actions, history) follow a renamed project and are kept after a delete.
* **Change boss**: the **Boss** button (Review screen) / **Change boss** (Manage projects) moves a whole country to another boss (RB / JT / SS) - it updates the geography distribution, every project there follows - or sets a boss on selected projects only, or removes that special boss again. Geography & leads still shows the full country list.
* **Manage projects** now also has the boss filter (All / RB / JT / SS / Unassigned, with counts) and a Lead column; the Generate decks list has a Lead filter too.
* Safety: daily backup, `Desk_snapshot.xlsx` refreshed on every close, nothing is ever physically deleted.
* If two people use the same folder through OneDrive, do not use the Desk at the same time - one at a time, otherwise OneDrive can create a conflicted copy of `data\desk.db`.

## Manage projects (main window -> "Manage projects...")

One screen for everything, single or multi-select (Ctrl / Shift-click):

| Button | What it does |
|---|---|
| **Add new project** | Asks which slides: Named + Unnamed / Named only / Unnamed only / one slide for both. Then either a form (builds the slides in the standard layout; the unnamed slide is generated from the same text with country -> region and your "words to hide"), or duplicate an existing project, or tag slides you added in PowerPoint. **Only the title is required** - anything left empty is simply left off the slide (a card with nothing in it disappears; 1-3 snapshot boxes re-space themselves). Blocks saving if an unnamed slide still shows an identifying word or if text would overflow the layout. |
| **Edit attributes** | Category, default version, ticked-by-default, country, region, model (and names, one project at a time). Only fields you change are applied. |
| **Delete** | Whole project, or only its Named or only its Unnamed slides. |
| **Retire / Restore** | Hides a project from the main list and from every deck WITHOUT deleting its slides. Reversible ("Show retired"). |
| **Rename key** | Changes the project key and carries its Excel details over. |
| **Duplicate** | Copies a project's slides under a new key (edit the text in PowerPoint afterwards). |
| **Move Up / Down / Top / Bottom** | Reorders the slides in the base deck (= order inside each category). |
| **Undo / backups** | Every change saves the deck as it was before; restore any of the last 40 states. |

Retired projects: speaker notes line `STATUS: retired` (set by the button; you can also type it).

## Sorting, filtering and Sector

Both the main list and **Manage projects** have a **Find** bar (Sector, Country, Category, free-text search) and clickable headings:
click a heading to sort, click again to reverse, click a SECOND heading to sort within the first (e.g. Sector, then Country).
The headings show ▲/▼ and the sort order (▲1, ▲2). **Deck order** returns to the slide order. Ticks and choices are never lost
when you sort or filter. Empty / "TBD" values always sink to the bottom.

**Sector** is a column in the registry (Power, Oil & Gas, Water, Transport, Health, Education, Agriculture & Rural, Mining,
Telecom, Urban & Infrastructure, Mixed / Other). It is filled in automatically from the project name the first time a project is
seen; change it any time with Manage projects -> Edit attributes (works on several projects at once) or in Excel.

## Sources / origination (who brought each project)

Every project has a **Source / Origination**: the person, minister, partner or influential contact who brought it (several are
separated by `/`, e.g. `Walter / Yann`). Blank = nothing recorded. It is read from the pipeline workbook ("Partner Who Introduced",
"Name of Local Partner", sponsors) - your internal team (RMs) and counterparty ministries are not treated as sources.

* **Main list and Manage projects** show a **Source** column (sortable) and a **Source** filter in the Find bar, including `(no source)`.
* **Sources...** button opens the Sources window: every source with its type, country, role, project counts by category;
  select one or SEVERAL sources to see their projects, **Show in main list** to filter by them, **Edit details**, **Rename / merge**,
  **Add source**, **Export report (Excel)** (by source, project-by-source, and projects with no source).
* Change the source of projects: **Manage projects -> Edit attributes** (add / remove / replace, works on many projects) or the
  Sources window -> *Edit source(s) of selected projects*.
* In Excel: columns **Sr. No.** (automatic serial in deck order), **Source / Origination**, **Source Notes** in the registry sheet,
  plus the **Sources** sheet (roles and types; counts refresh automatically).
* **Sources never appear in generated decks** (checked: no source name occurs anywhere in a generated file).

## Printing (landscape) - main screen, Manage projects and Sources

Each of the three screens has a **Print / PDF...** button. It prints the list exactly as shown (current sort and filters), either all
rows or only the ticked / selected ones. Choose columns, paper (A4 / A3 / Letter / Legal), **Landscape (default)** or portrait, text
size and an optional **group by** (Sector, Country, Category, Source). The top of the page states the filters and sort order.

* **Print...** opens the list in your browser with the print window already open (layout is already landscape).
* **Save as PDF** creates a real PDF (needs Edge or Chrome, both normally installed) and opens it.
* **Save as Excel (landscape)** creates a worksheet set to landscape, fit to one page wide, header row repeated on every page.

Header row repeats on every page, rows never split across pages, page numbers in the footer. Files are saved in `output\Prints\`.

## Blend Hub (new)
`START_HERE.bat` opens Blend Hub (the one app: decks, dashboard, discussion, counterparties) in its own window: pipeline dashboard (shortlisted EPCs / banks / ECAs / investors / insurers per transaction),
transaction detail (internal status Tie-up done / P1 / P2 / Preliminary / On hold, client type Government / SOE / Private, tender or negotiated,
information checklist), counterparty view (one EPC / bank / ECA -> all its transactions), import of the BIP workbook, activity log.
Data lives in `data/hub.db` (OneDrive: one editor at a time, automatic backups in `data/backups`). The deck generator (`START_HERE.bat`) is unchanged.
