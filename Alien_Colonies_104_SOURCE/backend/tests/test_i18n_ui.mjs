import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {t,html,text,LANGUAGES} from '../web/play/i18n.js';
const root=new URL('../',import.meta.url);

test('five selectable language codes are stable',()=>assert.deepEqual(Object.keys(LANGUAGES),['en','pl','de','es','fr']));
test('text templates preserve numbers and opaque player-authored strings',()=>{
 assert.equal(text`Poziom ${12}`,'Poziom 12');
 assert.equal(text`${'Budynki {0}'} · ${4} statków`,'Budynki {0} · 4 statków');
});
test('HTML localization does not translate/interpolate player names a second time',()=>{
 assert.equal(html`<h2>${'Kryształy {0}'}</h2>`,'<h2>Kryształy {0}</h2>');
});
test('HTML tags, machine attributes and URLs retain their original values',()=>{
 assert.equal(html`<button data-kind="${'research'}" title="Szczegóły: ${'Prism'}">${'Prism'}</button>`, '<button data-kind="research" title="Szczegóły: Prism">Prism</button>');
});
test('escaped player content remains escaped',()=>{
 assert.equal(html`<p>${'&lt;img src=x onerror=alert(1)&gt;'}</p>`,'<p>&lt;img src=x onerror=alert(1)&gt;</p>');
});
test('localized string interpolation handles zero and false without dropping values',()=>{
 assert.equal(t('{0} / {1}',0,false),'0 / false');
});
test('all UI keys exist in all five compiled catalogs',()=>{
 const keys=JSON.parse(fs.readFileSync(new URL('web/play/locale-keys.json',root)));
 for(const code of Object.keys(LANGUAGES)){
  const dict=JSON.parse(fs.readFileSync(new URL(`web/play/locales/${code}.json`,root)));
  for(const key of keys)assert.ok(Object.hasOwn(dict,key),`${code}: ${key}`);
 }
});
test('translations keep the same placeholder set as their source',()=>{
 const placeholders=s=>[...new Set(s.match(/\{\d+\}/g)||[])].sort();
 for(const code of Object.keys(LANGUAGES)){
  const dict=JSON.parse(fs.readFileSync(new URL(`web/play/locales/${code}.json`,root)));
  for(const [key,value] of Object.entries(dict))assert.deepEqual(placeholders(value),placeholders(key),`${code}: ${key}`);
 }
});
