import { ART } from './art-manifest.js?v=103';

const escapeAttribute = (value = '') => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
export const hasArt = (key) => typeof key === 'string' && Object.hasOwn(ART, key);

// Resolve only packaged, known keys. API values never become arbitrary URLs.
export function artImage(key, {className = '', sizes = '(max-width:620px) calc(100vw - 36px), (max-width:1150px) 40vw, 28vw', eager = false, alt = ''} = {}) {
  if (!hasArt(key)) return '';
  const art = ART[key];
  // The map opens magnified and can zoom further: always load its full texture.
  const srcset = className.split(/\s+/).includes('galaxy-map-art') ? `${art.src} ${art.width}w`
    : `${art.small} ${art.smallWidth}w, ${art.src} ${art.width}w`;
  return `<img class="game-art ${escapeAttribute(className)}" src="${art.src}" srcset="${srcset}" sizes="${escapeAttribute(sizes)}" width="${art.width}" height="${art.height}" alt="${escapeAttribute(alt)}" loading="${eager ? 'eager' : 'lazy'}" decoding="async" data-art-key="${escapeAttribute(key)}">`;
}

export function catalogArtKey(item = {}, group = '') {
  if (hasArt(item.web_art_key)) return item.web_art_key;
  if (group === 'research' && hasArt(`research/${item.key}`)) return `research/${item.key}`;
  if (group === 'ships' && hasArt(`fleet/${item.race_id}/${item.key}`)) return `fleet/${item.race_id}/${item.key}`;
  if (hasArt(item.art_key)) return item.art_key;
  const capitalAlias={battleship:'cruiser',dreadnought:'siege',flagship:'siege',titan:'siege'};
  if(capitalAlias[item.key]&&hasArt(`races/${item.race_id}/${capitalAlias[item.key]}`))return `races/${item.race_id}/${capitalAlias[item.key]}`;
  if(item.unique&&group==='research'&&hasArt(`races/${item.race_id}/weapon`))return `races/${item.race_id}/weapon`;
  const aliases = {battleship:'ship_cruiser',dreadnought:'ship_cruiser',flagship:'ship_cruiser',titan:'ship_cruiser',observatory:'building_lab', propulsion:'ship_scout', weapons:'ship_cruiser',
    interceptor:'ship_frigate', siege:'ship_cruiser', freighter:'ship_cargo'};
  const candidates = [aliases[item.key], item.key,
    group === 'buildings' ? `building_${item.key}` : `ship_${item.key}`,
    group === 'research' ? 'building_lab' : ''];
  return candidates.find(hasArt) || '';
}

export function planetArtKey(planet = {}) {
  const environment = planet.environment || {};
  // Do not invent a planet type for unexplored or undisclosed worlds.
  return [environment.planet_art, environment.type ? `worlds/planet_${environment.type}` : ''].find(hasArt) || '';
}

export function colonyArtKey(state = {}) {
  return [state.environment?.colony_art, state.colony_art, state.race?.colony_art, 'colony_panorama'].find(hasArt) || '';
}

// Keep the labels and actions usable if an image fails to load.
document.addEventListener('error', (event) => {
  const target = event.target;
  if (target instanceof HTMLImageElement && target.classList.contains('game-art')) {
    target.hidden = true;
    target.parentElement?.classList.add('art-unavailable');
  }
}, true);

