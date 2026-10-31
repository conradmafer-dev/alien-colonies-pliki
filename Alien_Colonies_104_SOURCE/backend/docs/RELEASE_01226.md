# Alien Colonies 0.12.26 / Android 93

Authenticated `POST /api/account/rename` accepts `name` and an optional selected
`planet_id`. It applies the existing 3–20 character name rules and case-insensitive
uniqueness, updates the login key and public empire name atomically, and retains
the player ID, sessions, authentication links, colonies, fleets and progression.
Password sign-in uses the new name after a rename. Android options and browser
settings expose the same action. Rank rows show localized faction names in blue,
red or green beside the empire name.

Android 93 checks for texture updates before login. The public, read-only manifest
is `/play/content/manifest.json`; immutable data packs are addressed by SHA-256.
Only texture resources and their imported texture data are accepted. Downloads
are bounded, verified and committed together. Unchanged packs are reused. A failed
download keeps the last verified release and offers retry or the bundled version.
Use `tools/make_asset_update.py` in the complete Android source after importing
changed textures, and deploy its output with this backend. No executable code is
downloaded by this mechanism.

Native app updates use the official Play in-app update API 2.1.0 through the
AlienUpdates Android plugin, with consent, progress, cancellation, retry and
install/restart. This requires a Google Play installation and an eligible newer
release. The first Android 93 build still needs normal Play publication. Existing
minimum/latest Android version policy is deliberately preserved until publication.

My position waits for completed layout and centers the row identified by the
player ID, independent of page, variable row height or the previous scroll offset.
Server snapshots wait for touch, wheel and inertial scrolling to settle. Unchanged
catalogue cards and unchanged price/action state keep their existing layout.
State responses are decoded once. Local refresh profiling improved from about
65 ms to about 13 ms; this is a desktop engine measurement, not an Android FPS claim.

Validation: 561 native layout/input checks (5 languages, 3 window sizes, including
rank 13), 139 fleet regressions, 19 asset-update checks with actual local HTTP,
5 rename transaction/authentication tests, 14 server ranking tests and browser
ranking markup/escaping tests. Physical Android and real Play update delivery
must be checked on a device after publication.
