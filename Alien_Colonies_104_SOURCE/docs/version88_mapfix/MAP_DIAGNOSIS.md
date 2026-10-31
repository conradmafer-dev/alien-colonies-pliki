# Version 88 galaxy map correction: diagnosis and headless verification

The corrected destination picker uses the same focus zoom and actual pixel
scale as the normal Galaxy page. Its larger map reveals additional neighbors
above and below the same centered home system.

## Three findings

The original mission UI fixture contains only two systems, without ring
topology. The renderer places them at opposite ends of a legacy ellipse. Once
the home system is centered, the other system is outside the viewport at both
3.2 and 2.4 zoom. That screenshot therefore does not demonstrate an own-system
filter. The full client passes all systems in the selected galaxy to both maps.

There was also a real zoom difference: the destination picker used 3.2 while the
normal home focus used 2.4. The application now uses the shared
`GalaxyMap.DEFAULT_FOCUS_ZOOM` value of 2.4 in both entry points.

The full 60-system comparison then exposed a second real layout issue. The
normal page calculated its map height before its labels and legend settled, and
did not fit the map again when their minimum sizes changed. Because the galaxy
projection depends on both width and height, equal numeric zoom still produced
different pixel spacing. The application now queues the existing fit operation
after the page's minimum size changes as well as after a tab resize. The height
formula and projection formula themselves are unchanged.

## Layout evidence

| Window | Tab height | Other content counted by fit | Stale map height | Height after one late fit | Stable after 80 frames |
|---|---:|---:|---:|---:|---|
| 720×1280 | 958 px | 291 px | 482 px | 667 px | Yes |
| 720×1600 | 1278 px | 291 px | 322 px | 987 px | Yes |

`galaxy_layout_diagnostic_before_fix.json` contains all container sizes and
minimum sizes before and after that manual diagnostic fit. The acceptance test
does not call the fit manually. After the application fix, it obtains the
correct height through normal navigation alone.

The visible zoom-control row ends 12 px before the page's bottom at both sizes.
The assertion measures the actual controls, because the ScrollContainer's body
can retain an older bounding height while its visible children have completed
layout. This avoids confusing that internal rectangle with blank space in the
rendered UI.

## Verified result

| Window | Normal map | Destination map | Visible systems: normal / picker | Shared visible systems | Maximum relative-position difference |
|---|---|---|---:|---:|---:|
| 720×1280 | 676×667 px | 676×838 px | 10 / 13 | 10 | 0.000031 px |
| 720×1600 | 676×987 px | 676×1158 px | 15 / 17 | 15 | 0.000062 px |

Both views have zoom 2.4 and an ellipse radius of 284×170.4 px. Home-to-neighbor
spacing differs by less than 0.000008 px. Both home systems remain centered.
The same comparisons pass when a fresh client opens the destination picker
before visiting Galaxy.

`galaxy_zoom88_comparison.gd` passed **51/51 checks**. It uses a complete
server-authored topology with 30 outer, 20 middle, and 10 inner systems. Its
fixture preserves ring properties and connections. The optional renderer mode
adds four screenshot-save checks.

`fleet_destination88_test.gd` passed **282/282 checks** on the corrected code:
Polish and English, 720×1280, 720×1600, and 450×800. It covers map height,
hierarchical Back, Android Back notifications, injected Escape with focused
controls, open choice lists, pan/zoom preservation, repeated opens, and choosing
either a new or the same planet.

The subsequent rendered capture passed **55/55 checks**, including four saved
PNGs, and its complete raw report is `galaxy_zoom_comparison_rendered.json`.

These are offline desktop Godot checks of the real client tree. No backend or production account is
used. Historical reports in `docs/version88` still describe their original
3.2 implementation and have not been replaced.

Exact reproduction commands and tested source hashes are in
`mapfix_headless_validation.json`. The headless comparison result and pixel
measurements are preserved in `galaxy_zoom_headless.log`, with its parsed summary
in `galaxy_zoom_comparison_headless.json`. The rendered run replaced the scene's
shared JSON output, so that complete report is kept under the rendered filename
instead of being mislabeled as headless. The navigation's complete raw report is
`fleet_destination_mapfix_headless.json`.
