# Fleet UI checks for version 88

These scenes run the real Godot client and its normal UI containers with a local
fixture. `OfflineClient` intercepts mission/quote requests, disables polling and
session persistence, and leaves the server address empty so independent login
configuration modules do not make requests.

Run from the project directory with Godot 4.5.1 after importing project assets:

```sh
godot --headless --path . res://tests/fleet_destination88_test.tscn
godot --headless --path . res://tests/android_fleet87_regression.tscn
```

If the normal user-data directory is not writable, set `XDG_DATA_HOME` to a
writable test directory and use `--log-file` with a writable absolute path.

## Destination layout and navigation

`fleet_destination88_test.gd` covers English and Polish at 720×1280, 720×1600,
and 450×800 window sizes. The smaller window uses the game's 720×1280 logical
canvas. Its 282 checks cover:

- Map height using the available screen space, with navigation, zoom buttons,
  the system chooser, Back, and active missions remaining available.
- The shared Galaxy focus zoom, zoom after changing galaxy, and reopening a
  destination. The map correction uses the Galaxy tab's 2.4 focus zoom.
- System → galaxy → fleet form for the visible Back button, Android Back, and
  Escape with keyboard focus on the Back control.
- Pan, zoom, ship quantities, cargo, and origin surviving navigation.
- Android Back and Escape closing a choice list without also closing the map.
- Choosing a new or unchanged destination closing the picker directly.
- Repeated opens retaining one resize callback, and unrelated details keeping
  their ordinary single-step Back behavior.

Android notifications are propagated through the full test tree. Escape is
injected through the viewport, so focused controls and normal input routing are
included. This is desktop runtime coverage of the Android callback, not a
physical-device test.

The test writes `fleet_destination88_report.json`, including measured map,
viewport, and selector rectangles. A failing check produces a nonzero exit code.

## Rendered screenshots

With a rendering display available, such as a local desktop or Xvfb, add the
optional capture flag and omit `--headless`:

```sh
godot --path . res://tests/fleet_destination88_test.tscn -- --capture
```

This runs the same assertions and writes nine PNGs into
`tests/fleet_destination88_screenshots`: the Polish galaxy view, selected system,
and return to the galaxy at each window size. The return screenshot preserves
the pan and zoom deliberately applied by the test. Successful screenshot saves
add nine checks, for 291 total.

## Existing mission regression

`android_fleet87_regression.gd` preserves the previous 139-check mission suite,
with its report moved into this test directory and independent login requests
disabled. It checks automatic route quotes, stale responses, debounce, ship and
cargo composition, affordability, dispatch gating, and the existing mission UI.
Its output is `android_fleet87_regression_report.json`.

## Comparing the actual Galaxy tab with the corrected destination map

```sh
godot --headless --path . res://tests/galaxy_zoom88_comparison.tscn
godot --path . res://tests/galaxy_zoom88_comparison.tscn -- --capture
```

The original mission test fixture replaces the galaxy with two systems and omits
the ring fields. It is useful for isolated mission behavior, but its screenshots
do not represent a populated galaxy. The renderer places those two systems at
opposite ends of its legacy ellipse. Focusing one system hides the other at both
the original 3.2 zoom and the corrected 2.4 zoom. A single visible star in that
fixture therefore cannot establish that the application filters out neighbors.

`galaxy_zoom88_comparison.gd` uses all 60 server-authored systems from the existing
ring fixture: 30 on the outer ring, 20 on the middle ring, and 10 on the inner
ring, preserving every `ring_*` field and connection. The test enters Galaxy
through the actual bottom navigation button, then starts a new mission. It
checks the number of visible stars, home centering, home-to-neighbor distances
in pixels, and positions of shared visible neighbors at 720×1280 and 720×1600.
Both views must show several systems; comparing only the numeric zoom would not
detect projection or layout differences.

The suite also opens the destination picker in a fresh client before visiting
Galaxy, and compares it with the normal view at the same window size. This
prevents a dependency on previously displaying the normal map. A separate
assertion checks that the normal Galaxy page uses the available height while
keeping its controls in view.

For this comparison the in-memory first-visit preference is set to already seen,
matching an existing player's normal map entry. No account preferences are saved
and no network requests are sent. Diagnostic steps recreate the previous 3.2
zoom and the two-system fixture on the runtime map object only.

The report is `galaxy_zoom88_comparison_report.json`. With `--capture`, four PNGs
are written to `tests/galaxy_zoom88_screenshots`: the normal Galaxy tab and the
destination picker at each size. There are 51 headless checks, or 55 checks with
the four screenshot saves. Historical version88 reports describe the
earlier 3.2 implementation and are retained; corrected validation belongs in
`docs/version88_mapfix`.

`galaxy_layout88_diagnostic.gd` is a separate measurement scene for layout timing.
It records container sizes and minimum sizes before and after one explicit call
to the existing `_fit_map`, after 16 and 80 frames. It does not change application
code. The acceptance comparison above does not call `_fit_map` manually. The
pre-fix diagnostic established that the automatic map size stayed at 482/322 px,
although the settled layout had 667/987 px available at the two window sizes.
One later fit produced those correct heights and stayed stable. The initial
comparison and diagnostic are preserved under `docs/version88_mapfix`.

```sh
godot --headless --path . res://tests/galaxy_layout88_diagnostic.tscn
```
