import StockTable from './StockTable'
import { Star } from './Icons'
import { pct, tone } from '../lib'
export default function Watchlist(p) {
  if (!p.loading && p.watch.length === 0)
    return (
      <div className="flex flex-col items-center p-12 text-center text-sm text-slate-500">
        <Star className="mb-3 h-8 w-8 text-slate-700" />
        Star a stock to pin it here.
        <span className="mt-1 text-[11px] text-slate-600">
          Tip: select a row and press <kbd className="rounded border px-1 font-mono">s</kbd>
        </span>
      </div>
    )
  const ch = p.rows.filter((r) => r.change_pct != null)
  const avg = ch.reduce((s, r) => s + r.change_pct, 0) / (ch.length || 1)
  return (
    <>
      {p.rows.length > 0 && (
        <div className="flex items-center justify-between border-b px-4 py-2 text-[11px] text-slate-500">
          <span>{p.rows.length} saved</span>
          <span>
            Equal-weight 1D <span className={`num font-semibold ${tone(avg)}`}>{pct(avg)}</span>
          </span>
        </div>
      )}
      <StockTable
        {...p}
        empty={
          <div className="p-10 text-center text-sm text-slate-500">
            No saved stocks match this filter.
          </div>
        }
      />
    </>
  )
}
