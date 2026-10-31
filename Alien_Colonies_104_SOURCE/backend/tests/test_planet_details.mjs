import test from 'node:test';
import assert from 'node:assert/strict';
import {planetInspection, planetDetailsHtml} from '../web/play/planet-details.js';

function fixture() {
  const own = {id:'s1p1', name:'Home', system_id:'s1', galaxy_id:'g1', owner_id:'p1', owner_type:'player', visibility:'own', environment:{type_name:'Oceaniczna', fields:88}};
  const enemy = {id:'s1p2', name:'Nest', system_id:'s1', galaxy_id:'g1', owner_id:'khar', owner_type:'alien', owner_name:'Rój Khar', visibility:'scouted', has_scout:true, scouted_at:300, swarm_crystals_stock:97, resources:{metal:987654}, environment:{type_name:'Lodowa'}, planet_scout:{id:'s1p2', scouted_at:300, resources:{metal:987654}, ships_display:[{key:'frigate',name:'Nowa migawka',count:97}]}};
  const empty = {id:'s1p3', name:'Free', system_id:'s1', galaxy_id:'g1', owner_id:'', owner_type:'empty', visibility:'observed', environment:{type_name:'Organiczna'}};
  const system = {id:'s1',name:'Alpha',galaxy_id:'g1',visibility:'scouted',scouted_at:300,planets:[own,enemy,empty]};
  const report = {id:'r1',at:200,title:'Zwiad historyczny',text:'Prawdziwy raport zwiadu',planet_scout:{id:'s1p2',scouted_at:200,owner_id:'khar',owner_type:'alien',resources:{metal:12345,crystal:1234,fuel:0},ships_display:[{key:'frigate',name:'Historyczna fregata',count:7}],defenses_display:[],observed_buildings:[{key:'shipyard',name:'Historyczna stocznia',level:2}]},scout:{id:'s1p2',scouted_at:200,swarm_crystals_stock:3,swarm_crystals_capacity:6,swarm_units:[{key:'frigate',name:'Historyczna fregata',count:7}],swarm_defenses:[],swarm_activity:'Rozbudowuje flotę'}};
  return {player:{id:'p1',name:'Test',race_id:'zetan'},planet_id:'s1p1',planet_name:'Home',server_time:1000,own_planets:[own],galaxy:[system],reports:[report],ships:{scout:2},resources:{metal:6789,crystal:88,fuel:66},fields:{total:88,used:4,free:84},catalog:{ships:[{key:'scout',name:'Zwiadowca'}],defenses:[],buildings:[]},environment:own.environment};
}

test('inspection resolves visible own, alien and empty planets; unknown planet stays unavailable', () => {
  const state=fixture();
  for (const id of ['s1p1','s1p2','s1p3']) assert.equal(planetInspection(state,id)?.planet.id,id);
  assert.equal(planetInspection(state,'s99p99'),null);
  assert.equal(planetInspection(null,'s1p1'),null);
  assert.equal(planetDetailsHtml(state,'s99p99'),'');
  assert.equal(planetInspection(state,'s1p1').own,true);
  assert.equal(planetInspection(state,'s1p1').currentOwn,true);
  assert.equal(planetInspection(state,'s1p2').own,false);
  assert.equal(planetInspection(state,'s1p3').own,false);
});

test('latest genuine scout report wins by arrival timestamp, irrespective of report array order', () => {
  const state=fixture(), newer=structuredClone(state.reports[0]);
  newer.id='newer';newer.at=250;newer.text='Nowszy zwiad';newer.planet_scout.scouted_at=250;
  state.reports=[state.reports[0],{id:'battle',at:900,title:'Raport bitwy',text:'Nowsza bitwa'},newer];
  const info=planetInspection(state,'s1p2');
  assert.equal(info.report.id,'newer');
  assert.equal(info.snapshot.scouted_at,250);
  assert.equal(info.swarm,newer.scout);
});

test('a more recent battle/map observation cannot replace the historical scout payload', () => {
  const state=fixture();
  state.reports.unshift({id:'battle',at:900,title:'Raport bitwy',text:'Nie jest raportem zwiadu'});
  const info=planetInspection(state,'s1p2');
  assert.equal(info.report.id,'r1');
  assert.equal(info.snapshot.resources.metal,12345);
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Prawdziwy raport zwiadu/);
  assert.match(markup,/Historyczna fregata/);
  assert.doesNotMatch(markup,/Nowa migawka|987[\s\u00a0\u202f]*654|Nie jest raportem zwiadu/);
});

test('legacy Swarm-only scout reports match their planet and provide usable snapshots', () => {
  const state=fixture();
  const report={id:'legacy',at:500,title:'Stary zwiad',text:'Raport starego klienta',scout:{id:'s1p2',scouted_at:500,resources:{metal:42},swarm_units:[{key:'frigate',name:'Stara fregata',count:2}]}};
  state.reports=[report];
  const info=planetInspection(state,'s1p2');
  assert.equal(info.report,report);assert.equal(info.snapshot,report.scout);assert.equal(info.swarm,report.scout);
  assert.match(planetDetailsHtml(state,'s1p2'),/Raport starego klienta/);
});

test('when the report has expired, known map intelligence remains available without inventing a report', () => {
  const state=fixture();state.reports=[];
  const planet=state.galaxy[0].planets[1], info=planetInspection(state,'s1p2');
  assert.equal(info.report,null);assert.equal(info.snapshot,planet.planet_scout);assert.equal(info.swarm,planet);
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Nowa migawka/);
  assert.doesNotMatch(markup,/Prawdziwy raport zwiadu|Historyczna fregata/);
});

test('legacy map-only Swarm intelligence keeps its recorded resources after reports have expired', () => {
  const state=fixture(), planet=state.galaxy[0].planets[1];
  state.reports=[];delete planet.planet_scout;
  planet.resources={metal:45678};planet.swarm_units=[{key:'frigate',name:'Dawna fregata',count:4}];
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Dawna fregata/);assert.match(markup,/45[\s\u00a0\u202f]*678/);
});

test('legacy Swarm building descriptions remain visible when generic scouting building lists are missing', () => {
  const state=fixture(), planet=state.galaxy[0].planets[1];
  state.reports=[];delete planet.planet_scout;
  planet.swarm_buildings=[{key:'shipyard',name:'Dawna stocznia Roju',level:6}];
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Dawna stocznia Roju/);assert.match(markup,/Poziom 6/);
});

test('map-only recorded observation is described as known observation without implying a genuine scout report', () => {
  const state=fixture(), planet=state.galaxy[0].planets[1];
  state.reports=[];
  planet.planet_scout={id:'s1p2',scouted_at:300,resources:{metal:987654}};
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Ostatnio poznany stan/);
  assert.doesNotMatch(markup,/Ostatni raport zwiadu|Dane z chwili zwiadu/);
});

test('observed identity without scout hides resource/unit quantities instead of substituting zeros', () => {
  const state=fixture(), planet=state.galaxy[0].planets[1];
  state.reports=[];delete planet.planet_scout;planet.has_scout=false;delete planet.resources;
  const info=planetInspection(state,'s1p2');
  assert.equal(info.snapshot,null);assert.equal(info.swarm,null);
  const markup=planetDetailsHtml(state,'s1p2');
  assert.doesNotMatch(markup,/NaN|undefined|987[\s\u00a0\u202f]*654|Historyczna fregata/);
  assert.match(markup,/zwiad|Zwiad/);
});

test('player-controlled names and report text are escaped before insertion into HTML', () => {
  const state=fixture();
  state.galaxy[0].name='System <script>alert(1)</script>';
  state.galaxy[0].planets[1].name='Planet <img src=x onerror="alert(1)"> & "quote"';
  state.galaxy[0].planets[1].owner_name='Empire <svg onload=alert(1)>';
  state.reports[0].title='Scout <script>evil()</script>';
  state.reports[0].text='Text <img onerror=evil()> & unsafe';
  const markup=planetDetailsHtml(state,'s1p2');
  assert.doesNotMatch(markup,/<script>|<img onerror|<svg onload|<img src=x/);
  assert.match(markup,/&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.match(markup,/Text &lt;img onerror=evil\(\)&gt; &amp; unsafe/);
});

test('limited environment disclosure does not fabricate physical statistics', () => {
  const state=fixture(), markup=planetDetailsHtml(state,'s1p3');
  assert.match(markup,/Organiczna/);
  assert.doesNotMatch(markup,/NaN|undefined|0\s*km|0\s*AU|0\s*°C/);
});

test('actions keep the existing colony-opening and mission semantics', () => {
  const state=fixture();
  assert.match(planetDetailsHtml(state,'s1p1'),/data-planet="s1p1"/);
  assert.match(planetDetailsHtml(state,'s1p2'),/data-target="s1p2"/);
  assert.match(planetDetailsHtml(state,'s1p2'),/data-mission="scout"/);
  assert.match(planetDetailsHtml(state,'s1p3'),/data-target="s1p3"/);
  assert.match(planetDetailsHtml(state,'s1p3'),/data-mission="colonize"/);
});

test('a liberated planet keeps its historical scout report and offers colonization from the known map state', () => {
  const state=fixture(), planet=state.galaxy[0].planets[1];
  planet.owner_type='empty';planet.owner_id='';planet.owner_name='';planet.has_scout=false;
  const info=planetInspection(state,'s1p2');
  assert.equal(info.report.id,'r1');assert.equal(info.snapshot.owner_id,'khar');
  const markup=planetDetailsHtml(state,'s1p2');
  assert.match(markup,/Prawdziwy raport zwiadu/);assert.match(markup,/data-mission="colonize"/);
});

test('another own colony does not borrow live ship counts/resources from the active colony', () => {
  const state=fixture(), planet={id:'s1p4',name:'Second',owner_id:'p1',owner_type:'player',visibility:'own',environment:{type_name:'Lodowa'}};
  state.own_planets.push(planet);state.galaxy[0].planets.push(planet);
  const info=planetInspection(state,'s1p4');
  assert.equal(info.own,true);assert.equal(info.currentOwn,false);
  const markup=planetDetailsHtml(state,'s1p4');
  assert.match(markup,/data-planet="s1p4"/);assert.doesNotMatch(markup,/6[\s\u00a0\u202f]*789|Zwiadowca/);
});

test('reading details does not mutate the delivered server snapshot', () => {
  const state=fixture(), before=JSON.stringify(state);
  planetInspection(state,'s1p2');planetDetailsHtml(state,'s1p2');
  assert.equal(JSON.stringify(state),before);
});
