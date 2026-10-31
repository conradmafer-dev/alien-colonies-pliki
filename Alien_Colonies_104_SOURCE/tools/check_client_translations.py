"""Reject missing Android UI translations and mismatched printf placeholders."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALL = re.compile(r'''I18n\s*\.\s*t\s*\(\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''')
FORMAT = re.compile(r"%(?:[-+0 #]*\d*(?:\.\d+)?[scdiuoxXfFeEgGv]|%)")


def main():
    keys = {ast.literal_eval(match[1]) for path in (ROOT / "client").rglob("*.gd")
            for match in CALL.finditer(path.read_text(encoding="utf-8"))}
    errors = []
    for language in ("en", "pl", "de", "es", "fr"):
        catalog = json.loads((ROOT / f"localization/{language}.json").read_text(encoding="utf-8"))
        for key in sorted(keys):
            value = catalog.get(key)
            if not isinstance(value, str) or not value:
                errors.append(f"{language}: missing {key!r}")
            elif FORMAT.findall(key) != FORMAT.findall(value):
                errors.append(f"{language}: invalid placeholders {key!r}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(keys)} authored client strings in all 5 languages; placeholders preserved")


if __name__ == "__main__":
    main()
