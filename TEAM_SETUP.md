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

### A3. Start the Hub in team mode
Double-click **`START_TEAM.bat`**.

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
Open a **second** window and double-click **`START_TUNNEL.bat`**.
After a few seconds it prints a web address like:

```
https://brave-tiger-1234.trycloudflare.com
```

**That is the link your team uses.** Test it yourself first: open it in a browser, sign in with your
master login. You should see the Hub.

Keep **both** windows (Hub + tunnel) open.

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

That's it — you're live.

---

## Part B — Everyday use

**To bring the Hub online:**
1. Double-click **`START_TEAM.bat`** (wait for "running").
2. Double-click **`START_TUNNEL.bat`** (wait for the `https://…` link).
3. Share the link if it changed (see note below).

**To take it offline:** close both black windows.

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
