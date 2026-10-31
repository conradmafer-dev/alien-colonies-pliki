import test from 'node:test';
import assert from 'node:assert/strict';
import {resetMissionDraft,projectReason,protectedPlanet} from '../compact-ui.js';

test('starting another expedition discards its target, quantities, cargo, quote and travel mode',()=>{
 const model={fleetTarget:'old-world',fleetSystemId:'old-system',fleetMission:'attack',fleetTravelMode:'tunnel',fleetPreview:{fuel:123},fleetDraft:{ships:{scout:4},cargo:{metal:500}},galaxyId:'g2',planet_id:'current-colony'};
 resetMissionDraft(model);
 assert.equal(model.fleetTarget,'');assert.equal(model.fleetSystemId,'');assert.equal(model.fleetMission,'scout');assert.equal(model.fleetTravelMode,'normal');assert.equal(model.fleetPreview,null);assert.equal(model.fleetDraft,null);assert.equal(model.missionSelecting,true);assert.equal(model.galaxyMode,'map');assert.equal(model.planet_id,'current-colony');
});
test('requirements are not repeated, but origin, queue and resource blockers remain visible',()=>{
 const requirements=[{met:false}];
 assert.equal(projectReason({requirements,reason:'Wymaga: Stocznia 7.'}),'');
 assert.equal(projectReason({requirements,reason:'Nie spełniono wymagań projektu.'}),'');
 for(const reason of ['Odzyskaj kolonię będącą centrum projektu.','Budowa megastruktury już trwa.','Brakuje surowców.'])assert.equal(projectReason({requirements,reason}),reason);
 assert.equal(projectReason({requirements:[],reason:'Brakuje surowców.'}),'Brakuje surowców.');
});
test('known protection expires at its advertised deadline and missing intelligence never invents a shield',()=>{
 assert.equal(protectedPlanet({protected_until:120},100),true);
 assert.equal(protectedPlanet({protected_until:120},120),false);
 assert.equal(protectedPlanet({protected_until:120},121),false);
 assert.equal(protectedPlanet({},100),false);
});
