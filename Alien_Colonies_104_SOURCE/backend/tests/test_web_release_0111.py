"""0.11.1 regressions: dedicated assets, localization and complete deployments."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
import fleet_expansion
from i18n import language_scope


class WebRelease111Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.world=app.World(str(Path(self.temp.name)/'world.sqlite3'),1)
    def tearDown(self):
        self.world.close();self.temp.cleanup()
    def account(self,race):
        account=self.world.register('test_'+race,'LocalTest-only-1234')
        owner=account['state']['player']['id'];pid=account['state']['planet_id']
        self.world.action(owner,{'type':'choose_race','race_id':race,'planet_id':pid})
        return owner,pid
    def manifest(self):
        text=(ROOT/'web/play/art-manifest.js').read_text()
        return json.loads(text.split('Object.freeze(',1)[1].rsplit(');',1)[0])
    def test_all_12_new_ships_have_dedicated_unique_packaged_art(self):
        art=self.manifest();seen=set()
        for race in app.RACES:
            owner,pid=self.account(race)
            with language_scope('en'):
                catalog=self.world.state(owner,pid)['catalog']['ships']
            for item in catalog:
                if item['key'] not in fleet_expansion.CAPITAL_ROLES:continue
                key=item['web_art_key'];self.assertEqual(key,f"fleet/{race}/{item['key']}")
                file=ROOT/'web'/art[key]['src'].lstrip('/')
                data=file.read_bytes();digest=hashlib.sha256(data).hexdigest()
                self.assertNotIn(digest,seen);seen.add(digest)
        self.assertEqual(len(seen),12)
    def test_each_of_35_technologies_has_its_own_icon_and_no_building_alias(self):
        art=self.manifest();by_key={}
        for race in app.RACES:
            owner,pid=self.account(race)
            for item in self.world.state(owner,pid)['catalog']['research']:
                key=item['web_art_key'];self.assertEqual(key,'research/'+item['key'])
                file=ROOT/'web'/art[key]['src'].lstrip('/')
                by_key[key]=hashlib.sha256(file.read_bytes()).hexdigest()
        self.assertEqual(len(by_key),35)
        self.assertEqual(len(set(by_key.values())),35)
    def test_new_catalogue_and_effects_are_english_without_polish_leakage(self):
        expected={'zetans':['Horizon Guardian','Cataclysm','Singularity Prism','Zenith Ark'],
                  'symbionts':['Behemoth','Star Devourer','Matriarch','Progenitor'],
                  'automatons':['Dominator','Executioner','Omega Bastion','Eternity Colossus']}
        for race in app.RACES:
            owner,pid=self.account(race)
            with language_scope('en'):
                state=self.world.state(owner,pid)
                ships=[s for s in state['catalog']['ships'] if s['key'] in fleet_expansion.CAPITAL_ROLES]
                self.assertEqual([s['name'] for s in ships],expected[race])
                for item in [*ships,*state['catalog']['research']]:
                    for field in ['name','description','effect_current','effect_next','reason','role_name']:
                        self.assertNotRegex(str(item.get(field,'')),r'[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]',(race,item['key'],field))
    def test_added_server_content_has_all_five_locales(self):
        sources=['Konstrukcja okrętów liniowych','Uzbrojenie okrętów liniowych','Rdzeń tytana']
        sources += [v[0] for ships in fleet_expansion.SHIPS.values() for v in ships.values()]
        sources += [v[1] for ships in fleet_expansion.SHIPS.values() for v in ships.values()]
        sources += ['Odblokowuje okręt specjalny: '+fleet_expansion.SHIPS[r]['flagship'][0]+'.' for r in app.RACES]
        for lang in ['en','de','es','fr']:
            catalog=json.loads((ROOT/(lang+'.json')).read_text())
            for source in sources:self.assertTrue(catalog.get(source),(lang,source))
    def test_frontend_locales_exist_and_default_language_is_english(self):
        for lang in ['en','pl','de','es','fr']:
            data=json.loads((ROOT/'web/play/locales'/f'{lang}.json').read_text())
            self.assertTrue(data['Ustawienia'])
        self.assertEqual(json.loads((ROOT/'web/play/locales/en.json').read_text())['Ustawienia'],'Settings')
        self.assertIn("browser ? 'en' : 'pl'",(ROOT/'web/play/i18n.js').read_text())
    def test_release_manifest_matches_every_runtime_file(self):
        release=json.loads((ROOT/'web/play/release.json').read_text())
        self.assertEqual(release['version'],app.VERSION)
        for name,digest in release['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/'web'/name).read_bytes()).hexdigest(),digest,name)
        for name in ['play/game.js','play/i18n.js','play/galaxy-map.js','play/research-tree.js','play/release.css']:
            self.assertIn(name,release['files'])
    def test_translation_does_not_change_player_authored_names(self):
        owner,pid=self.account('zetans')
        self.world._player(owner)['name']='Budynki'
        self.world.data['planets'][pid]['name']='Kryształy'
        with language_scope('en'):
            state=self.world.state(owner,pid)
        self.assertEqual(state['player']['name'],'Budynki')
        self.assertEqual(state['planet_name'],'Kryształy')
