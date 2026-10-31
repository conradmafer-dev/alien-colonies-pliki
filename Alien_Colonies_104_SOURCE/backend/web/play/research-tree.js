import { t, text, html, getLanguage, getLocale, LANGUAGES, setLanguage } from './i18n.js?v=0111';
/** Research graph: positions follow server preferences; edges are real prerequisites.
 * DOM-free graph functions are also used by the regression tests.
 */
export function researchEdges(items = []) {
  const keys = new Set(items.map(item => item.key));
  return items.flatMap(item => (item.requirements || [])
    .filter(req => req.group === 'research' && keys.has(req.key))
    .map(req => ({from:req.key, to:item.key, level:Number(req.level), met:Boolean(req.met)})));
}

export function researchLayout(items = []) {
  // Match the Android three-row view: graph depth sets progression, while old
  // server coordinates only order peers and choose a preferred horizontal row.
  const unique = [...new Map(items.filter(item => item.key).map(item => [item.key,item])).values()];
  const edges = researchEdges(unique);
  const sorted = [...unique].sort((a,b) => (a.tree?.row || 0) - (b.tree?.row || 0)
    || (a.tree?.column || 0) - (b.tree?.column || 0) || a.key.localeCompare(b.key));
  const parents = new Map(sorted.map(item => [item.key,edges.filter(edge => edge.to === item.key)]));
  const depths = new Map(), pending = [...sorted];
  while (pending.length) {
    const i = pending.findIndex(item => parents.get(item.key).every(edge => depths.has(edge.from)));
    if (i < 0) throw new Error(t('Cyclic research prerequisites'));
    const item = pending.splice(i,1)[0];
    depths.set(item.key, Math.max(0,...parents.get(item.key).map(edge => depths.get(edge.from)+1)));
  }
  const placed = new Map();
  let columns = 0;
  for (let depth=0; depth<=Math.max(-1,...depths.values()); depth++) {
    const peers = sorted.filter(item => depths.get(item.key) === depth);
    const firstColumn = Math.max(columns,...peers.flatMap(item => parents.get(item.key).map(edge => placed.get(edge.from).column+1)));
    const occupied = new Set();
    for (const item of peers) {
      let column = firstColumn;
      const preferred = Math.min(2,Math.max(0,Number(item.tree?.column) || 0));
      let row = preferred;
      while (occupied.has(`${column}:${row}`)) {
        const free = [preferred,(preferred+1)%3,(preferred+2)%3].find(candidate => !occupied.has(`${column}:${candidate}`));
        if (free !== undefined) { row = free; break; }
        column++;
      }
      occupied.add(`${column}:${row}`);
      placed.set(item.key,{key:item.key,row,column,depth,item});
      columns = Math.max(columns,column+1);
    }
  }
  return {nodes:[...placed.values()], edges, rows:3, columns};
}

export function researchStatus(item, queue) {
  if (queue?.key === item.key) return 'active';
  if (Number(item.level) >= Number(item.max_level)) return 'complete';
  if (item.enabled) return 'ready';
  if (Number(item.level) > 0) return 'learned';
  return item.requirements_met ? 'waiting' : 'locked';
}

/** Horizontal orthogonal edges use the row gutters, never another card. */
export function mountResearchTree(root, graph, {view = {}, onView = () => {}} = {}) {
  if (!root) return {destroy(){}};
  const canvas = root.querySelector('.tech-tree');
  const svg = root.querySelector('.tech-links');
  const cards = [...root.querySelectorAll('[data-research-node]')];
  const nodes = new Map((cards.length ? cards : [...root.querySelectorAll('[data-research]')]).map(node => [node.dataset.researchNode || node.dataset.research,node]));
  const meta = new Map(graph.nodes.map(node => [node.key,node]));
  const NS = 'http://www.w3.org/2000/svg';
  let raf = 0, disposed = false;
  const draw = () => {
    if (disposed || !canvas || !svg) return;
    const origin = canvas.getBoundingClientRect();
    svg.setAttribute('viewBox',`0 0 ${origin.width} ${canvas.scrollHeight}`);
    svg.setAttribute('width',String(origin.width));
    svg.setAttribute('height',String(canvas.scrollHeight));
    svg.replaceChildren();
    const ordered = [...graph.edges].sort((a,b) => Number(a.met)-Number(b.met));
    for (const edge of ordered) {
      const source = nodes.get(edge.from), target = nodes.get(edge.to);
      if (!source || !target) continue;
      const a=source.getBoundingClientRect(), b=target.getBoundingClientRect();
      const ax=a.right-origin.left, ay=a.top+a.height/2-origin.top;
      const bx=b.left-origin.left, by=b.top+b.height/2-origin.top;
      const from=meta.get(edge.from), to=meta.get(edge.to);
      const neighbors = graph.edges.filter(e=>e.to===edge.to);
      const offset = neighbors.findIndex(e=>e.from===edge.from)*5;
      const exit = ax+16+offset, entry=bx-16-offset;
      let d;
      if (from.row === to.row && to.column === from.column+1) {
        d=`M ${ax} ${ay} H ${bx}`;
      } else {
        // A horizontal gutter between rows or the outside padding for row 0.
        const gutter = parseFloat(getComputedStyle(canvas).rowGap) || 30;
        const lane = to.row === 0 ? 7 : b.top-origin.top-gutter/2;
        d=`M ${ax} ${ay} H ${exit} V ${lane} H ${entry} V ${by} H ${bx}`;
      }
      const group=document.createElementNS(NS,'g');
      group.classList.add('tech-edge',edge.met?'met':'unmet');
      group.dataset.from=edge.from;group.dataset.to=edge.to;
      const path=document.createElementNS(NS,'path');
      path.setAttribute('d',d);group.append(path);
      const arrow=document.createElementNS(NS,'path');
      arrow.setAttribute('d',`M ${bx-5} ${by-3} L ${bx} ${by} L ${bx-5} ${by+3}`);
      group.append(arrow);
      svg.append(group);
    }
  };
  const schedule = () => {cancelAnimationFrame(raf);raf=requestAnimationFrame(draw);};
  const observer = new ResizeObserver(schedule);
  observer.observe(canvas);
  nodes.forEach(node=>observer.observe(node));
  const save=()=>onView({left:root.scrollLeft,top:root.scrollTop});
  root.scrollLeft=Number(view.left)||0;root.scrollTop=Number(view.top)||0;
  root.addEventListener('scroll',save,{passive:true});
  const highlight=event=>{
    const node=event.target.closest('[data-research]');
    svg.querySelectorAll('.tech-edge').forEach(edge=>edge.classList.toggle('highlighted',
      Boolean(node && (edge.dataset.from===node.dataset.research || edge.dataset.to===node.dataset.research))));
  };
  root.addEventListener('pointerover',highlight);root.addEventListener('focusin',highlight);
  schedule();
  return {destroy(){disposed=true;save();observer.disconnect();cancelAnimationFrame(raf);
    root.removeEventListener('scroll',save);root.removeEventListener('pointerover',highlight);root.removeEventListener('focusin',highlight);}};
}

