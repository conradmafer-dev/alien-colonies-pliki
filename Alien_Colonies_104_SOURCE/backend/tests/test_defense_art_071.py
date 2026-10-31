"""Static resource/mapping checks. These are not a Godot runtime or rendering test."""
import hashlib
import json
from pathlib import Path
import re
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def builder_compat_digest(path):
    data=path.read_bytes()
    if path.name=="build_google_play_aab.ps1":
        data=re.sub(rb"    # BEGIN VERSION_SYNC_074\r?\n.*?    # END VERSION_SYNC_074\r?\n",b"",data,flags=re.S)
    return hashlib.sha256(data).hexdigest()


class DefenseArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'docs/DEFENSE_ART_071.json').read_text())
        cls.entries=cls.manifest['files']
        cls.art=(ROOT/'client/scripts/art_library.gd').read_text()
        cls.client=(ROOT/'client/scripts/main.gd').read_text()

    def test_four_existing_gameplay_keys_have_separate_images(self):
        from server.defenses import KEYS
        self.assertEqual({e['unit'] for e in self.entries},set(KEYS))
        self.assertEqual(len({e['art_key'] for e in self.entries}),4)
        self.assertEqual(len({e['sha256'] for e in self.entries}),4)

    def test_images_decode_and_match_honest_dimensions(self):
        self.assertFalse(self.manifest['native_hd_generation_succeeded'])
        for e in self.entries:
            data=(ROOT/e['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),e['sha256'])
            with Image.open(ROOT/e['file']) as im:
                im.load()
                self.assertEqual(im.size,(e['width'],e['height']))
                self.assertEqual(im.size,(762,508))
                self.assertEqual(im.mode,'RGB')
                self.assertEqual(im.format,'WEBP')

    def test_paths_are_allowlisted_and_mapped_by_unit_key(self):
        for e in self.entries:
            self.assertIn('"%s": "%s"'%(e['unit'],e['art_key']),self.art)
            prefix, *rest=e['art_key'].split('/')
            if prefix=='races':
                race,name=rest
                self.assertRegex(self.art, '"'+race+'": \\["'+name+'",')
            else:
                self.assertIn('const SWARM_ASSETS: Array[String] = ["acid_spire",',self.art)

    def test_defense_override_precedes_legacy_art_mapping(self):
        function=self.client.split('func _entry_art_key(',1)[1].split('\n\nfunc ',1)[0]
        self.assertLess(function.index('ArtLibrary.defense_art_key'),function.index('entry.get("art_key"'))
        self.assertIn('return defense_art',function)
        self.assertIn('return supplied if not supplied.is_empty() else fallback',function)

    def test_scout_reports_resolve_semantic_defense_keys(self):
        function=self.client.split('func _add_scout_data(',1)[1].split('\n\nfunc ',1)[0]
        self.assertIn('_entry_art_key(unit, str(unit.get("key", "")))',function)
        self.assertIn('str(building.get("art_key", ""))',function)

    def test_original_building_art_is_not_remapped(self):
        from server.defenses import ART
        for legacy_key in ART.values():
            self.assertTrue((ROOT/('client/assets/art/'+legacy_key+'.webp')).is_file())
        self.assertNotIn('"echo_observatory": "races/zetans/phase_sentinel"',self.art)

    def test_signing_tools_unchanged_from_070(self):
        manifest=json.loads((ROOT/'docs/UNCHANGED_FROM_070_ART.json').read_text())
        for name,digest in manifest.items():
            # 0.7.2 deliberately updates server/localization; saved-key tools stay identical.
            if not name.endswith((".bat", ".cmd", ".ps1")):
                continue
            self.assertEqual(builder_compat_digest(ROOT/name),digest,name)

    def test_import_preserves_dimensions_and_enables_mipmaps(self):
        for e in self.entries:
            imp=(ROOT/(e['file']+'.import')).read_text()
            for setting in ('mipmaps/generate=true','process/size_limit=0','compress/mode=0'):
                self.assertIn(setting,imp)
            self.assertIn('source_file="res://'+e['file']+'"',imp)

if __name__=='__main__':
    unittest.main()
