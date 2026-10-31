import test from 'node:test';
import assert from 'node:assert/strict';
import {rankingHtml,rankingRewardDisplay,rankingRewardHtml} from '../ranking.js';
import {reportIconKind} from '../fleet-motion.js';
import {reportTypeIcon} from '../report-icons.js';

const reward={schema:1,category:'total',position:11,active:true,days_per_crystal:14,interval_seconds:14*86400,progress:0.5,remaining_seconds:7*86400,as_of:100};

test('reward displays the overall position and fourth tier independently of the selected category',()=>{
 const markup=rankingHtml({self:{position:2,score:10,scores:{}},items:[],page:1,pages:1,reward},{category:'fleet'});
 assert.match(markup,/#11 · 1 \/ 14 d/);
 assert.match(markup,/data-art-key="swarm\/crystal"/);
 assert.match(markup,/11–30: 1 \/ 14 dni/);
 assert.match(markup,/value="0.5"/);
});
test('display interpolation follows the server rate and stops at one complete crystal',()=>{
 assert.equal(rankingRewardDisplay(reward,100+86400).progress,0.5+1/14);
 const ready=rankingRewardDisplay(reward,100+8*86400);
 assert.equal(ready.progress,1);
 assert.match(ready.status,/100%.*Sprawdzanie/);
 assert.equal(reward.progress,0.5);
});
test('paused reward preserves progress and never extrapolates offline time',()=>{
 const paused={...reward,position:31,active:false,days_per_crystal:0,interval_seconds:0,remaining_seconds:null};
 const view=rankingRewardDisplay(paused,100+100*86400);
 assert.equal(view.progress,0.5);
 assert.match(view.caption,/TOP 30/);
 assert.match(view.status,/wstrzymane/);
 assert.equal(rankingRewardHtml(undefined),'');
});
test('a newer authenticated state snapshot refreshes only the current reward',()=>{
 const later={...reward,as_of:200,position:1,days_per_crystal:3};
 const markup=rankingHtml({self:{position:2,score:0,scores:{}},items:[],reward},{reward:later});
 assert.match(markup,/#1 · 1 \/ 3 d/);
 assert.doesNotMatch(markup,/#11 · 1 \/ 14 d/);
});
test('ranking reward reports have a stable crystal-shaped report icon',()=>{
 assert.equal(reportIconKind({kind:'ranking'}),'ranking');
 assert.match(reportTypeIcon({kind:'ranking'}),/data-report-kind="ranking"/);
 assert.doesNotMatch(reportTypeIcon({kind:'ranking'}),/undefined/);
});
