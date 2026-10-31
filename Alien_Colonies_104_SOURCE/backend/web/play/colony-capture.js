// Capture availability uses known identity only. Defenses and ships are
// checked by the server at preview, dispatch and arrival, never inferred here.
export const COLONIZATION_WARNING = 'Uwaga: przy braku floty, obrony planetarnej i wsparcia sojuszników dodatkowa kolonia może zostać przejęta przez inną cywilizację. Planeta macierzysta jest chroniona przed przejęciem.';

export function canAttemptColonization(state, planet, now = Date.now() / 1000) {
  if (!planet || planet.visibility === 'unknown' || planet.owner_id === state.player?.id) return false;
  if (planet.owner_type === 'empty') return true;
  if (!state.colonization_capture?.enabled || planet.owner_type !== 'player' || planet.is_home_planet !== false) return false;
  if (state.alliance?.id && state.alliance.id === planet.alliance_id) return false;
  return Number(planet.protected_until || 0) <= now;
}
