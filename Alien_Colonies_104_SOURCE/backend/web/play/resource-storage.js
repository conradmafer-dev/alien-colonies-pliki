// Display-only estimates. Purchases and queues always use server eligibility.
const RESOURCES = ['metal', 'crystal', 'fuel'];
const nonnegative = value => Math.max(0, Number(value) || 0);

export function storageCapacity(state, key) {
  const value = state?.storage?.capacity?.[key];
  return value != null && Number.isFinite(Number(value)) && Number(value) >= 0 ? Number(value) : null;
}

export function resourceSnapshot(state, key, elapsed = 0) {
  const stock = nonnegative(state?.resources?.[key]);
  const capacity = storageCapacity(state, key);
  const production = nonnegative(state?.production?.[key]) * nonnegative(elapsed) / 3600;
  // Deliveries may exceed storage: never truncate existing stock to capacity.
  const ceiling = capacity == null ? Number(state?.limits?.resource_cap || 1e9) : Math.max(stock, capacity);
  const current = Math.min(ceiling, stock + production);
  return {current, capacity, full: capacity != null && current >= capacity};
}

export function storageBlocksCost(state, cost = {}, amount = 1) {
  return RESOURCES.some(key => {
    const needed = nonnegative(cost[key]) * nonnegative(amount);
    const capacity = storageCapacity(state, key);
    return capacity != null && needed > capacity && needed > nonnegative(state?.resources?.[key]);
  });
}
