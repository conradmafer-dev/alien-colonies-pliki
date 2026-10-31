import { t, text, html, getLanguage, getLocale, LANGUAGES, setLanguage } from './i18n.js?v=0111';
// Presentation only: every value comes from the authoritative catalogue.
// Do not duplicate economy rules here: energy shortage, planet traits and skills
// are already included in details.metrics by the server.
const number = (value) => Number(value || 0).toLocaleString(getLocale(), {maximumFractionDigits:2});
const integer = (value) => Number(value || 0).toLocaleString(getLocale(), {maximumFractionDigits:0});
const metric = (item, key) => item.details?.metrics?.find((row) => row.key === key);
const hasNext = (item) => Number(item.level) < Number(item.max_level);
const resourceLabels = {metal:t('Metal'), crystal:t('Kryształy'), fuel:t('Paliwo')};
const compactEffects = {
  scout_time_reduction:[t('Czas zwiadu'), 'discount'],
  mining_energy_reduction:[t('Energia wydobycia'), 'discount'],
  research_crystal_refund:[t('Zwrot kryształów'), 'percent'],
  batch_time_reduction_per_extra:[t('Czas / kolejny statek'), 'discount'],
  defense_first_volley:[t('Pierwsza salwa obrony'), 'bonus'],
  wreck_recovery_fraction:[t('Odzysk metalu z wraków'), 'percent'],
  building_time_reduction:[t('Czas budowy'), 'discount'],
  colony_start_building_bonus:[t('Start kolonii'), 'colony'],
  renewal_fraction:[t('Regeneracja obrony'), 'points'],
  ship_time_reduction:[t('Czas budowy statków'), 'discount'],
  protected_resources:[t('Ochrona surowców'), 'stock'],
  fleet_fuel_reduction:[t('Paliwo wypraw'), 'discount'],
  production_all:[t('Wydobycie'), 'bonus'],
  production_metal:[t('Metal'), 'bonus'],
};

function effectValue(value, unit) {
  if (value == null) return '—';
  if (unit === 'per_hour') return `${integer(value)}/h`;
  if (unit === 'bonus') return `+${number(value)}%`;
  if (unit === 'percent') return `${number(value)}%`;
  return number(value);
}

function uniqueValue(value, unit) {
  if (value == null) return '—';
  if (unit === 'colony') return text`poz. ${integer(1 + Number(value))}`;
  if (unit === 'stock') return text`${integer(value)} / surowiec`;
  if (unit === 'points') return text`+${number(value * 100)} pkt proc.`;
  return `${unit === 'bonus' ? '+' : unit === 'discount' && value > 0 ? '−' : ''}${number(value * 100)}%`;
}

export function buildingSummary(item) {
  const resource = item.production_resource;
  if (resource) {
    const row = metric(item, `mine_${resource}`);
    return row ? `${resourceLabels[resource] || resource} ${effectValue(row.current, 'per_hour')}` : t('Wydobycie · szczegóły');
  }
  if (item.key === 'power_plant' && Number.isFinite(item.energy_supply_current)) {
    return text`Energia +${number(item.energy_supply_current)}`;
  }
  if (item.key === 'lab' || item.key === 'shipyard') {
    const row = metric(item, item.key === 'lab' ? 'lab_speed_bonus' : 'shipyard_speed_bonus');
    return `${item.key === 'lab' ? t('Badania') : t('Produkcja statków')} ${row ? effectValue(row.current, 'bonus') : t('· szczegóły')}`;
  }
  if (item.key === 'observatory') {
    const range = item.observation?.current?.range;
    return range == null || range < 0 ? t('Obserwacja nieaktywna') : text`Zasięg: ${range} w każdą stronę`;
  }
  const effect = item.building_effect;
  const entry = compactEffects[effect?.key];
  if (entry) return `${entry[0]} ${uniqueValue(effect.current, entry[1])}`;
  return item.effect_current || t('Efekt w szczegółach');
}

export function buildingDescription(item) {
  if (item.production_resource) return text`Wydobywa ${ {metal:t('metal'),crystal:t('kryształy'),fuel:t('paliwo')}[item.production_resource] || item.production_resource }. Potrzebuje energii.`;
  return {
    power_plant:t('Dostarcza energię do wydobycia surowców.'),
    lab:t('Odblokowuje technologie i przyspiesza badania w tej kolonii.'),
    shipyard:t('Odblokowuje i przyspiesza produkcję statków oraz obrony w tej kolonii.'),
    observatory:t('Zapewnia stały podgląd sąsiednich układów. Wyższe poziomy rozszerzają zasięg obserwacji.'),
  }[item.key] || item.description;
}

export function buildingComparison(item, detailed = false) {
  const rows = [];
  const next = hasNext(item);
  const add = (label, current, following, unit = 'number') => rows.push({label,
    current:effectValue(current, unit), next:next ? effectValue(following, unit) : null});
  const addMetric = (key, label, unit) => {
    const row = metric(item, key);
    if (row) add(label, row.current, row.next, unit || row.unit);
  };
  if (item.production_resource) {
    const resource = item.production_resource;
    addMetric(`mine_${resource}`, text`${resourceLabels[resource]} z budynku`, 'per_hour');
    addMetric('energy_use', t('Zużycie energii'));
    if (detailed) addMetric(`colony_${resource}`, text`${resourceLabels[resource]} w całej kolonii`, 'per_hour');
  } else if (item.key === 'power_plant') {
    // energy_supply also includes Dyson power. Show the plant's own contribution
    // separately, so a Dyson sphere is never presented as this building's bonus.
    if (Number.isFinite(item.energy_supply_current)) {
      add(t('Energia z budynku'), item.energy_supply_current, item.energy_supply_next);
    }
    if (detailed) {
      addMetric('energy_supply', t('Łączna energia kolonii'));
      for (const [key, label] of Object.entries(resourceLabels)) addMetric(`colony_${key}`, text`${label} w kolonii`, 'per_hour');
    }
  } else if (item.key === 'lab' || item.key === 'shipyard') {
    addMetric(item.key === 'lab' ? 'lab_speed_bonus' : 'shipyard_speed_bonus',
      item.key === 'lab' ? t('Szybkość badań') : t('Szybkość produkcji'), 'bonus');
    if (detailed) addMetric('facility_time_reduction', t('Skrócenie czasu'), 'percent');
  } else if (item.key === 'observatory') {
    const label = (profile) => profile?.range >= 0 ? text`${profile.range} w każdą stronę` : t('Nieaktywna');
    rows.push({label:t('Zasięg obserwacji'), current:label(item.observation?.current), next:next ? label(item.observation?.next) : null});
    if (detailed) rows.push({label:t('Podgląd budynków'), current:label({range:item.observation?.current?.building_range}), next:next ? label({range:item.observation?.next?.building_range}) : null});
  } else if (item.building_effect && compactEffects[item.building_effect.key]) {
    const effect = item.building_effect;
    const [label, unit] = compactEffects[effect.key];
    rows.push({label, current:uniqueValue(effect.current, unit), next:next ? uniqueValue(effect.next, unit) : null});
  } else if (item.effect_current) {
    rows.push({label:t('Działanie'), current:item.effect_current, next:next ? item.effect_next || '—' : null});
  }
  addMetric('storage_capacity', t('Pojemność magazynów'));
  if (detailed && item.unique) {
    for (const [key, label] of Object.entries(resourceLabels)) addMetric(`colony_${key}`, text`${label} w kolonii`, 'per_hour');
  }
  return rows;
}

export function buildingNotes(item, detailed = false) {
  const notes = [];
  const efficiency = metric(item, 'energy_efficiency');
  if (item.production_resource) notes.push(t('Wydobycie uwzględnia premie i dostępną energię. Nie obejmuje pasywnej produkcji kolonii.'));
  if (efficiency && (efficiency.current < 100 || efficiency.next != null && efficiency.next < 100)) {
    notes.push(t('Niedobór energii ogranicza wydobycie. Rozbudowa elektrowni pozwoli wykorzystać pełny potencjał kopalń.'));
  }
  if (item.key === 'lab' || item.key === 'shipyard') notes.push(t('Szybkość: ×(1 + poziom). Rozpoczęte projekty zachowują swój czas; zaplanowane obliczają go przy starcie.'));
  if (item.building_effect?.key === 'batch_time_reduction_per_extra') notes.push(t('Bonus za każdy kolejny statek w partii; łączne skrócenie czasu partii nie przekracza 30%.'));
  if (item.key === 'pioneer_nursery') notes.push(t('Bonus dotyczy czterech budynków gospodarczych nowej kolonii założonej wyprawą z tej planety.'));
  if (detailed && item.production_resource) notes.push(t('Następny poziom pokazuje efekt rozbudowy tylko tego budynku przy obecnym stanie kolonii.'));
  return notes;
}
