// Keep older server responses usable while preferring the concise catalog copy.
export function catalogDescription(item) {
  for (const value of [item?.brief_description, item?.description]) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}
