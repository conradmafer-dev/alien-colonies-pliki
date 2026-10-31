import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {galaxyLayout,galaxyArtLayout,orbitRadii,galaxyConnections,hasRingTopology} from '../galaxy-map.js';

const systems=JSON.parse(readFileSync(new URL('./fixtures/six-rings99.json',import.meta.url),'utf8')).systems;
const profiles=JSON.parse(readFileSync(new URL('./fixtures/galaxy-art100.json',import.meta.url),'utf8'));

test('six rings have155 systems,50 new outer systems and180 undirected lanes',()=>{
  assert(hasRingTopology(systems));
  assert.equal(systems.length,155);
  assert.equal(systems.filter(s=>s.ring_index===5).length,50);
  assert.equal(new Set(systems.map(s=>s.ring_index)).size,6);
  assert.equal(galaxyConnections(systems).length,180);
});

for(const [width,height] of [[360,500],[720,640],[960,640],[1440,720]]) {
  test(`orbit and artwork geometry stay aligned at${width}x${height}`,()=>{
    const {rx,ry}=orbitRadii(width,height);
    assert(Math.abs(ry/rx-.60)<1e-12);
    const points=galaxyLayout(systems,width,height);
    for(const [name,profile] of Object.entries(profiles)) {
      const art=galaxyArtLayout(3840,2560,width,height,`/assets/art/galaxies/${name}.3840.fixture.webp`);
      assert(Math.abs(art.left+art.width*profile.core[0]-width/2)<1e-8);
      assert(Math.abs(art.top+art.height*profile.core[1]-height/2)<1e-8);
      for(const [i,point] of points.entries()) {
        assert(point.x>art.left+16 && point.x<art.left+art.width-16,name+' marker fits image horizontally');
        assert(point.y>art.top+16 && point.y<art.top+art.height-16,name+' marker fits image vertically');
        if(['void','eclipse'].includes(name) && systems[i].ring_index===4) {
          const horizon=profile.dark_horizon_radius_pixels*art.width/3840;
          const clearance=Math.hypot(point.x-width/2,point.y-height/2)-horizon;
          assert(clearance>2,name+' innermost system centre outside horizon');
          if(name==='void')assert(clearance*4.5>22,'Void44px system glyph clears horizon at normal focus zoom');
        }
      }
    }
  });
}
