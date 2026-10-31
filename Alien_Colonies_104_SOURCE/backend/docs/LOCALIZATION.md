# Localization — Alien Colonies 0.5.1

Supported languages: en, pl, de, es, fr. English is the explicit first-run default; device language does not override it. The choice is stored separately from account/session data in user://language.cfg. Use the chooser on the login screen or in Settings.

## Authored strings

The runtime catalogs are localization/{en,pl,de,es,fr}.json. Keys are the exact Polish authored source strings, including whitespace and formatting placeholders. Separate *_source.json and *_en.json files provide the maintained inventory/English authoring sources. The five runtime catalogs must have every inventory key. Extra entries for late corrections are in extra_translations.json.

Client: call I18n.t("source") BEFORE % interpolation, .format or concatenation. Never translate IDs, URLs, user-entered names, passwords, recovery codes or numeric input. Translate source constants at their read sites, not at parse time. New mobile pickers should use _choice and receive already localized authored captions; user-authored option names remain literal.

Server: call t("source").format(...) with immutable placeholders before interpolating user values. Use join_text for text assembled into persistent reports. Do not pretranslate catalog constants at module import. Accept-Language is scoped per HTTP request through ContextVar; direct simulation calls keep the legacy Polish default. The shared server catalog loader falls back to English for missing locale values.

## Adding content

1. Add a source key and its English translation to the relevant inventory pair (main, widgets, server, or a new pair).
2. Add the key to all five runtime JSON files. Use concise, natural interface copy and preserve numbers and gameplay meaning.
3. Keep Godot %s/%d/%.1f placeholders in the same order and preserve %% literals. Python {0}/{1} placeholders may move while retaining their indices and format specs.
4. Run `python tools/check_localization.py`. It checks coverage, placeholders, whitespace and raw unlocalized Polish client strings.
5. Run server tests and the offline localized mobile UI tests. Inspect long-language layouts; never shrink resource amounts into vertical digits.
6. Copy the five runtime catalogs into railway/localization alongside i18n.py. Android/Windows export presets explicitly include all five JSON files.

## Reports and safe language changes

New reports store neutral template metadata with literal formatting arguments. The same report renders in the reader's selected language. Saved legacy bodies lack structured arguments and remain untouched to avoid rewriting player names; their fixed titles translate. This update does not reset the world.

Changing language rebuilds authored UI and fetches a fresh localized state. It waits while a gameplay request, unresolved idempotent order or APK transfer is active. Selections and login fields are passed directly to the replacement scene; passwords are not written to preferences. Mission quotes are invalidated after restoring the view, so a stale quote cannot submit a different fleet.

Account deletion UI requires the exact token DELETE ACCOUNT in every language. The server also accepts the legacy Polish token for older clients.

## Offline tests

The deferred bootstrap loads test suites after autoload registration. Example:

```
python tests/make_localization_fixture.py /tmp/alien-locales.json
godot --headless --path . --script tests/run_localized_test.gd -- tests/test_localized_game.gd /tmp/alien-locales.json
godot --headless --path . --script tests/run_localized_test.gd -- tests/test_localized_widgets.gd
python -m unittest discover -s tests -p 'test_*.py'
```

Do not load production sessions while testing. Preferences/restart tests use an isolated XDG_DATA_HOME. Phone testing and native-language editorial review remain separate release checks; headless layout checks do not substitute for installing the APK.
