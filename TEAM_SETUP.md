# Blend Hub — Team Setup & Sharing Guide

*Make the Hub work for your whole team (≈10 people), live, from Windows **and** iPhone/iPad, from anywhere.*

---

## The idea in one picture

```
   YOUR PC (stays on)                    EVERYONE ELSE
   ┌───────────────────┐                 (nothing to install)
   │  Blend Hub running │  ── internet ──►  Edge / Chrome / Safari
   │  (START_TEAM.bat)  │                   on Windows, iPhone, iPad
   │  + internet link   │                   → they just open ONE link
   │  (START_TUNNEL.bat)│                      and sign in
   └───────────────────┘
```

- **Only your one PC runs the program.** It holds all the data in one place.
- **Nobody else installs anything.** They open a web link and sign in. Works on iPhone/iPad too.
- **Everyone edits at the same time**, live. Changes show up on everyone's screen within a few seconds.
- **Three access levels:** *Master* (you — full control), *Editor* (can change deals), *Viewer* (read only).

> **Python note:** Only the host PC needs Python — and even that is optional if you use the
> **portable bundle** (`MAKE_PORTABLE.bat`), which has Python built in. **Your team needs nothing but a browser.**

---

## Part A — One-time setup (do this once, ~15 minutes)

### A1. Pick the host PC
Choose the Windows PC that will stay **on and awake** during work hours. This is usually your office desktop.
(A laptop works too, but if it sleeps or goes home, the Hub goes offline for everyone — see **A5**.)

### A2. Put the Blend Hub folder on that PC
Either:
- Use the folder you already have, **or**
- Build a portable copy: double-click **`MAKE_PORTABLE.bat`**, then unzip the file it creates
  (`dist\DealDeck_Studio_Portable_<date>.zip`) somewhere like `C:\BlendHub`.
  The portable copy has Python inside it, so nothing needs installing.

### A3. Start everything (one double-click)
Double-click **`BLEND_HUB.bat`**. It opens the Hub **and** the internet link together,
then shows the web address to share (also saved to `LINK.txt`) and opens it for you.

*(If you ever want to run the pieces separately: `START_TEAM.bat` is just the Hub, and
`START_TUNNEL.bat` is just the internet link. `BLEND_HUB.bat` runs both.)*

A black window opens. **The very first time**, it prints your master login, like:

```
  FIRST-TIME SETUP - your master login was just created:
     username:  admin
     password:  Xy7k2mQp9
```

**Write this down.** Keep the black window open.

> Want a specific admin username/password instead of the random one? Before the first run,
> you can set them — but the simplest path is: use the printed one, sign in, then change your
> password (top-right → **Password**).

### A4. Get the internet link
`BLEND_HUB.bat` already did this — the address (like `https://brave-tiger-1234.trycloudflare.com`)
is shown in the window and saved in **`LINK.txt`**. **That is the link your team uses.**
Test it yourself: open it, sign in with your master login, you should see the Hub.

Keep the helper windows open (you can minimise them).

### A5. Stop the PC from sleeping
So the Hub doesn't disappear when you step away:
- Windows **Settings → System → Power** → set **Screen off** and **Sleep** to **Never** (at least while plugged in).
- Optional: keep the two windows minimised, not closed.

### A6. Add your team (the Users page)
Signed in as master, click **Users** (top-right). For each of the ~10 people:
1. Enter a **username** (e.g. `rahul`), their **name**, pick an **access level**, type a **first password**.
2. Click **Add person**.
3. Send them their username + first password (see the team guide, `FOR_THE_TEAM.md`).

**Access levels:**

| Level | Can do |
|---|---|
| **Master** | Everything: edit, generate decks, **manage users**, delete, swap the base deck, reassign leads/countries. Keep this to 1–2 trusted people. |
| **Editor** | Add & change deals, comments, needs, actions; generate decks; print/export. Cannot manage users or do destructive/structural actions. |
| **Viewer** | Read everything, print & export. Cannot change anything. |

### A7. Choose exactly what each role can see & do (optional, fully customizable)
On the **Users & permissions** page there's a **"What each role can do & see"** grid.
Tick precisely what **Viewers** and **Editors** are allowed to do (edit deals, comment, generate
decks, delete, import, etc.) and see (deal **values**, **comments**, the **change log**). Masters
always have everything. Click **Save**; it applies to everyone within a few seconds. Sensible
defaults are set already, and **Reset to recommended defaults** is one click away.

That's it — you're live.

> **Heads-up about new deals:** a brand-new deal starts as **"Preliminary"**, and the default
> view hides Preliminary deals. If you add one and "can't see it", tick **Show Preliminary** in
> the filters (or set its status). Editing existing deals always shows up live.

---

## Part B — Everyday use

**To bring the Hub online:** double-click **`BLEND_HUB.bat`**. Done.
(Want it to start by itself after a reboot? Run **`INSTALL_AUTOSTART.bat`** once.)

**To take it offline:** close the two black helper windows.

> **About the link changing:** with the free "quick tunnel", the `https://…trycloudflare.com` address
> can change **each time you restart `START_TUNNEL.bat`**. While that window stays open, the link is stable.
> If you restart it and get a new link, resend it. To get a link that **never changes**, see **Part D**.

---

## Part C — Keeping it safe

- **Change the admin password** on first sign-in (top-right → **Password**).
- The internet link is **HTTPS** (encrypted) end-to-end to Cloudflare. Still, treat the link as confidential —
  anyone with the link *and a login* can reach the Hub. No login = no access.
- **Backups are automatic:** the Hub keeps database backups in `data\backups\` and an Excel snapshot.
  To force one, use the Hub's **Backup** button. Copy the `data\` folder somewhere safe weekly.
- **Keep at least two Masters** so you're never locked out (the Hub won't let you remove the last master).
- Removing someone: **Users → Disable** (keeps their history) or **Delete**.

---

## Part D — (Optional) Make the link permanent

The quick tunnel is perfect to launch now. When you have 20 spare minutes, upgrade to a **named tunnel**
so the address (e.g. `https://hub.yourdomain.com`) **never changes**, even after a reboot:

1. Create a **free Cloudflare account** and add a domain you control to it
   (any cheap domain works; Cloudflare's DNS is free).
2. On the host PC: `cloudflared login` (authorises the PC with your Cloudflare account).
3. `cloudflared tunnel create blendhub`
4. Map a hostname to it: `cloudflared tunnel route dns blendhub hub.yourdomain.com`
5. Run it: `cloudflared tunnel run --url http://localhost:8765 blendhub`
   (You can later install this as a Windows service so it starts on boot.)

Full current steps: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/>

If you don't have a domain yet, **stay on the quick tunnel** — it works fine; you just re-share the link
if you restart the tunnel window.

---

## Part E — Troubleshooting

| Problem | Fix |
|---|---|
| Team sees "This site can't be reached" | Make sure **both** windows (Hub + tunnel) are open on the host PC, and the PC is awake. |
| The link changed | It does if you restarted the tunnel. Resend it, or set up the permanent link (Part D). |
| "Python was not found" on the host | Install Python 3 from python.org (tick *Add to PATH*), **or** use the portable bundle (Python included). |
| Someone forgot their password | You (master) → **Users → Reset password**, send them the new one. |
| Someone should no longer have access | **Users → Disable** (or Delete). |
| Two people editing the same deal | Fine — it's built for that. Each save is recorded with who made it; the screen refreshes every few seconds. |
| Need to free the port / restart cleanly | Close both windows, wait 5 seconds, run `START_TEAM.bat` again. |

---

*Questions or something not working? Note exactly what the black windows say and what the browser shows.*
