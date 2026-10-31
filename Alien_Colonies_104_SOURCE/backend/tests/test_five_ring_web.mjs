import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {galaxyLayout, hasRingTopology, galaxyConnections, shortestSystemRoute, galaxyArtLayout, GALAXY_CORES, orbitRadii} from '../web/play/galaxy-map.js';

const fixture = JSON.parse(readFileSync(process.env.AC_FIVE_RING_FIXTURE));
test('optical cores of all six galaxy textures align with the orbital centre', () => {
  for (const name of Object.keys(GALAXY_CORES)) {
    for (const [width, height] of [[340,475], [720,530], [800,360]]) {
      const art = galaxyArtLayout(1536,1024,width,height,'/assets/art/galaxies/'+name+'.1280.webp');
      assert.ok(Math.abs(art.left + art.width * art.focalX - width / 2) < .001);
      assert.ok(Math.abs(art.top + art.height * art.focalY - height / 2) < .001);
      const {rx,ry} = orbitRadii(width,height);
      assert.ok(art.width >= rx * 2 && art.height >= ry * 2);
    }
  }
  assert.equal(galaxyArtLayout(0,0,300,500),null);
});
test('new perimeter and central routes match server costs, ties and wrapped orbits', () => {
  for (const expected of fixture.routes) {
    const actual = shortestSystemRoute(fixture.systems, expected.origin, expected.target);
    assert.deepEqual(actual.system_ids, expected.system_ids);
    assert.deepEqual(actual.segments, expected.segments);
    assert.equal(actual.network_distance, expected.distance);
  }
});
test('five distinct ellipses fit both phone orientations and desktop', () => {
  assert.equal(hasRingTopology(fixture.systems), true);
  for (const [width, height] of [[340, 475], [720, 530], [800, 360]]) {
    const points = galaxyLayout(fixture.systems, width, height);
    assert.equal(new Set(points.map(p => p.x + ':' + p.y)).size, fixture.systems.length);
    assert.ok(points.every(p => p.x > 20 && p.x < width - 20 && p.y > 20 && p.y < height - 20));
    const tops = new Map(fixture.systems.filter(s => s.ring_order === 0).map(s => [s.ring_index, points[fixture.systems.indexOf(s)].y]));
    assert.ok(tops.get(3) < tops.get(0) && tops.get(0) < tops.get(1)
      && tops.get(1) < tops.get(2) && tops.get(2) < tops.get(4) && tops.get(4) < height / 2);
  }
  const edges = galaxyConnections(fixture.systems);
  assert.equal(edges.filter(e => e.kind === 'orbit').length, fixture.systems.length);
  assert.equal(edges.filter(e => e.kind === 'bridge').length, 25);
});

