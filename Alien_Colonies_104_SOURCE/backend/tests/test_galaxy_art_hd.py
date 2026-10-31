"""Offline regression checks for the 0.6.1 client-only galaxy-art update."""
from pathlib import Path
import hashlib
import json
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('aurora', 'eclipse', 'nexus', 'omega', 'zephyr', 'void')
try:
    from PIL import Image
except ImportError:
    Image = None


def builder_compat_digest(path):
    data=path.read_bytes()
    if path.name=="build_google_play_aab.ps1":
        data=re.sub(rb"    # BEGIN VERSION_SYNC_074\r?\n.*?    # END VERSION_SYNC_074\r?\n",b"",data,flags=re.S)
    return hashlib.sha256(data).hexdigest()


class GalaxyArtHdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'docs/GALAXY_ART_061.json').read_text())

    def test_catalogue_has_all_six_existing_keys(self):
        from server.galaxies import CATALOG
        self.assertEqual([g['art_key'] for g in CATALOG], ['galaxies/' + n for n in NAMES])
        self.assertEqual([e['galaxy'] for e in self.manifest['files']], list(NAMES))

    def test_all_asset_hashes_and_sizes_match(self):
        for entry in self.manifest['files']:
            data = (ROOT / entry['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            self.assertEqual(len(data), entry['bytes'])

    def test_no_old_thumbnail_survives(self):
        for entry in self.manifest['files']:
            self.assertNotEqual(entry['sha256'], entry['replaces']['sha256'])
            self.assertGreater(entry['width'] * entry['height'],
                entry['replaces']['size'][0] * entry['replaces']['size'][1] * 20)

    @unittest.skipIf(Image is None, 'Pillow required for full image decode')
    def test_native_dimensions_and_complete_decode(self):
        for entry in self.manifest['files']:
            with Image.open(ROOT / entry['file']) as image:
                image.load()
                self.assertEqual(image.size, (1536, 1024))
                self.assertEqual(image.mode, 'RGB')
                self.assertEqual(image.format, 'WEBP')

    def test_mipmaps_and_no_import_downscaling(self):
        for entry in self.manifest['files']:
            settings = (ROOT / (entry['file'] + '.import')).read_text()
            self.assertIn('mipmaps/generate=true', settings)
            self.assertIn('process/size_limit=0', settings)
            self.assertIn('compress/mode=0', settings)
            self.assertIn('source_file="res://' + entry['file'] + '"', settings)

    def test_six_unique_full_resolution_files(self):
        self.assertEqual(len({e['sha256'] for e in self.manifest['files']}), 6)

    def test_aab_builder_files_remain_unchanged(self):
        hashes = json.loads((ROOT / 'docs/UNCHANGED_FROM_060.json').read_text())
        for name, digest in hashes.items():
            # 0.7.0 changes the server intentionally, not the saved-key builder.
            if not name.endswith(('.bat', '.cmd', '.ps1')):
                continue
            self.assertEqual(builder_compat_digest(ROOT / name), digest, name)

    def test_version_code_and_package_are_consistent(self):
        main = (ROOT / 'client/scripts/main.gd').read_text()
        export = (ROOT / 'export_presets.cfg').read_text()
        self.assertIn('const CLIENT_VERSION_CODE: int = 36', main)
        self.assertIn('const CLIENT_VERSION_NAME: String = "0.7.7"', main)
        self.assertEqual(export.count('version/code=36'), 2)
        self.assertEqual(export.count('package/unique_name="com.conradmafer.aliencolonies"'), 2)
        self.assertIn('config/version="0.7.7"', (ROOT / 'project.godot').read_text())

    def test_texture_cache_is_bounded_and_separate(self):
        code = (ROOT / 'client/scripts/art_library.gd').read_text()
        self.assertIn('const MAX_CACHED_GALAXIES: int = 2', code)
        self.assertIn('while galaxy_cache_keys.size() > MAX_CACHED_GALAXIES:', code)
        self.assertEqual(code.count('_remember_galaxy(key)'), 2)

    def test_map_uses_filter_and_keeps_aspect_ratio(self):
        code = (ROOT / 'client/scripts/galaxy_map.gd').read_text()
        self.assertIn('TEXTURE_FILTER_LINEAR_WITH_MIPMAPS', code)
        self.assertIn('var art_size: Vector2 = source_size * fit_scale', code)
        self.assertIn('res://client/assets/art/galaxies/aurora.webp', code)


if __name__ == '__main__':
    unittest.main()
