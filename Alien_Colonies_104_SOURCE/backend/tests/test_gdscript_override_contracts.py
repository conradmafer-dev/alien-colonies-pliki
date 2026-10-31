"""Static regression checks for test doubles inheriting main.gd.

These checks cover the one-line method declarations used by these test doubles.
They do not parse all GDScript and do not replace an import/test run in Godot.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = re.compile(
    r"^(?P<indent>\t*)func (?P<name>\w+)\((?P<args>[^\n]*)\)\s*->\s*(?P<result>\w+):",
    re.MULTILINE,
)


def declarations(text, indent):
    """Return argument type/default pairs and return type, ignoring argument names."""
    found = {}
    for match in DECLARATION.finditer(text):
        if len(match['indent']) != indent:
            continue
        args = []
        if match['args'].strip():
            for arg in match['args'].split(','):
                _, typed = arg.strip().split(':', 1)
                type_name, separator, default = typed.partition('=')
                args.append((type_name.strip(), default.strip() if separator else None))
        found[match['name']] = (tuple(args), match['result'])
    return found


class GDScriptOverrideContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / 'client/scripts/main.gd').read_text(encoding='utf-8')
        cls.language = (ROOT / 'tests/test_language_switch.gd').read_text(encoding='utf-8')
        cls.base = declarations(cls.main, 0)
        cls.overrides = declarations(cls.language, 1)

    def test_poll_accepts_the_same_optional_boolean_as_production(self):
        self.assertEqual(self.base['_poll'], ((("bool", "false"),), "void"))
        self.assertEqual(self.overrides['_poll'], self.base['_poll'])

    def test_original_missing_argument_would_be_detected(self):
        old = declarations('\tfunc _poll() -> void:\n\t\tpass\n', 1)
        self.assertNotEqual(old['_poll'], self.base['_poll'])

    def test_all_main_test_double_overrides_have_matching_contracts(self):
        count = 0
        for path in sorted((ROOT / 'tests').glob('*.gd')):
            source = path.read_text(encoding='utf-8')
            if '\textends "res://client/scripts/main.gd"' not in source:
                continue
            for name, signature in declarations(source, 1).items():
                if name in self.base:
                    with self.subTest(file=path.name, method=name):
                        self.assertEqual(signature, self.base[name])
                    count += 1
        self.assertGreaterEqual(count, 10, 'Expected to inspect both existing offline test doubles')

    def test_language_test_keeps_network_and_session_isolation(self):
        self.assertIn('gameplay_requests.append(', self.language)
        self.assertIn('func _save_session() -> void:', self.language)
        self.assertNotIn('super._poll', self.language)
        self.assertIn('session_saves += 1', self.language)
        self.assertIn('alien-language-', self.language)

    def test_test_scripts_remain_excluded_from_all_export_presets(self):
        source = (ROOT / 'export_presets.cfg').read_text(encoding='utf-8')
        filters = re.findall(r'^exclude_filter="([^"]*)"', source, re.MULTILINE)
        self.assertEqual(len(filters), 3)
        for value in filters:
            self.assertIn('tests/*', value.split(','))


if __name__ == '__main__':
    unittest.main()
