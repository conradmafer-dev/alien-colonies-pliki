// Authoritative flight timing; route distances, never screen pixels, apportion time.
const positive = value => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : 0;
export function flightPlan(fleet) {
  const route = fleet.route || {}, returning = fleet.status === 'returning';
  const origin = fleet.origin_system_id || route.system_ids?.[0] || '';
  const target = fleet.target_system_id || route.system_ids?.at(-1) || '';
  const mode = route.travel_mode === 'tunnel' ? 'tunnel' : route.intergalactic ? 'intergalactic' : 'normal';
  let segments = mode === 'normal' && Array.isArray(route.segments)
    ? route.segments.filter(s => s.from_system_id && s.to_system_id && positive(s.distance)).map(s => ({...s,distance:positive(s.distance)})) : [];
  if (!segments.length) segments = [{from_system_id:origin,to_system_id:target,
    kind:mode === 'normal' ? origin === target ? 'local' : 'legacy' : mode,distance:1}];
  if (returning) segments = segments.reverse().map(s => ({...s,from_system_id:s.to_system_id,to_system_id:s.from_system_id}));
  if (returning && Number.isFinite(Number(fleet.map_return_fraction)) && Number(fleet.map_return_fraction) < 1) {
    const fraction=Math.max(0,Number(fleet.map_return_fraction));
    let skip=segments.reduce((n,s)=>n+s.distance,0)*(1-fraction);
    while(segments.length && skip>=segments[0].distance-1e-10)skip-=segments.shift().distance;
    if(segments.length){segments[0].from_fraction=skip/segments[0].distance;segments[0].distance-=skip;}
    else segments=[{from_system_id:origin,to_system_id:origin,kind:'stationary',distance:1}];
  }
  return {segments,total:segments.reduce((n,s)=>n+s.distance,0),returning,mode,origin,target,
    fromGalaxy:returning ? fleet.target_galaxy_id || route.target_galaxy_id : fleet.origin_galaxy_id || route.origin_galaxy_id,
    toGalaxy:returning ? fleet.origin_galaxy_id || route.origin_galaxy_id : fleet.target_galaxy_id || route.target_galaxy_id};
}
export function flightProgress(fleet, now) {
  if (['holding','exploring'].includes(fleet.status)) return 1;
  const end = positive(fleet.arrives_at), seconds = positive(fleet.seconds);
  const start = positive(fleet.started_at) || end - seconds;
  if (!end || !Number.isFinite(Number(now))) return 0;
  if (end <= start) return Number(now) >= end ? 1 : 0;
  return Math.max(0,Math.min(1,(Number(now)-start)/(end-start)));
}
export function flightSample(fleet, now, plan = flightPlan(fleet)) {
  const progress = flightProgress(fleet,now);
  let remaining = progress * plan.total;
  for (let index=0;index<plan.segments.length;index++) {
    const segment=plan.segments[index];
    if (remaining < segment.distance || index === plan.segments.length-1)
      return {progress,index,segment,fraction:Math.max(0,Math.min(1,remaining/segment.distance)),...plan};
    remaining-=segment.distance;
  }
  return {progress,index:0,segment:plan.segments[0],fraction:0,...plan};
}
export function reportIconKind(report) {
  const allowed = ['scout','battle','warning','transport','return','colonization','research','construction','defense','shipyard','skill','protection','empire','recycling','expedition','ranking'];
  if (allowed.includes(report.kind)) return report.kind;
  if (report.battle_replay_available) return 'battle';
  if (report.scout || report.planet_scout || report.system_scout) return 'scout';
  return 'empire';
}


// Semantic map colors are shared by the route, moving ship, and legend.
export const FLEET_MAP_COLORS = Object.freeze({
  scout:'#91a8c8', transport:'#e4c17a', colonize:'#9be4ad',
  attack:'#ff9295', alliance_attack:'#ff9295', alliance_defense:'#bcabff',
  returning:'#b6bdc8', expedition:'#d7a6ff',
});
export function fleetMapColor(fleet) {
  return fleet.status === 'returning' ? FLEET_MAP_COLORS.returning
    : FLEET_MAP_COLORS[fleet.mission] || FLEET_MAP_COLORS.scout;
}

// Mission cards retain their existing UI accent.
export function fleetMarkerToken(fleet) {
  return String(fleet.art_key || '').startsWith('swarm/') ? '--gold' : '--teal';
}

