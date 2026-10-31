import test, {beforeEach, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {mountCatalogCarousels} from '../catalog-carousel.js';

let observers, savedGlobals, reducedMotion;
beforeEach(() => {
  observers = [];
  reducedMotion = false;
  savedGlobals = {document: globalThis.document, ResizeObserver: globalThis.ResizeObserver};
  globalThis.document = {documentElement: {classList: {contains: name => name === 'reduce-motion' && reducedMotion}}};
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe(element) { this.element = element; }
    disconnect() { this.disconnected = true; }
  };
});
afterEach(() => {
  for (const [key, value] of Object.entries(savedGlobals)) {
    if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
  }
});

class Element {
  constructor(dataset = {}) { this.dataset = dataset; this.listeners = new Map(); }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name).add(callback);
  }
  removeEventListener(name, callback) { this.listeners.get(name)?.delete(callback); }
  fire(name, event = {}) { for (const callback of this.listeners.get(name) || []) callback(event); }
  listenerCount() { return [...this.listeners.values()].reduce((sum, listeners) => sum + listeners.size, 0); }
}
function carousel({key = 'ships', keys = ['scout', 'cargo', 'colonizer', 'frigate', 'cruiser', 'interceptor'], width = 300, step = 320, batches = {}} = {}) {
  const track = new Element({catalogCarousel: key}), section = new Element();
  track.clientWidth = width;
  track.scrollWidth = keys.length ? (keys.length - 1) * step + 300 : width;
  let scrollLeft = 0;
  Object.defineProperty(track, 'scrollLeft', {
    get: () => scrollLeft,
    set: value => { scrollLeft = Math.max(0, Math.min(Number(value), Math.max(0, track.scrollWidth - track.clientWidth))); },
  });
  track.getBoundingClientRect = () => ({left: 137});
  const cards = keys.map((key, index) => {
    const card = new Element({catalogCard: key});
    card.getBoundingClientRect = () => ({left: 137 + index * step - track.scrollLeft});
    return card;
  });
  const inputs = Object.entries(batches).map(([key, value]) => Object.assign(new Element({batch: key}), {value: String(value)}));
  const previous = Object.assign(new Element({carouselStep: '-1'}), {disabled: false});
  const next = Object.assign(new Element({carouselStep: '1'}), {disabled: false});
  for (const button of [previous, next]) button.closest = selector => selector === '[data-carousel-step]' ? button : null;
  section.querySelector = selector => selector.includes('"-1"') ? previous : next;
  track.closest = selector => selector === '[data-carousel-section]' ? section : null;
  track.querySelectorAll = selector => selector === '[data-catalog-card]' ? cards : selector === '[data-batch]' ? inputs : [];
  track.scrollCalls = [];
  track.scrollTo = options => { track.scrollCalls.push(options); track.scrollLeft = options.left; track.fire('scroll'); };
  const root = {querySelectorAll: () => [track]};
  return {root, track, section, cards, inputs, previous, next,
    scrollTo(left) { track.scrollLeft = left; track.fire('scroll'); },
    click(direction) { section.fire('click', {target: direction < 0 ? previous : next}); },
    input(key, value) { const input = inputs.find(input => input.dataset.batch === key); input.value = String(value); track.fire('input', {target: input}); return input; },
  };
}

test('polling destroy/remount preserves scroll and the offset inside the visible card', () => {
  const views = {}, first = carousel();
  const controller = mountCatalogCarousels(first.root, views);
  first.scrollTo(667);
  controller.destroy();
  assert.deepEqual(views.ships, {left: 667, anchor: 'colonizer', offset: 27, batches: {}});
  const second = carousel();
  const remounted = mountCatalogCarousels(second.root, views);
  assert.equal(second.track.scrollLeft, 667);
  assert.equal(second.previous.disabled, false);
  assert.equal(second.next.disabled, false);
  remounted.destroy();
});

test('the saved card remains the anchor when polling reorders cards or changes their width', () => {
  const views = {}, first = carousel();
  const controller = mountCatalogCarousels(first.root, views);
  first.scrollTo(667);
  controller.destroy();
  const second = carousel({keys: ['cruiser', 'colonizer', 'scout', 'frigate', 'cargo', 'interceptor'], step: 350});
  const remounted = mountCatalogCarousels(second.root, views);
  assert.equal(second.track.scrollLeft, 377, 'colonizer moved to the second card, keeping its offset');
  remounted.destroy();
  assert.equal(views.ships.anchor, 'colonizer');
  assert.equal(views.ships.offset, 27);
});

test('stored ship quantities are restored and onBatch recalculates the affected previews', () => {
  const views = {}, first = carousel({batches: {scout: 1, cargo: 1}});
  const controller = mountCatalogCarousels(first.root, views);
  first.input('scout', 7);
  first.input('cargo', 3);
  first.scrollTo(330);
  controller.destroy();
  const second = carousel({batches: {scout: 1, cargo: 1, titan: 1}}), previews = [];
  const remounted = mountCatalogCarousels(second.root, views, {onBatch: input => previews.push({key: input.dataset.batch, amount: Number(input.value)})});
  assert.deepEqual(previews, [{key: 'scout', amount: 7}, {key: 'cargo', amount: 3}]);
  assert.deepEqual(Object.fromEntries(second.inputs.map(input => [input.dataset.batch, input.value])), {scout: '7', cargo: '3', titan: '1'});
  assert.equal(second.track.scrollLeft, 330);
  remounted.destroy();
});

test('colony and catalog views are independent even when the previous controller is destroyed later', () => {
  const colonyA = {}, colonyB = {};
  const a = carousel({batches: {scout: 1}}), b = carousel({batches: {scout: 1}});
  const aController = mountCatalogCarousels(a.root, colonyA);
  a.scrollTo(650); a.input('scout', 9);
  const bController = mountCatalogCarousels(b.root, colonyB);
  assert.equal(b.track.scrollLeft, 0);
  assert.equal(b.inputs[0].value, '1');
  b.scrollTo(320); b.input('scout', 2);
  aController.destroy();
  assert.equal(colonyB.ships.left, 320);
  assert.equal(colonyB.ships.batches.scout, '2');
  const buildings = carousel({key: 'buildings'});
  const buildingsController = mountCatalogCarousels(buildings.root, colonyA);
  assert.equal(buildings.track.scrollLeft, 0, 'the ship anchor must not move the building catalog');
  buildings.scrollTo(960);
  buildingsController.destroy(); bController.destroy();
  assert.equal(colonyA.ships.left, 650);
  assert.equal(colonyA.buildings.left, 960);
  const returned = carousel({batches: {scout: 1}}), returnedController = mountCatalogCarousels(returned.root, colonyA);
  assert.equal(returned.track.scrollLeft, 650);
  assert.equal(returned.inputs[0].value, '9');
  returnedController.destroy();
});

test('arrows move to adjacent cards, respect both ends and use reduced-motion preferences', () => {
  const view = {}, mounted = carousel();
  const controller = mountCatalogCarousels(mounted.root, view);
  assert.equal(mounted.previous.disabled, true);
  assert.equal(mounted.next.disabled, false);
  mounted.click(-1);
  assert.equal(mounted.track.scrollCalls.length, 0);
  mounted.click(1);
  assert.deepEqual(mounted.track.scrollCalls.at(-1), {left: 320, behavior: 'smooth'});
  assert.equal(mounted.previous.disabled, false);
  reducedMotion = true;
  mounted.click(1);
  assert.deepEqual(mounted.track.scrollCalls.at(-1), {left: 640, behavior: 'instant'});
  mounted.scrollTo(10000);
  assert.equal(mounted.next.disabled, true);
  const count = mounted.track.scrollCalls.length;
  mounted.click(1);
  assert.equal(mounted.track.scrollCalls.length, count);
  mounted.click(-1);
  assert.equal(mounted.track.scrollLeft, 1280);
  controller.destroy();
});

test('resize updates controls, and cleanup removes observers and all listeners', () => {
  const views = {}, mounted = carousel({keys: ['scout', 'cargo']});
  const controller = mountCatalogCarousels(mounted.root, views);
  assert.equal(mounted.next.disabled, false);
  mounted.track.clientWidth = 1000;
  observers[0].callback();
  assert.equal(mounted.next.disabled, true, 'no next action when all cards fit');
  assert.equal(mounted.previous.disabled, true);
  controller.destroy();
  assert.equal(observers[0].disconnected, true);
  assert.equal(mounted.track.listenerCount(), 0);
  assert.equal(mounted.section.listenerCount(), 0);
  const snapshot = structuredClone(views);
  mounted.track.clientWidth = 300;
  mounted.scrollTo(100); mounted.click(1);
  assert.deepEqual(views, snapshot, 'detached elements cannot overwrite the saved view');
});

test('missing anchors fall back to the saved scroll position; empty catalogs remain safe', () => {
  const views = {ships: {anchor: 'removed', left: 345, offset: 17}};
  const mounted = carousel(), controller = mountCatalogCarousels(mounted.root, views);
  assert.equal(mounted.track.scrollLeft, 345);
  controller.destroy();
  const empty = carousel({keys: []}), emptyController = mountCatalogCarousels(empty.root, {});
  assert.equal(empty.previous.disabled, true);
  assert.equal(empty.next.disabled, true);
  empty.click(1);
  emptyController.destroy();
});


test('polling preserves independent vertical reading positions in the text, without moving art or controls', () => {
  const withTextBodies = () => {
    const mounted = carousel();
    mounted.bodies = mounted.cards.map(card => {
      const body = Object.assign(new Element(), {scrollTop:0});
      card.scrollTop = 0;
      card.querySelector = selector => selector === '[data-card-scroll]' ? body : null;
      return body;
    });
    return mounted;
  };
  const views = {}, first = withTextBodies();
  const controller = mountCatalogCarousels(first.root, views);
  first.bodies[0].scrollTop = 180;
  first.bodies[0].fire('scroll');
  first.bodies[1].scrollTop = 315;
  first.bodies[1].fire('scroll');
  first.scrollTo(320);
  controller.destroy();
  assert.deepEqual(views.ships.scrollTops, {scout:180,cargo:315});
  const second = withTextBodies();
  const restored = mountCatalogCarousels(second.root, views);
  assert.equal(second.bodies[0].scrollTop, 180);
  assert.equal(second.bodies[1].scrollTop, 315);
  assert.equal(second.bodies[2].scrollTop, 0);
  assert.equal(second.track.scrollLeft, 320);
  assert.ok(second.cards.every(card=>card.scrollTop===0), 'artwork and footer stay outside the scroller');
  const snapshot = structuredClone(views);
  first.bodies[0].scrollTop = 900;
  first.bodies[0].fire('scroll');
  assert.deepEqual(views, snapshot, 'detached cards cannot change live positions');
  restored.destroy();
  assert.ok(second.bodies.every(body=>body.listenerCount()===0));
});
