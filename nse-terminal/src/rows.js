// Filtering and sorting for the stock table (pure functions, unit-tested).

// 'move' sorts by the size of today's move regardless of direction
export function sortValue(row, key) {
  if (key === 'move') return row.change_pct == null ? null : Math.abs(row.change_pct)
  return row[key]
}

export function compareRows(a, b, { key, dir }) {
  if (key === 'symbol') return dir * a.symbol.localeCompare(b.symbol)
  const va = sortValue(a, key)
  const vb = sortValue(b, key)
  // Missing values always sink to the bottom, whatever the direction
  if (va == null) return vb == null ? 0 : 1
  if (vb == null) return -1
  return dir * (va - vb)
}

export function filterRows(quotes, { query = '', sector = null, watchOnly = false, watch = [] }) {
  const q = query.trim().toLowerCase()
  return quotes.filter(
    (s) =>
      (!q || s.symbol.toLowerCase().includes(q) || (s.name || '').toLowerCase().includes(q)) &&
      (!sector || s.sector === sector) &&
      (!watchOnly || watch.includes(s.ticker)),
  )
}

export function visibleRows(
  quotes,
  { query = '', sector = null, watchOnly = false, watch = [], sort },
) {
  const q = query.trim().toLowerCase()
  // While searching, an exact symbol match floats to the top
  const exactFirst = (s) => (q && s.symbol.toLowerCase() === q ? 0 : 1)
  return filterRows(quotes, { query, sector, watchOnly, watch }).sort(
    (a, b) => exactFirst(a) - exactFirst(b) || compareRows(a, b, sort),
  )
}
