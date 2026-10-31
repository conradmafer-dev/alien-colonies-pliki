import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// Load the browser module as ESM without changing the repository's runtime.
const source = await readFile(new URL('../colony-capture.js', import.meta.url), 'utf8');
const {canAttemptColonization, COLONIZATION_WARNING} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const state = {player:{id:'p1'}, alliance:{id:'a1'}, colonization_capture:{enabled:true}};
const colony = {owner_type:'player', owner_id:'p2', is_home_planet:false};
assert.equal(canAttemptColonization(state,colony,100),true);
assert.equal(canAttemptColonization(state,{...colony,is_home_planet:true},100),false);
assert.equal(canAttemptColonization(state,{owner_type:'player',owner_id:'p2'},100),false);
assert.equal(canAttemptColonization({...state,colonization_capture:undefined},colony,100),false);
assert.equal(canAttemptColonization(state,{...colony,owner_id:'p1'},100),false);
assert.equal(canAttemptColonization(state,{...colony,alliance_id:'a1'},100),false);
assert.equal(canAttemptColonization(state,{...colony,protected_until:101},100),false);
assert.equal(canAttemptColonization(state,{...colony,protected_until:100},100),true);
assert.equal(canAttemptColonization(state,{owner_type:'alien',owner_id:'khar'},100),false);
assert.equal(canAttemptColonization(state,{owner_type:'empty',owner_id:null},100),true);
assert.equal(canAttemptColonization(state,null,100),false);
assert.match(COLONIZATION_WARNING,/wsparcia sojuszników/);
console.log('12 colony capture web checks passed');
