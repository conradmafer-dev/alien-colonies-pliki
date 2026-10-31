import test from 'node:test';
import assert from 'node:assert/strict';
import {buildingSummary, buildingComparison, buildingNotes} from '../web/play/building-effects.js';
import {ellipseLayout, sortSystems, systemStatus} from '../web/play/galaxy-map.js';
const make = (key, level, metrics = [], rest = {}) => ({key, level, max_level:12, details:{metrics}, ...rest});

test('mine uses authoritative building contribution, not passive colony production', () => {
  const item = make('metal_mine', 4, [
    {key:'mine_metal', current:200, next:220, unit:'per_hour'},
    {key:'colony_metal', current:250, next:270, unit:'per_hour'},
    {key:'energy_use', current:60, next:75},
  ], {production_resource:'metal'});
  assert.equal(buildingSummary(item), 'Metal 200/h');
  const rows = buildingComparison(item);
  assert.equal(rows[0].current,'200/h');
  assert.equal(rows[0].next,'220/h');
  assert.equal(rows.length,2);
  assert.equal(buildingComparison(item,true)[2].current,'250/h');
});

test('energy shortage is not silently replaced with nominal or always increasing production', () => {
  const item = make('metal_mine', 4, [
    {key:'mine_metal',current:120,next:118,unit:'per_hour'},
    {key:'energy_efficiency',current:60,next:45,unit:'percent'},
  ],{production_resource:'metal'});
  assert.equal(buildingComparison(item)[0].next,'118/h');
  assert.ok(buildingNotes(item).some(note=>note.includes('Niedobór energii')));
  assert.ok(!buildingComparison(item).some(row=>row.label.includes('Wydajność')));
});

test('facility speed is rendered from server preview, without confusing speed and time reduction', () => {
  const item = make('lab',3,[{key:'lab_speed_bonus',current:20,next:30,unit:'percent'},
    {key:'facility_time_reduction',current:16.666667,next:23.076923,unit:'percent'}]);
  assert.equal(buildingSummary(item),'Badania +20%');
  assert.equal(buildingComparison(item)[0].next,'+30%');
  assert.equal(buildingComparison(item).length,1);
  assert.equal(buildingComparison(item,true)[1].current,'16,67%');
});

test('power plant card excludes unrelated Dyson sphere energy', () => {
  const item = make('power_plant',2,[{key:'energy_supply',current:1080,next:1120}],{energy_supply_current:80,energy_supply_next:120,energy_supply_per_level:999});
  assert.equal(buildingSummary(item),'Energia +80');
  assert.equal(buildingComparison(item)[0].next,'120');
  assert.equal(buildingComparison(item,true)[1].current,'1080');
});

test('unbuilt and fully upgraded buildings never invent a purchasable next level', () => {
  const zero=make('metal_mine',0,[{key:'mine_metal',current:0,next:45,unit:'per_hour'}],{production_resource:'metal'});
  assert.equal(buildingSummary(zero),'Metal 0/h');
  const max=make('metal_mine',12,[{key:'mine_metal',current:700,next:null,unit:'per_hour'}],{production_resource:'metal'});
  assert.equal(buildingComparison(max)[0].next,null);
  const unique=make('world_root',5,[],{max_level:5,building_effect:{key:'building_time_reduction',current:.4,next:null}});
  assert.equal(buildingSummary(unique),'Czas budowy −40%');
  assert.equal(buildingComparison(unique)[0].next,null);
});

test('racial effects retain percent, percentage points, stock and colony-start units', () => {
  const item=(key,current,next)=>make('unique',2,[],{unique:true,max_level:5,building_effect:{key,current,next}});
  assert.equal(buildingSummary(item('renewal_fraction',.04,.06)),'Regeneracja obrony +4 pkt proc.');
  assert.equal(buildingSummary(item('protected_resources',3000,4500)),'Ochrona surowców 3000 / surowiec');
  assert.equal(buildingSummary(item('colony_start_building_bonus',2,3)),'Start kolonii poz. 3');
  assert.equal(buildingSummary(item('defense_first_volley',.24,.36)),'Pierwsza salwa obrony +24%');
  assert.equal(buildingSummary(item('wreck_recovery_fraction',.1,.15)),'Odzysk metalu z wraków 10%');
  assert.equal(buildingComparison(item('batch_time_reduction_per_extra',.015,.03))[0].current,'−1,5%');
});

test('observatory inactivity and maximum range are shown without negative ranges', () => {
  const item=make('observatory',0,[],{observation:{current:{range:-1,building_range:-1},next:{range:1,building_range:-1}}});
  assert.equal(buildingSummary(item),'Obserwacja nieaktywna');
  assert.equal(buildingComparison(item)[0].next,'1 w każdą stronę');
});

test('map status uses only visible information and prioritizes the player colony', () => {
  const s={visibility:'unknown',planets:[]};
  assert.equal(systemStatus(s,'u1'),'unknown');
  assert.equal(systemStatus({...s,visibility:'scouted',planets:[{owner_id:'khar'}]},'u1'),'swarm');
  assert.equal(systemStatus({...s,visibility:'observed',planets:[{owner_id:'khar'},{owner_id:'u1'}]},'u1'),'own');
  assert.equal(systemStatus({...s,visibility:'remembered',planets:[{owner_id:'u2',owner_type:'player'}]},'u1'),'inhabited');
});

test('numeric ordering is stable and does not mutate server coordinates or source arrays', () => {
  const systems=[{id:'s10',x:3,y:5},{id:'s2',x:4,y:9},{id:'s1',x:0,y:0}];
  const before=JSON.stringify(systems);
  assert.deepEqual(sortSystems(systems).map(s=>s.id),['s1','s2','s10']);
  assert.equal(JSON.stringify(systems),before);
});

test('30 points lie on an ellipse, remain in bounds and are separated at mobile and desktop sizes', () => {
  for (const [w,h] of [[338,475],[364,475],[490,530],[760,530],[1000,565]]) {
    const points=ellipseLayout(30,w,h);
    assert.equal(points.length,30);
    const rx=w*(w<500?.39:.41), ry=h*(w<500?.40:.36);
    for (let i=0;i<points.length;i++) {
      const a=points[i],b=points[(i+1)%points.length];
      const ellipse=((a.x-w/2)/rx)**2+((a.y-h/2)/ry)**2;
      assert.ok(Math.abs(ellipse-1)<.00002);
      assert.ok(a.x>20&&a.y>20&&a.x<w-20&&a.y<h-20);
      assert.ok(Math.hypot(a.x-b.x,a.y-b.y)>32,`${w}: point separation`);
    }
  }
  assert.deepEqual(ellipseLayout(0,800,500),[]);
});
