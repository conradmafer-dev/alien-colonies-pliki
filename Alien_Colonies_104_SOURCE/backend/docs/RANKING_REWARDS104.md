# Ranking rewards — Alien Colonies 104 / 0.12.37

The overall empire ranking now grants rare Swarm Crystals for the actual time
spent in a rewarded position. Category tabs do not grant additional rewards.

| Overall place | Time for one crystal |
| --- | --- |
| 1 | 3 real days |
| 2–3 | 5 real days |
| 4–10 | 7 real days |
| 11–30 | 14 real days |

Fractional progress is preserved when changing positions. Outside the top 30,
accrual pauses without clearing the fraction. It resumes at the new bracket's
rate upon reentry. Whole crystals are credited automatically, with a localized
ranking report. No collection button or continuous app connection is needed.

The policy starts on first deployment and gives no retroactive reward for
pre-release rankings. A new account starts at zero. Existing worlds, accounts,
colonies and reset markers are preserved. Later restarts replay offline asset
completion and combat events in order, settling the old ranking before each
event and the new ranking for the following interval. Currency, progress,
settlement time and reports share the existing atomic world transaction.

The native and browser rankings show two compact lines: the existing Swarm
Crystal icon, overall position and rate, followed by a progress bar, percentage
and remaining time. A help control explains all four brackets, offline accrual
and pausing. English, Polish, German, Spanish and French are included.

Checks: exact bracket boundaries and millisecond thresholds, mixed rates,
pausing/reentry, offline SQLite reopening, no retroactive credit, new accounts,
event-time score changes, read-only views and rollback/retry. The native UI is
measured at 320×568, 390×844 and 900×600 in all five languages. Android bundle
verification checks the actual bytecode, language files and sparse asset index.

Physical Android installation and Google Play publication remain author steps.
