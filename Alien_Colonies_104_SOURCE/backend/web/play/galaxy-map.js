import {mountFleetOverlay} from './fleet-map-overlay.js?v=103';
import { t, text, html, getLanguage, getLocale, LANGUAGES, setLanguage } from './i18n.js?v=0111';
// Ring geometry and connections come from the server. Legacy worlds retain the
// original one-ellipse view; map estimates never determine flight cost or time.
export const GALAXY_CORES = {"aurora":[0.49505208333333334,0.465234375],"nexus":[0.5002604166666667,0.500390625],"omega":[0.5013020833333334,0.501171875],"zephyr":[0.49947916666666664,0.498828125],"eclipse":[0.5024660011574074,0.4961310040509259],"void":[0.5000341728711029,0.499450871044672]};
export function galaxyArtLayout(sourceWidth, sourceHeight, width, height, source = '', scale = 1.65) {
  if (!(sourceWidth > 0 && sourceHeight > 0 && width > 0 && height > 0)) return null;
  const name = Object.keys(GALAXY_CORES).find(key => source.includes('/' + key + '.'));
  const [fx, fy] = GALAXY_CORES[name] || [.5, .5];
  const {rx,ry} = orbitRadii(width,height);
  const fit = Math.min(rx * 2.2 / sourceWidth, ry * 2 / sourceHeight) * scale;
  const imageWidth = sourceWidth * fit, imageHeight = sourceHeight * fit;
  return {width:imageWidth, height:imageHeight, left:width / 2 - imageWidth * fx,
    top:height / 2 - imageHeight * fy, focalX:fx, focalY:fy};
}

export const sortSystems = (systems) => [...systems].sort((a, b) => String(a.id).localeCompare(String(b.id), 'en', {numeric:true}));

export const hasRingTopology = systems => systems.length > 0 && systems.every(system =>
  Number.isInteger(system.ring_index) && Number.isInteger(system.ring_order)
  && Number.isInteger(system.ring_size) && system.ring_size > 0
  && system.ring_order >= 0 && system.ring_order < system.ring_size
  && Number(system.ring_radius) > 0 && Number(system.ring_radius) <= 1
  && Array.isArray(system.connections));

export function galaxyLayout(systems, width, height) {
  if (!hasRingTopology(systems)) return ellipseLayout(systems.length, width, height);
  const rings = new Map();
  return systems.map(system => {
    if (!rings.has(system.ring_size)) rings.set(system.ring_size,ellipseLayout(system.ring_size,width,height));
    const point = rings.get(system.ring_size)[system.ring_order];
    return {x:width / 2 + (point.x - width / 2) * system.ring_radius,
      y:height / 2 + (point.y - height / 2) * system.ring_radius};
  });
}

export function galaxyConnections(systems) {
  const ids = new Set(systems.map(system => system.id)), seen = new Set(), edges = [];
  if (!hasRingTopology(systems)) return edges;
  for (const system of systems) for (const connection of system.connections) {
    const to = connection.system_id;
    if (!ids.has(to) || to === system.id || !['orbit','bridge'].includes(connection.kind) || !(Number(connection.distance) > 0)) continue;
    const key = [system.id, to].sort().join(':');
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({from_system_id:system.id,to_system_id:to,kind:connection.kind,distance:Number(connection.distance)});
  }
  return edges;
}

// Matches server Dijkstra: numeric system ID resolves equal-distance queue ties,
// sorted neighbours and strict improvement preserve the same predecessor.
export function shortestSystemRoute(systems, originId, targetId) {
  const byId = new Map(systems.map(system => [system.id, system]));
  if (!hasRingTopology(systems) || !byId.has(originId) || !byId.has(targetId)) return null;
  const compareId = (a,b) => String(a).localeCompare(String(b),'en',{numeric:true});
  const distances = new Map([[originId,0]]), previous = new Map(), queue = [{id:originId,distance:0}];
  while (queue.length) {
    queue.sort((a,b) => a.distance - b.distance || compareId(a.id,b.id));
    const current = queue.shift();
    if (current.distance !== distances.get(current.id)) continue;
    if (current.id === targetId) break;
    const connections = [...(byId.get(current.id).connections || [])].sort((a,b) => compareId(a.system_id,b.system_id));
    for (const edge of connections) {
      if (!byId.has(edge.system_id) || !['orbit','bridge'].includes(edge.kind) || !(Number(edge.distance) > 0)) continue;
      const distance = Math.round((current.distance + Number(edge.distance)) * 1e8) / 1e8;
      if (distance >= (distances.get(edge.system_id) ?? Infinity)) continue;
      distances.set(edge.system_id,distance);
      previous.set(edge.system_id,{from_system_id:current.id,to_system_id:edge.system_id,kind:edge.kind,distance:Number(edge.distance)});
      queue.push({id:edge.system_id,distance});
    }
  }
  if (!distances.has(targetId)) return null;
  const segments = [], ids = [targetId];
  for (let current = targetId; current !== originId;) {
    const edge = previous.get(current);
    if (!edge) return null;
    segments.unshift(edge); current = edge.from_system_id; ids.unshift(current);
  }
  return {system_ids:ids,segments,network_distance:distances.get(targetId)};
}

export function systemStatus(system, playerId) {
  const planets = system.planets || [];
  if (planets.some((planet) => planet.owner_id === playerId)) return 'own';
  if (system.visibility === 'unknown') return 'unknown';
  if (planets.some((planet) => planet.owner_id === 'khar')) return 'swarm';
  if (planets.some((planet) => planet.owner_type === 'player')) return 'inhabited';
  return 'known';
}

export function ellipseLayout(count, width, height) {
  if (count < 1) return [];
  const {rx,ry} = orbitRadii(width,height);
  // Equal arc-length spacing avoids bunching buttons at the narrow ends of an ellipse.
  const samples = 960;
  const points = [];
  let total = 0;
  for (let step = 0; step <= samples; step++) {
    const angle = -Math.PI / 2 + step / samples * Math.PI * 2;
    const x = Math.cos(angle) * rx, y = Math.sin(angle) * ry;
    if (step) total += Math.hypot(x - points[step - 1].x, y - points[step - 1].y);
    points.push({x, y, distance:total});
  }
  let index = 1;
  return Array.from({length:count}, (_, order) => {
    const target = order / count * total;
    while (index < points.length - 1 && points[index].distance < target) index++;
    const a = points[index - 1], b = points[index];
    const ratio = (target - a.distance) / (b.distance - a.distance || 1);
    return {x:width / 2 + a.x + (b.x - a.x) * ratio,
      y:height / 2 + a.y + (b.y - a.y) * ratio};
  });
}

export function orbitRadii(width,height) {
  // One tilted galactic disk in every viewport, matching Android's0.60 ellipse.
  const rx = Math.min(width * (width < 500 ? .39 : .41), height * .43 / .60);
  return {rx,ry:rx * .60};
}

export function mountGalaxyMap(viewport, view, controls, {systems = [], route = null, fleets = [], now = () => Date.now()/1000, galaxyId = ''} = {}) {
  const abort = new AbortController();
  const signal = abort.signal;
  const plane = viewport.querySelector('.galaxy-plane');
  const galaxyArt = plane.querySelector('.galaxy-map-art');
  const nodes = [...viewport.querySelectorAll('[data-system]')];
  const pointers = new Map();
  let width = 0, height = 0, gesture = null, suppressUntil = 0;
  let anchorSystemId = view.focusSystemId || view.anchorSystemId || '';
  let positions = new Map();
  const topology = hasRingTopology(systems);
  const expanded = topology && new Set(systems.map(system => system.ring_index)).size >= 5;
  const maxZoom = 6;
  const byId = new Map(systems.map(system => [system.id,system]));
  const edges = galaxyConnections(systems);
  const fleetOverlay = mountFleetOverlay(viewport,{systems,positions:()=>positions,now,fleets,galaxyId});
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.classList.add('galaxy-connections'); svg.setAttribute('aria-hidden','true');
  plane.querySelector('.galaxy-core')?.before(svg);
  viewport.classList.toggle('ring-map', topology);
  viewport.classList.toggle('expanded-ring-map', expanded);
  function pathFor(edge) {
    const a = positions.get(edge.from_system_id), b = positions.get(edge.to_system_id);
    if (!a || !b) return '';
    const from = byId.get(edge.from_system_id), to = byId.get(edge.to_system_id);
    if (edge.kind === 'orbit' && from?.ring_index === to?.ring_index && topology) {
      const radii = orbitRadii(width,height);
      const rx = radii.rx * from.ring_radius;
      const ry = radii.ry * from.ring_radius;
      const clockwise = (to.ring_order - from.ring_order + from.ring_size) % from.ring_size === 1;
      return `M${a.x},${a.y} A${rx},${ry} 0 0 ${clockwise ? 1 : 0} ${b.x},${b.y}`;
    }
    return `M${a.x},${a.y} L${b.x},${b.y}`;
  }
  function paintConnections() {
    svg.replaceChildren();
    const draw = (edge, highlighted = false) => {
      const d = pathFor(edge); if (!d) return;
      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('d',d); path.setAttribute('class',`map-connection ${edge.kind}${highlighted ? ' route' : ''}`);
      path.setAttribute('vector-effect','non-scaling-stroke'); svg.append(path);
    };
    edges.forEach(edge => draw(edge));
    if (!route?.intergalactic && route?.travel_mode !== 'tunnel') (route?.segments || []).forEach(edge => draw(edge,true));
  }
  const clamp = () => {
    view.scale = Math.min(maxZoom, Math.max(1, Number(view.scale) || 1));
    let limitX = width * (view.scale - 1) / 2;
    let limitY = height * (view.scale - 1) / 2;
    // Every system can reach the centre, including those on the outer ring.
    if (view.scale > 1) for (const point of positions.values()) {
      limitX = Math.max(limitX, Math.abs(point.x - width / 2) * view.scale);
      limitY = Math.max(limitY, Math.abs(point.y - height / 2) * view.scale);
    }
    view.x = Math.max(-limitX, Math.min(limitX, Number(view.x) || 0));
    view.y = Math.max(-limitY, Math.min(limitY, Number(view.y) || 0));
  };
  function clearAnchor() {
    anchorSystemId = '';
    delete view.anchorSystemId;
    delete view.focusSystemId;
  }
  function paint() {
    clamp();
    fleetOverlay.paint(view);
    viewport.style.touchAction = view.scale > 1.01 ? 'none' : 'pan-y';
    viewport.classList.toggle('map-magnified', view.scale >= 1.2);
    plane.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
    // Points stay the same legible/tappable size as the galaxy is magnified.
    plane.style.setProperty('--point-scale', String(1 / view.scale));
    if (controls) {
      controls.querySelector('[data-map-scale]').textContent = `${Math.round(view.scale * 100)}%`;
      controls.querySelector('[data-map-zoom="out"]').disabled = view.scale <= 1;
      controls.querySelector('[data-map-zoom="in"]').disabled = view.scale >= maxZoom;
    }
  }
  function zoom(scale, clientX, clientY) {
    clearAnchor();
    const rect = viewport.getBoundingClientRect();
    const ax = clientX == null ? 0 : clientX - rect.left - width / 2;
    const ay = clientY == null ? 0 : clientY - rect.top - height / 2;
    const next = Math.min(maxZoom, Math.max(1, scale));
    const ratio = next / view.scale;
    view.x = ax - (ax - view.x) * ratio;
    view.y = ay - (ay - view.y) * ratio;
    view.scale = next;
    paint();
  }
  function resize() {
    width = viewport.clientWidth;
    height = viewport.clientHeight;
    const artLayout = galaxyArt && galaxyArtLayout(galaxyArt.naturalWidth, galaxyArt.naturalHeight, width, height, galaxyArt.currentSrc || galaxyArt.src, expanded ? 1.65 : 1);
    if (artLayout) Object.assign(galaxyArt.style, {inset:'auto', transform:'none', width:artLayout.width+'px', height:artLayout.height+'px', left:artLayout.left+'px', top:artLayout.top+'px'});
    const ordered = nodes.map(node => byId.get(node.dataset.system) || {id:node.dataset.system});
    positions = new Map();
    galaxyLayout(ordered, width, height).forEach((point, index) => {
      const node = nodes[index];
      positions.set(node.dataset.system,point);
      node.style.left = `${point.x}px`;
      node.style.top = `${point.y}px`;
      node.dataset.labelSide = point.x < width * .22 ? 'left' : point.x > width * .78 ? 'right' : 'center';
    });
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    viewport.classList.toggle('narrow-map', width < 500);
    paintConnections();
    fleetOverlay.layout(width,height,view);
    const focus = positions.get(anchorSystemId);
    if (focus && width > 0 && height > 0) {
      if (view.focusSystemId) view.scale = maxZoom;
      view.x = (width / 2 - focus.x) * view.scale;
      view.y = (height / 2 - focus.y) * view.scale;
      // Keep centring through layout/orientation changes until manual navigation.
      // The local view retains the anchor when polling remounts the map.
      view.anchorSystemId = anchorSystemId;
      delete view.focusSystemId;
    }
    paint();
  }
  galaxyArt?.addEventListener('load', resize, {signal});
  const observer = new ResizeObserver(resize);
  observer.observe(viewport);
  resize();
  controls?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-map-zoom]');
    if (!button || button.disabled) return;
    if (button.dataset.mapZoom === 'reset') { clearAnchor(); view.scale = 1; view.x = view.y = 0; paint(); }
    else zoom(view.scale * (button.dataset.mapZoom === 'in' ? 1.25 : .8));
  }, {signal});
  viewport.addEventListener('wheel', (event) => {
    // Preserve browser page zoom when Ctrl is held.
    if (event.ctrlKey) return;
    event.preventDefault();
    zoom(view.scale * Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * .003), event.clientX, event.clientY);
  }, {passive:false, signal});
  viewport.addEventListener('keydown', (event) => {
    const node = event.target.closest('[data-system]');
    if (node && ['ArrowRight','ArrowDown','ArrowLeft','ArrowUp'].includes(event.key)) {
      event.preventDefault();
      const direction = ['ArrowRight','ArrowDown'].includes(event.key) ? 1 : -1;
      const following = nodes[(nodes.indexOf(node) + direction + nodes.length) % nodes.length];
      following.focus({preventScroll:true});
      // Restore the full map so keyboard focus never disappears beyond the viewport.
      clearAnchor();
      view.scale = 1; view.x = view.y = 0; paint();
      return;
    }
    if (['+','=','-','0','Home'].includes(event.key)) {
      event.preventDefault();
      if (event.key === '0' || event.key === 'Home') { clearAnchor(); view.scale = 1; view.x = view.y = 0; paint(); }
      else zoom(view.scale * (event.key === '-' ? .8 : 1.25));
    }
  }, {signal});
  function beginGesture() {
    const values = [...pointers.values()];
    if (!values.length) { gesture = null; return; }
    const a = values[0], b = values[1];
    gesture = {x:b ? (a.x + b.x) / 2 : a.x, y:b ? (a.y + b.y) / 2 : a.y,
      distance:b ? Math.hypot(a.x - b.x, a.y - b.y) : 0,
      scale:view.scale, panX:view.x, panY:view.y, moved:false};
  }
  viewport.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 && event.pointerType === 'mouse') return;
    pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
    beginGesture();
    if (pointers.size > 1) suppressUntil = performance.now() + 500;
  }, {signal});
  viewport.addEventListener('pointermove', (event) => {
    if (!pointers.has(event.pointerId) || !gesture) return;
    pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
    const [a,b] = [...pointers.values()];
    const x = b ? (a.x + b.x) / 2 : a.x, y = b ? (a.y + b.y) / 2 : a.y;
    if (!gesture.moved && !b && Math.hypot(x - gesture.x, y - gesture.y) < 7) return;
    if (event.pointerType === 'touch' && !b && view.scale <= 1.01) return;
    clearAnchor();
    gesture.moved = true;
    try { viewport.setPointerCapture(event.pointerId); } catch { /* Released pointer. */ }
    viewport.classList.add('dragging');
    suppressUntil = performance.now() + 500;
    if (b && gesture.distance > 0) {
      const rect = viewport.getBoundingClientRect();
      const next = Math.min(maxZoom, Math.max(1, gesture.scale * Math.hypot(a.x - b.x, a.y - b.y) / gesture.distance));
      const ax = gesture.x - rect.left - width / 2, ay = gesture.y - rect.top - height / 2;
      view.x = ax - (ax - gesture.panX) * next / gesture.scale + x - gesture.x;
      view.y = ay - (ay - gesture.panY) * next / gesture.scale + y - gesture.y;
      view.scale = next;
    } else {
      view.x = gesture.panX + x - gesture.x;
      view.y = gesture.panY + y - gesture.y;
    }
    paint();
  }, {signal});
  function endPointer(event) {
    if (!pointers.has(event.pointerId)) return;
    if (gesture?.moved || pointers.size > 1) suppressUntil = performance.now() + 350;
    pointers.delete(event.pointerId);
    viewport.classList.remove('dragging');
    beginGesture();
  }
  window.addEventListener('pointerup', endPointer, {signal});
  window.addEventListener('pointercancel', endPointer, {signal});
  viewport.addEventListener('click', (event) => {
    if (performance.now() < suppressUntil) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, {capture:true, signal});
  return {destroy:() => { abort.abort(); observer.disconnect(); svg.remove(); fleetOverlay.destroy(); },
    isInteracting:() => pointers.size > 0,
    setFleets(next) { fleetOverlay.update(next); },
    setRoute(next) { route = next; paintConnections(); }};
}



