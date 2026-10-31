import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {researchEdges, researchLayout, mountResearchTree} from '../research-tree.js';

// Exercise the current server catalog, including racial and capital-ship research.
// The temporary world is entirely local and never touches the production database.
const serverRoot = fileURLToPath(new URL('../../../', import.meta.url));
const fixture = spawnSync('python', ['-c', `
import json, pathlib, tempfile
import app
from i18n import language_scope
with tempfile.TemporaryDirectory() as tmp:
    world = app.World(str(pathlib.Path(tmp) / 'research-layout.sqlite3'), 1, now=1800000000)
    try:
        catalogs = {}
        for race in app.RACES:
            account = world.register('layout_' + race, 'LocalLayout-94751')
            owner = account['state']['player']['id']
            planet_id = account['state']['planet_id']
            world.action(owner, {'type': 'choose_race', 'race_id': race, 'planet_id': planet_id})
            with language_scope('pl'):
                catalogs[race] = world._catalog(owner, world.data['planets'][planet_id])['research']
        print(json.dumps(catalogs))
    finally:
        world.close()
`], {cwd: serverRoot, encoding: 'utf8', timeout: 30000});
assert.equal(fixture.status, 0, fixture.stderr || fixture.stdout);
const catalogs = JSON.parse(fixture.stdout);

function assertLayout(graph, expectedKeys) {
  assert.equal(graph.rows, 3);
  assert.deepEqual([...graph.nodes.map(node => node.key)].sort(), [...expectedKeys].sort());
  assert.equal(new Set(graph.nodes.map(node => `${node.row}:${node.column}`)).size, graph.nodes.length,
    'every research occupies a distinct card position');
  const nodes = new Map(graph.nodes.map(node => [node.key, node]));
  for (const node of graph.nodes) {
    assert.ok(Number.isInteger(node.row) && node.row >= 0 && node.row < 3, `${node.key}: row ${node.row}`);
    assert.ok(Number.isInteger(node.column) && node.column >= 0 && node.column < graph.columns);
  }
  for (const edge of graph.edges) {
    assert.ok(nodes.get(edge.from).column < nodes.get(edge.to).column,
      `${edge.from} must precede ${edge.to} from left to right`);
    assert.ok(nodes.get(edge.from).depth < nodes.get(edge.to).depth);
  }
}

test('all three real race catalogs fit three rows and place every child after every prerequisite', () => {
  assert.deepEqual(Object.keys(catalogs).sort(), ['automatons', 'symbionts', 'zetans']);
  for (const [race, items] of Object.entries(catalogs)) {
    assert.equal(items.length, 25, `${race}: complete player research catalog`);
    const graph = researchLayout(items);
    assertLayout(graph, items.map(item => item.key));
    assert.equal(graph.edges.length, items.reduce((sum, item) => sum + item.requirements.filter(req => req.group === 'research').length, 0));
    assert.equal(new Set(graph.nodes.map(node => node.row)).size, 3);
    assert.ok(graph.nodes.find(node => node.key === 'titan_core').column > graph.nodes.find(node => node.key === 'dyson_design').column);
  }
});

const research = (key, parents = [], tree = {row: 0, column: 0}) => ({key, tree,
  requirements: parents.map(key => ({group: 'research', key, level: 1, met: false}))});

test('wide levels overflow into additional columns without overlapping or creating a fourth row', () => {
  const roots = Array.from({length: 11}, (_, i) => research(`root${i}`));
  const children = Array.from({length: 8}, (_, i) => research(`child${i}`, roots.map(item => item.key)));
  const items = [...roots, ...children, research('end', children.map(item => item.key))];
  const graph = researchLayout(items);
  assertLayout(graph, items.map(item => item.key));
  assert.ok(graph.columns >= 8);
  const positions = new Map(graph.nodes.map(node => [node.key, node.column]));
  assert.ok(Math.min(...children.map(item => positions.get(item.key))) > Math.max(...roots.map(item => positions.get(item.key))));
});

test('actual prerequisites override conflicting server coordinates and remain stable when input order changes', () => {
  const items = [research('child', ['parent'], {row: 0, column: 2}),
    research('parent', ['root'], {row: 100, column: 1}), research('root', [], {row: 1000, column: 0})];
  const graph = researchLayout(items);
  assertLayout(graph, items.map(item => item.key));
  const positions = graph => graph.nodes.map(({key, row, column, depth}) => ({key, row, column, depth}));
  assert.deepEqual(positions(graph), positions(researchLayout([...items].reverse())));
});

test('cycles and self-dependencies fail explicitly instead of hanging or losing research', () => {
  assert.throws(() => researchLayout([research('a', ['b']), research('b', ['a'])]), /Cyclic/);
  assert.throws(() => researchLayout([research('a', ['a'])]), /Cyclic/);
});

test('graph edges exclude building requirements and references outside the visible research catalog', () => {
  const items = [research('root'), {...research('child', ['root', 'absent']), requirements: [
    {group: 'research', key: 'root', level: 4, met: true},
    {group: 'research', key: 'absent', level: 1, met: false},
    {group: 'buildings', key: 'root', level: 7, met: false},
  ]}];
  assert.deepEqual(researchEdges(items), [{from: 'root', to: 'child', level: 4, met: true}]);
  assertLayout(researchLayout(items), items.map(item => item.key));
  assert.deepEqual(researchLayout([]), {nodes: [], edges: [], rows: 3, columns: 0});
});

class Element {
  constructor(rect = {}) { this.rect = rect; this.dataset = {}; this.children = []; this.attrs = {}; this.listeners = new Map(); this.classList = {add() {}, toggle() {}}; }
  getBoundingClientRect() { return this.rect; }
  setAttribute(key, value) { this.attrs[key] = value; }
  replaceChildren() { this.children = []; }
  append(node) { this.children.push(node); }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  removeEventListener(name) { this.listeners.delete(name); }
}
function pathPoints(d) {
  const tokens = d.match(/[MHV]|-?\d+(?:\.\d+)?/g);
  const points = [];
  let x = 0, y = 0;
  while (tokens.length) {
    const command = tokens.shift();
    if (command === 'M') { x = Number(tokens.shift()); y = Number(tokens.shift()); }
    else if (command === 'H') x = Number(tokens.shift());
    else if (command === 'V') y = Number(tokens.shift());
    else throw new Error(`Unexpected SVG command ${command}`);
    points.push({x, y});
  }
  return points;
}
function segmentCrossesCard(a, b, card) {
  if (a.y === b.y) return a.y > card.top && a.y < card.bottom && Math.max(a.x, b.x) > card.left && Math.min(a.x, b.x) < card.right;
  assert.equal(a.x, b.x, 'connection segments must be horizontal or vertical');
  return a.x > card.left && a.x < card.right && Math.max(a.y, b.y) > card.top && Math.min(a.y, b.y) < card.bottom;
}

test('real-catalog connection routes meet card edges and avoid unrelated cards at desktop and mobile geometry', () => {
  // This is a deterministic geometry test, not a claim of browser rendering QA.
  const saved = Object.fromEntries(['document', 'ResizeObserver', 'requestAnimationFrame', 'cancelAnimationFrame', 'getComputedStyle'].map(key => [key, globalThis[key]]));
  try {
    let draw;
    globalThis.document = {createElementNS: () => new Element()};
    globalThis.ResizeObserver = class {observe() {} disconnect() {}};
    globalThis.requestAnimationFrame = callback => { draw = callback; return 1; };
    globalThis.cancelAnimationFrame = () => {};
    globalThis.getComputedStyle = () => ({rowGap: '30px'});
    for (const items of Object.values(catalogs)) for (const [width, height, padding] of [[190, 154, 22], [164, 155, 9]]) {
      const graph = researchLayout(items), gapX = 66, gapY = 30;
      const left = -450, top = 160; // Horizontal scroll and nonzero page offset.
      const canvas = new Element({left, top, width: graph.columns * (width + gapX) - gapX + padding * 2});
      canvas.scrollHeight = height * 3 + gapY * 2 + 38;
      const svg = new Element(), root = new Element();
      const nodes = graph.nodes.map(meta => {
        const x = padding + meta.column * (width + gapX), y = 14 + meta.row * (height + gapY);
        const node = new Element({left: left + x, right: left + x + width, top: top + y, bottom: top + y + height, width, height});
        node.dataset.research = meta.key;
        return node;
      });
      root.querySelector = name => name === '.tech-tree' ? canvas : svg;
      root.querySelectorAll = () => nodes;
      const byKey = new Map(nodes.map(node => [node.dataset.research, node]));
      const controller = mountResearchTree(root, graph);
      draw();
      assert.equal(svg.children.length, graph.edges.length);
      for (const edge of svg.children) {
        const points = pathPoints(edge.children[0].attrs.d);
        const source = byKey.get(edge.dataset.from).rect, target = byKey.get(edge.dataset.to).rect;
        assert.deepEqual(points[0], {x: source.right - left, y: source.top + source.height / 2 - top});
        assert.deepEqual(points.at(-1), {x: target.left - left, y: target.top + target.height / 2 - top});
        for (const node of nodes) {
          if ([edge.dataset.from, edge.dataset.to].includes(node.dataset.research)) continue;
          const r = node.rect, relative = {left: r.left - left, right: r.right - left, top: r.top - top, bottom: r.bottom - top};
          for (let i = 1; i < points.length; i++) assert.equal(segmentCrossesCard(points[i - 1], points[i], relative), false,
            `${edge.dataset.from} -> ${edge.dataset.to} crosses ${node.dataset.research}`);
        }
      }
      controller.destroy();
    }
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});
