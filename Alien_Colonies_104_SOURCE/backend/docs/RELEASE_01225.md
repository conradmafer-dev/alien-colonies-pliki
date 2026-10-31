# Alien Colonies 0.12.25 — player ranking / Android92

Authenticated `GET /api/ranking` serves the same read-only empire valuations to
Android and the browser. No score ledger, world migration or account reset is
introduced. The existing Android minimum-version policy is preserved.

One point is 1,000 metal, ordinary crystal and fuel combined at the current
catalogue construction prices, before speed or cost bonuses. All completed
building/research levels count cumulatively; research counts once per empire.
Surviving ships count in colonies and every mission/support/return state exactly
once. Defense counts only on currently owned planets. Foreign buildings retain
their catalogue value when a colony changes hands. Completed Dyson stages and
the gate remain the builder's assets, matching existing megastructure ownership.
Queues, stockpiles, cargo, rare Swarm crystals, skill balances and the Khar NPC
are excluded. Total values are summed before rounding down; category columns
round their own totals, so displayed category integers may differ from the
overall integer by up to three points. Equal scores sort by player name, then ID.

The endpoint supports `category=total|buildings|research|fleet|defense`, positive
`page`, and `around_me=1`, with fixed 50-row pages. Every page includes the
caller's position and aggregate category scores. Names/race and aggregate scores
are the only public player information; no coordinates or private empire state
are exposed. Requests use the existing authentication and per-player rate limits.

Android92 adds a 64×64 trophy button beside Settings. The existing responsive
header relocates the skill wallet when necessary and truncates colony names.
The separate ranking screen has a pinned own-position card, category picker,
paging, refresh/retry, own-row highlighting and My position. Back restores the
previous game screen. Logout clears the cached ranking; stale responses from a
previous token/server cannot repaint it. All five existing locales are included.
The browser exposes the same view through its header trophy and Settings.

Validation uses isolated SQLite worlds, real authenticated local HTTP, the actual
native main scene, all five languages and 360×640, 450×800 and 720×1600 displays.
Native screenshots use synthetic empires only. Physical Android interaction and
live Firebase notification delivery are not part of these checks.

The AAB is unsigned for the owner's existing upload key. The Windows helper
checks package, code92, version0.12.25 and the existing upload certificate.
