export function validFleetQuote(result) {
  const nonnegative = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  return Boolean(result && nonnegative(result.seconds) && nonnegative(result.fuel_cost)
    && nonnegative(result.capacity) && typeof result.affordable === 'boolean'
    && (!result.tunnel || nonnegative(result.tunnel.energy_cost)));
}

/** Latest-draft server quotes. Completing a quote never dispatches a mission. */
export function createFleetQuoteController({read, quote, onChange, delay = 300,
  setTimer = setTimeout, clearTimer = clearTimeout}) {
  let generation = 0, timer = null, state = {phase:'idle'}, snapshot = null;
  const identity = value => value && JSON.stringify([value.scope, value.payload]);
  const stockDecreased = (current, previous) => {
    const next = current?.stock || {}, prior = previous?.stock || {};
    return [...new Set([...Object.keys(next),...Object.keys(prior)])]
      .some(key => Number(next[key] ?? 0) < Number(prior[key] ?? 0));
  };
  const publish = next => { state = next; onChange?.(next); };
  function cancel() {
    generation++;
    if (timer !== null) clearTimer(timer);
    timer = null; snapshot = null; state = {phase:'idle'};
  }
  function update() {
    const current = read();
    if (current && !current.reason && identity(current) === identity(snapshot)) {
      const stock = current.stock || {}, previous = snapshot?.stock || {};
      const decreased = stockDecreased(current,snapshot);
      const increased = Object.keys(stock).some(key => Number(stock[key]) > Number(previous[key]));
      // Passive polling must not starve a slow preview. Growing resources and
      // observation timestamps do not change the quoted route or ship prices.
      if (!decreased && (state.phase === 'waiting' || state.phase === 'loading')) {
        snapshot = {...snapshot,stock:{...stock}};
        return;
      }
      if (!decreased && state.phase === 'ready' && (state.result.affordable || !increased)) {
        snapshot = {...snapshot,stock:{...stock}};
        return;
      }
    }
    cancel();
    if (!current || current.reason) {
      publish({phase:'invalid', reason:current?.reason || ''});
      return;
    }
    snapshot = current;
    const request = generation, key = identity(current);
    publish({phase:'waiting'});
    timer = setTimer(async () => {
      timer = null;
      if (request !== generation || key !== identity(read())) return;
      publish({phase:'loading'});
      try {
        const result = await quote(current.payload);
        if (request !== generation || key !== identity(read())) return;
        if (stockDecreased(read(),snapshot)) { update(); return; }
        if (!validFleetQuote(result)) throw new Error('Niepełna wycena trasy. Spróbuj ponownie.');
        snapshot = {...current,stock:result.affordable ? read()?.stock : current.stock};
        publish({phase:'ready', payload:current.payload, result});
      } catch (error) {
        if (request !== generation || key !== identity(read())) return;
        publish({phase:'error', error});
      }
    }, delay);
  }
  function currentQuote() {
    const current = read();
    if (state.phase !== 'ready' || !current || current.reason || identity(current) !== identity(snapshot)
      || stockDecreased(current,snapshot) || !validFleetQuote(state.result) || state.result.affordable !== true) return null;
    return {payload:state.payload, result:state.result};
  }
  return {update, cancel, currentQuote, snapshot:() => state};
}

/** Price/eligibility context, excluding polling timestamps and growing stocks. */
export function fleetQuoteContext(state, payload, now) {
  const systems = state.galaxy || [];
  const target = systems.flatMap(system => system.planets || []).find(planet => planet.id === payload.target_id);
  const system = systems.find(system => system.id === payload.target_system_id || system.id === target?.system_id
    || system.scout_target_id === payload.target_id || system.system_scout_target_id === payload.target_id);
  const mega = state.megastructures || {}, window = mega.window || {};
  return JSON.stringify([
    state.planet_id,state.ships,state.research,state.buildings,state.speed,state.expeditions,
    (state.own_planets || []).map(planet => [planet.id,planet.system_id]),
    (state.fleets || []).map(fleet => [fleet.id,fleet.mission,fleet.status,fleet.target_id]),
    state.limits?.colonies,state.alliance?.id,
    target && [target.id,target.owner_id,target.owner_type,target.alliance_id,target.is_home_planet,
      Number(target.protected_until) > now,target.system_id,target.galaxy_id,target.x,target.y],
    system && [system.id,system.galaxy_id,system.x,system.y,system.connections],
    mega.origin_id,mega.dyson_stage,mega.gate_level,window.id,window.target_id,
    Number(window.closes_at) > now,
    (state.catalog?.ships || []).map(ship => [ship.key,ship.capacity,ship.speed,ship.fuel,ship.stats]),
  ]);
}

/** Remember composition independently of which destination view is open. */
export function saveFleetDraft(model, payload) {
  if (!payload?.target_id || payload.planet_id !== model.state?.planet_id) return;
  model.fleetDraft = JSON.parse(JSON.stringify(payload));
  model.fleetMission = payload.mission;
  model.fleetTravelMode = payload.travel_mode;
}
