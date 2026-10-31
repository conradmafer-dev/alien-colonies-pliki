import test from 'node:test';
import assert from 'node:assert/strict';
import {rankingHtml,rankingCategories} from '../web/play/ranking.js';

test('five server ranking categories and escaped player names', () => {
  assert.deepEqual(Object.keys(rankingCategories),['total','buildings','research','fleet','defense']);
  const row={position:62,score:8,name:'<img src=x onerror=alert(1)>',is_self:true,scores:{buildings:0,research:0,fleet:8,defense:0,total:8}};
  const markup=rankingHtml({self:row,items:[row],page:2,pages:2,players_total:62});
  assert.match(markup,/&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(markup,/<img src=x/);
  assert.match(markup,/data-ranking-self/);
  assert.match(markup,/data-ranking-own/);
  assert.match(markup,/data-ranking-page="1"/);
  assert.match(markup,/data-ranking-page="3"[^>]* disabled/);
});

test('loading and failure preserve retry and disable redundant navigation', () => {
  const loading=rankingHtml(null,{busy:true});
  assert.match(loading,/aria-busy="true"/);
  assert.match(loading,/data-ranking-refresh disabled/);
  assert.match(loading,/Ładowanie rankingu/);
  const error=rankingHtml(null,{error:'Server <unavailable>'});
  assert.match(error,/Server &lt;unavailable&gt;/);
  assert.doesNotMatch(error,/data-ranking-refresh disabled/);
});


test('race names beside empire names use controlled faction colour classes', () => {
  for (const [race, expected] of [['zetans','Zetanie'],['automatons','Automatony'],['symbionts','Symbionci']]) {
    const row={position:13,score:10,name:'My Empire',race_id:race,is_self:true,scores:{}};
    const markup=rankingHtml({self:row,items:[row],page:1,pages:1,players_total:30});
    assert.ok(markup.includes('ranking-race--'+race));
    assert.ok(markup.includes(expected));
  }
});
