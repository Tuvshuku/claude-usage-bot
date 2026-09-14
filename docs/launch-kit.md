# Claude Usage Bot — launch kit

## The pitch

**Your usage, with a little personality.**

A tiny desktop pet that keeps your Claude Code usage in view. It wanders,
it naps, and it opens your dashboard with a click. Free and open source for
Windows, with a WSL collector option.

The first audience is people already using Claude Code on Windows or WSL.
Lead with the moving pet, then show the practical dashboard.

## Ready-to-share material

- [Share card](images/launch-card.png): 1280 × 640, matching the landing page.
- [Short preview video](images/launch-demo.mp4): approximately 15 seconds, MP4.
- [WebM version](images/launch-demo.webm).
- [Desktop page preview](images/landing-desktop.png).
- [Mobile page preview](images/landing-mobile.png).
- [Desktop app screenshots](images/bot-dashboard.png) and the existing
  [desktop demonstration](images/demo.gif).

The new card and video show the **interactive browser preview**, not a recording
of the native Windows app. Example data is labeled on-screen. Use the desktop
screenshots or capture the native app when specifically demonstrating native
installation or real account sync. The mood buttons belong to the browser demo;
the installed pet changes mood automatically.

## Short social post

> Your Claude Code usage monitor now has a personality.
>
> I made a tiny desktop pet that wanders around, naps when things go quiet, and
> opens a usage dashboard when clicked.
>
> Free + open source. Windows app, WSL supported.
>
> The clip is an interactive preview with example data.
>
> https://github.com/Tuvshuku/claude-usage-bot

Attach `launch-demo.mp4`. Use the original desktop GIF instead if you want to
show the native app, and adjust the preview sentence accordingly.

## Community showcase

Title: **I made a little desktop pet that shows your Claude Code usage**

> I wanted my usage monitor to feel a little more at home on my desktop, so I
> made Claude Usage Bot: a small pixel pet built for Claude Code users.
>
> Click it to see session and weekly usage. Its colour follows usage, it sleeps
> after inactivity, and you can turn wandering off. It supports native Windows
> and Claude Code running inside WSL.
>
> Live sync reads your account usage using Claude Code's existing login. You
> can disable it and use local estimates. The code is MIT-licensed.
>
> One limitation: the desktop UI is Windows-only. The executable is currently
> unsigned. Local cost figures are estimates, not your subscription bill.
>
> Project and download: https://github.com/Tuvshuku/claude-usage-bot
>
> I'd especially appreciate feedback on installation and dashboard readability.

Review each community's current showcase rules before posting. Adapt this to
your own story and only describe how it was built if that description is true.

## Show HN

Title: **Show HN: A Windows desktop pet that displays Claude Code usage**

URL: `https://github.com/Tuvshuku/claude-usage-bot`

First comment draft:

> I made this for people who use Claude Code on Windows or WSL and want their
> usage visible without keeping a dashboard open. The UI is a small WPF pet;
> a Python collector reads transcripts and optionally syncs account usage.
>
> A recent round of fixes reconciles cumulative streaming records, handles
> reset boundaries and partial account responses, and prevents duplicate
> collectors from writing the same state. Local estimates are marked with ~;
> saved account readings are marked with *.
>
> The Windows executable bundles Python. Source and a WSL setup are available.
> This is independent of Anthropic. Happy to discuss the accounting, WPF
> animation, or installation tradeoffs.

Post when a release containing the fixes is available and you can answer
questions. Don't solicit upvotes or mass-post identical messages.

## Release description draft

**A little desktop company, with more reliable usage tracking.**

- Updated streaming token counts are reconciled instead of discarded.
- Historical transcript copies no longer inflate retained totals or enter the
  current session.
- Saved account readings expire at reset boundaries and survive partial responses.
- Windows and WSL launchers honor configured paths; WSL Startup works from its
  installed location. Collector writers share a lock.
- Local estimates remain visibly approximate after calibration.
- A new interactive landing page lets you meet the pet using example data.

Attach `ClaudeUsageBot.exe` and `SHA256SUMS.txt` from `dist/`. Choose the next
version after checking the latest published release; no version is assumed here.

Upgrading: restart the collector. WSL users should stop the old collector and
rerun `./install.sh --service --autostart`, then reopen the widget. Schema 5
rebuilds local totals on first launch. See [upgrade details](collector-fixes.md).

## First-user checklist

Ask 3–5 people to try the downloadable build before a broad launch:

1. Can they choose native Windows versus WSL without explanation?
2. Does the pet appear, and do clicks, dragging, idle mode, and Quit work?
3. With live sync working, do usage percentages match their account reading?
4. Can they understand an offline or estimated reading?
5. After signing out and back in, does their selected startup setup work?

Keep a small log: OS/setup, step attempted, what happened, and whether it was
fixed. Ask for a voluntary one-week follow-up. Do not add tracking or collect
account credentials. A useful first milestone is 20 people still using it a
week later; downloads alone do not tell you that.

## Preview, build, and publish

The landing page is static HTML/CSS/JS with no build step, analytics, remote
fonts, or third-party scripts. From the repository root:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Open `http://localhost:8765`. You can also open `docs/index.html` directly;
the Copy button falls back to selecting text if clipboard access is unavailable.

For optional browser verification, install Playwright in a development tools
directory and run `scripts/check-site.mjs`. `PLAYWRIGHT_MODULE` can point to its
`index.mjs`; `CHROMIUM_EXECUTABLE` can select an installed browser. Pass
`--capture` to regenerate the PNGs and WebM. Convert the WebM to H.264 MP4 for
social uploads, for example:

```bash
ffmpeg -i docs/images/launch-demo.webm -an -c:v libx264 -pix_fmt yuv420p \
  -movflags +faststart docs/images/launch-demo.mp4
```

On Windows, `powershell -ExecutionPolicy Bypass -File scripts/build-windows.ps1`
creates an isolated temporary build environment, runs tests, and writes the
executable and checksum into `dist/`.

When ready to publish the website, GitHub Pages can serve the `/docs` directory
on `main`. The social-image URL assumes
`https://tuvshuku.github.io/claude-usage-bot/`; update it if using another host.
Set the repository's social preview to `docs/images/launch-card.png`. Suggested
topics: `claude-code`, `desktop-pet`, `usage-monitor`, `windows`, `wsl`, `python`,
`powershell`, `open-source`.

Publishing the website or release, changing repository settings, and submitting
posts are separate public actions. This kit prepares the material locally.
