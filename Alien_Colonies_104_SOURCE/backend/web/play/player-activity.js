// A quiet open tab is not player activity. Requests carry only a pending gesture,
// foreground transition, or initial launch; failed requests never consume it.
export function createPlayerActivity({now = () => performance.now(), interval = 60000} = {}) {
  let generation = 1, acknowledged = 0, attemptedAt = -Infinity;
  return {
    mark() { generation++; },
    reset() { generation = 1; acknowledged = 0; attemptedAt = -Infinity; },
    take({authenticated, visible, method = 'GET', path = ''}) {
      if (!authenticated || !visible || method !== 'GET' || !/^\/state(?:\?|$)/.test(path)
          || generation <= acknowledged || now() - attemptedAt < interval) return 0;
      attemptedAt = now();
      return generation;
    },
    acknowledge(sent) { if (sent) acknowledged = Math.max(acknowledged, sent); },
  };
}

export function productionWindow(state, now) {
  const status = state.production_status;
  const snapshot = Number(state.server_time || now);
  const stop = Number(status?.stops_at);
  const paused = status?.paused === true || (Number.isFinite(stop) && stop > 0 && now >= stop);
  const elapsed = status?.paused ? 0 : Math.max(0, Math.min(now, Number.isFinite(stop) && stop > 0 ? stop : now) - snapshot);
  return {paused, elapsed};
}
