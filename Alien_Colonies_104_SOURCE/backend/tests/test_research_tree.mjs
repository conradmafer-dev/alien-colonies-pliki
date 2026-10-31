import test from 'node:test';
import assert from 'node:assert/strict';
import {researchEdges,researchLayout,researchStatus} from '../web/play/research-tree.js';
const node=(key,row=0,column=0,requirements=[])=>({key,tree:{row,column},requirements});
const req=(key,level=1,met=false,group='research')=>({key,level,met,group});

test('edges come only from actual research requirements, with required levels and met state',()=>{
 const data=[node('root'),node('branch',1,1,[req('root',3,true),req('lab',8,false,'buildings'),req('dyson',4,true,'megastructures')])];
 assert.deepEqual(researchEdges(data),[{from:'root',to:'branch',level:3,met:true}]);
});
test('unknown parents do not create dangling lines and no synthetic edges are added',()=>{
 assert.deepEqual(researchEdges([node('a'),node('b',1,1,[req('unknown')])]),[]);
});
test('topological placement always keeps prerequisites above their children',()=>{
 const graph=researchLayout([node('end',0,0,[req('b'),req('c')]),node('c',0,0,[req('a')]),node('b',0,0,[req('a')]),node('a')]);
 const byKey=Object.fromEntries(graph.nodes.map(n=>[n.key,n]));
 for(const edge of graph.edges)assert.ok(byKey[edge.from].row<byKey[edge.to].row);
 assert.equal(new Set(graph.nodes.map(n=>`${n.row}:${n.column}`)).size,4);
});
test('three-column layout retains valid authoritative coordinates',()=>{
 const data=[node('a',0,0),node('b',1,2,[req('a')]),node('c',3,1,[req('a'),req('b')])];
 const graph=researchLayout(data);
 assert.deepEqual(graph.nodes.map(n=>[n.row,n.column]),[[0,0],[1,2],[3,1]]);
 assert.equal(graph.rows,4);assert.equal(graph.columns,3);
});
test('position collisions are resolved without overlap or extra columns',()=>{
 const graph=researchLayout(Array.from({length:25},(_,i)=>node(String(i),0,i%3)));
 assert.equal(graph.nodes.length,25);
 assert.equal(new Set(graph.nodes.map(n=>`${n.row}:${n.column}`)).size,25);
 assert.ok(graph.nodes.every(n=>n.column>=0&&n.column<3));
});
test('cycle is rejected rather than hanging the renderer',()=>{
 assert.throws(()=>researchLayout([node('a',0,0,[req('b')]),node('b',0,1,[req('a')])]),/Cyclic/);
});
test('input order and requirements are not mutated',()=>{
 const data=[node('last',0,2,[req('first')]),node('first')],before=JSON.stringify(data);
 researchLayout(data);researchEdges(data);assert.equal(JSON.stringify(data),before);
});
test('empty tree is valid',()=>{
 assert.deepEqual(researchLayout([]),{nodes:[],edges:[],rows:0,columns:3});
});
test('queued research has active status, not an unlocked completed level',()=>{
 assert.equal(researchStatus({key:'a',level:0,max_level:1,enabled:false},{key:'a'}),'active');
});
test('completed blueprints cannot be marked ready for another level',()=>{
 assert.equal(researchStatus({key:'a',level:1,max_level:1,enabled:false},null),'complete');
});
test('available, resource-limited, learned and prerequisite-locked states are distinct',()=>{
 const a={key:'a',level:0,max_level:12};
 assert.equal(researchStatus({...a,enabled:true},null),'ready');
 assert.equal(researchStatus({...a,enabled:false,requirements_met:true},null),'waiting');
 assert.equal(researchStatus({...a,level:3,enabled:false},null),'learned');
 assert.equal(researchStatus({...a,enabled:false,requirements_met:false},null),'locked');
});
