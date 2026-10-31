#!/usr/bin/env python3
"""Validate release localization catalogs and authored Godot UI coverage.

Run from any directory: python tools/check_localization.py
Checks placeholder integrity, source coverage and accidental untranslated literals.
Gameplay protocol keys, constants translated at their use sites and player names
are deliberately outside the raw-literal check.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import string

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "pl", "de", "es", "fr")
PRINTF = re.compile(r"%(?:\d+)?(?:\.\d+)?[sdif%]")
STRINGS = re.compile(r'"(?:[^"\\]|\\.)*"')
MASK_STRINGS = re.compile(r'''"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*' '''.rstrip())


def read_object(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
        raise ValueError(f"{path}: expected a string-to-string object")
    return data


def brace_fields(text: str) -> Counter:
    return Counter((name, spec, conversion) for _, name, spec, conversion in string.Formatter().parse(text) if name is not None)


def edge_space(text: str) -> tuple[str, str]:
    return (text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):])


def raw_ui_literals(root: Path, keys: set[str]) -> list[str]:
    errors = []
    for path in sorted((root / "client/scripts").glob("*.gd")):
        if path.name == "i18n.gd":
            continue
        in_const, balance = False, 0
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("const "):
                in_const = True
            masked = MASK_STRINGS.sub("", line).split("#", 1)[0]
            if in_const:
                balance += sum(masked.count(c) for c in "([{") - sum(masked.count(c) for c in ")]}")
                if balance <= 0:
                    in_const = False
                continue
            # Export defaults must be constant; mobile_choice translates the
            # dialog_title property at both its creation and refresh sites.
            if path.name == "mobile_choice.gd" and line.lstrip().startswith("@export var dialog_title:"):
                continue
            for match in STRINGS.finditer(line):
                before = line[:match.start()]
                if "#" in MASK_STRINGS.sub("", before):
                    break
                literal = json.loads(match.group())
                if path.name == "release_panel.gd" and literal == "USUŃ KONTO" and before.strip() == 'payload["confirmation"] =':
                    continue  # Backward-compatible, immutable server protocol token.
                authored = literal in keys or bool(re.search("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", literal))
                if authored and not re.search(r"I18n\.t\(\s*$", before):
                    errors.append(f"{path.relative_to(root)}:{lineno}: untranslated authored literal {literal!r}")
    return errors


def validate(root: Path, locales: tuple[str, ...]) -> tuple[list[str], int]:
    directory = root / "localization"
    sources, client_keys = {}, set()
    for path in sorted(directory.glob("*_source.json")):
        data = read_object(path)
        sources.update(data)
        if path.name in ("main_source.json", "widgets_source.json"):
            client_keys.update(data)
    if not sources:
        return ["No source inventories found."], 0
    errors = []
    for locale in locales:
        path = directory / f"{locale}.json"
        if not path.exists():
            errors.append(f"Missing catalog: {path.name}")
            continue
        translations = read_object(path)
        missing = sources.keys() - translations.keys()
        if missing:
            errors.append(f"{locale}: {len(missing)} missing source keys; first: {sorted(missing)[0]!r}")
        for source in sources.keys() & translations.keys():
            translated = translations[source]
            if source and not translated:
                errors.append(f"{locale}: empty translation for {source!r}")
            # Only Godot UI text uses printf. Server prose contains literal
            # percentages and uses explicit {0} positional formatting instead.
            if source in client_keys and PRINTF.findall(source) != PRINTF.findall(translated):
                errors.append(f"{locale}: printf placeholder mismatch: {source!r} -> {translated!r}")
            try:
                if brace_fields(source) != brace_fields(translated):
                    errors.append(f"{locale}: brace placeholder mismatch: {source!r} -> {translated!r}")
            except ValueError as exc:
                errors.append(f"{locale}: invalid brace format for {source!r}: {exc}")
            if edge_space(source) != edge_space(translated):
                errors.append(f"{locale}: leading/trailing whitespace differs: {source!r} -> {translated!r}")
            if source.count("\n") != translated.count("\n"):
                errors.append(f"{locale}: newline count differs: {source!r}")
        # The client hides duplicate requirement reasons by this prefix; the
        # server's independently authored prefix must agree in every language.
        if "Wymaga:" in translations and "Wymaga: " in translations:
            if translations["Wymaga:"].strip() != translations["Wymaga: "].strip():
                errors.append(f"{locale}: client/server requirement prefixes disagree")
    errors.extend(raw_ui_literals(root, client_keys))
    main = (root / "client/scripts/main.gd").read_text(encoding="utf-8")
    # The two authenticated/metadata request paths must both localize responses.
    if main.count('"Accept-Language: " + I18n.locale') < 2:
        errors.append("Both gameplay and updater HTTP paths must send Accept-Language.")
    if not re.search(r'var locale:\s*String\s*=\s*"en"', (root / "client/scripts/i18n.gd").read_text(encoding="utf-8")):
        errors.append("First-run language must be explicitly English.")
    return errors, len(sources)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locales", nargs="+", choices=LOCALES, default=list(LOCALES))
    args = parser.parse_args()
    errors, count = validate(ROOT, tuple(args.locales))
    if errors:
        print("Localization validation failed:")
        for error in errors:
            print("-", error)
        return 1
    print(f"Localization OK: {count} source keys × {len(args.locales)} languages; placeholders, whitespace, UI wrapping and HTTP language verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
