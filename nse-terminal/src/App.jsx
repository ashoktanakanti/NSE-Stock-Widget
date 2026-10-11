import { useCallback, useMemo, useRef, useState } from 'react'
import Breadth from './components/Breadth'
import ForecastPanel from './components/ForecastPanel'
import Header from './components/Header'
import { Warn } from './components/Icons'
import MobileNav from './components/MobileNav'
import Profile from './components/Profile'
import StockTable from './components/StockTable'
import Watchlist from './components/Watchlist'
import { useMarketData, useShortcuts } from './hooks'
import { ago, parseTs, useLocal } from './lib'
import { visibleRows } from './rows'

const STALE_MS = 10 * 60_000
const DESKTOP_TABS = [
  ['home', 'All NSE'],
  ['watch', 'Watchlist'],
  ['profile', 'Data'],
]

export default function App() {
  const { quotes, loading, error, status, refreshing, load, refresh } = useMarketData()

  const [query, setQuery] = useState('')
  const [sector, setSector] = useState(null)
  const [tab, setTab] = useState('home')
  const [selected, setSelected] = useState(null)
  const [sort, setSort] = useLocal('nse.sort', { key: 'market_cap', dir: -1 })
  const [watch, setWatch] = useLocal('nse.watch', [])
  const searchRef = useRef(null)

  const rows = useMemo(
    () => visibleRows(quotes, { query, sector, sort, watch, watchOnly: tab === 'watch' }),
    [quotes, query, sector, sort, watch, tab],
  )
  const selectedQuote = quotes.find((q) => q.ticker === selected)

  const toggleWatch = useCallback(
    (ticker) =>
      setWatch((w) => (w.includes(ticker) ? w.filter((t) => t !== ticker) : [...w, ticker])),
    [setWatch],
  )

  useShortcuts({
    query,
    clearQuery: () => setQuery(''),
    clearSelection: () => setSelected(null),
    focusSearch: () => searchRef.current?.focus(),
    refresh,
    star: () => selected && toggleWatch(selected),
    toggleWatchView: () => setTab((t) => (t === 'watch' ? 'home' : 'watch')),
    move: (step) => {
      if (!rows.length) return
      const i = rows.findIndex((r) => r.ticker === selected)
      const next = i < 0 ? 0 : Math.max(0, Math.min(rows.length - 1, i + step))
      setSelected(rows[next].ticker)
    },
  })

  const banners = getBanners({ error, quotes, status, load, refresh })
  const tableProps = {
    rows,
    loading,
    sort,
    setSort,
    selected,
    onSelect: setSelected,
    watch,
    toggle: toggleWatch,
  }
  const panel = (
    <ForecastPanel
      quote={selectedQuote}
      onClose={() => setSelected(null)}
      watched={Boolean(selectedQuote) && watch.includes(selectedQuote.ticker)}
      toggle={toggleWatch}
    />
  )
  // On mobile the panel is a bottom sheet over the list (except on the Analytics tab)
  const sheetOpen = selectedQuote && tab !== 'analytics'

  return (
    <div className="flex h-[100dvh] flex-col">
      <Header
        ref={searchRef}
        query={query}
        setQuery={setQuery}
        status={status}
        refreshing={refreshing}
        onRefresh={refresh}
      />

      {banners.map(({ message, action, onAction }) => (
        <div
          key={message}
          className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/[.07] px-4 py-1.5 text-[11px] text-amber-200"
        >
          <Warn className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">{message}</span>
          {action && (
            <button
              onClick={onAction}
              className="rounded border border-amber-500/30 px-2 py-0.5 transition hover:bg-amber-500/10"
            >
              {action}
            </button>
          )}
        </div>
      ))}

      {tab !== 'profile' && (
        <Breadth quotes={quotes} sector={sector} setSector={setSector} onSelect={setSelected} />
      )}

      <div className="hidden border-b px-4 lg:flex">
        {DESKTOP_TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`border-b-2 px-3 py-2 text-xs transition ${
              tab === key
                ? 'border-up text-up'
                : 'border-transparent text-slate-500 hover:text-slate-200'
            }`}
          >
            {key === 'watch' ? `★ ${label} (${watch.length})` : label}
          </button>
        ))}
      </div>

      <main className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_400px] 2xl:grid-cols-[minmax(0,1fr)_460px]">
        <section className="min-h-0 overflow-y-auto pb-20 lg:border-r lg:pb-0">
          <MainView
            tab={tab}
            blank={!loading && quotes.length === 0}
            error={error}
            status={status}
            load={load}
            quotes={quotes}
            watch={watch}
            setWatch={setWatch}
            tableProps={tableProps}
            panel={selectedQuote ? panel : null}
          />
        </section>

        <aside
          className={`${
            sheetOpen
              ? 'fixed inset-0 z-40 flex flex-col bg-black/50 pt-16 backdrop-blur-[2px] lg:static lg:z-auto lg:bg-card lg:pt-0 lg:backdrop-blur-none'
              : 'hidden lg:block'
          } min-h-0 bg-card`}
          onClick={(e) => e.target === e.currentTarget && setSelected(null)}
        >
          <div className="min-h-0 flex-1 overflow-hidden rounded-t-2xl border-t lg:h-full lg:rounded-none lg:border-0">
            {panel}
          </div>
        </aside>
      </main>

      <MobileNav tab={tab} setTab={setTab} count={watch.length} />
    </div>
  )
}

function MainView({ tab, blank, error, status, load, quotes, watch, setWatch, tableProps, panel }) {
  if (blank) return <Empty error={error} retry={load} seeding={status?.seeding} />
  if (tab === 'profile') {
    return <Profile status={status} quotes={quotes} watch={watch} setWatch={setWatch} />
  }
  if (tab === 'watch') return <Watchlist {...tableProps} />
  if (tab === 'analytics') {
    // Mobile-only tab: show the selected stock inline, or a list to pick from
    return (
      <>
        <div className="lg:hidden">
          {panel || (
            <>
              <div className="border-b px-4 py-3 text-xs text-slate-500">
                Pick a stock to see its chart and forecast.
              </div>
              <StockTable {...tableProps} />
            </>
          )}
        </div>
        <div className="hidden lg:block">
          <StockTable {...tableProps} />
        </div>
      </>
    )
  }
  return <StockTable {...tableProps} />
}

function getBanners({ error, quotes, status, load, refresh }) {
  const asOf = parseTs(status?.last_quote_at)
  const stale = status?.market?.open && asOf && Date.now() - asOf > STALE_MS
  const banners = []
  if (error && quotes.length > 0) {
    banners.push({
      message: `${error}. Showing last loaded data.`,
      action: 'Retry',
      onAction: load,
    })
  }
  if (status?.tickers_simulated > 0) {
    banners.push({
      message: `${status.tickers_simulated} stock(s) show simulated prices because Yahoo could not be reached. They are marked SIM and get no forecast.`,
    })
  }
  if (stale) {
    banners.push({
      message: `Market is open but the latest quote is ${ago(asOf)}. Live fetches may be failing.`,
      action: 'Refresh',
      onAction: refresh,
    })
  }
  return banners
}

function Empty({ error, retry, seeding }) {
  // Fresh deploys start with an empty DB and seed in the background (~20s)
  if (seeding && !error) {
    return (
      <div className="mx-auto max-w-md p-10 text-sm text-slate-400">
        <div className="mb-2 flex items-center gap-2 font-semibold text-slate-200">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
          Loading market data
        </div>
        <p className="text-xs text-slate-500">
          Fetching 6 months of daily prices for the Nifty 500. This takes about 20 seconds on first
          start; the page fills in automatically.
        </p>
        <div className="mt-4 space-y-px">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="skel h-9" style={{ opacity: 1 - i * 0.15 }} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md p-10 text-sm text-slate-400">
      {error ? (
        <>
          <div className="mb-2 flex items-center gap-2 font-semibold text-slate-200">
            <Warn className="h-4 w-4 shrink-0 text-amber-300" />
            {error}
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Retrying every 5 seconds. If the server was asleep it can take up to a minute to wake.
            Running locally? Start the backend from the project folder:
          </p>
        </>
      ) : (
        <>
          <div className="mb-2 font-semibold text-slate-200">No market data yet</div>
          <p className="mb-3 text-xs text-slate-500">
            The database is empty. Start the API and it will load ~6 months of history:
          </p>
        </>
      )}
      <pre className="mb-4 overflow-x-auto rounded-lg border bg-card p-3 font-mono text-[11px] leading-relaxed text-slate-300">
        python app.py
      </pre>
      <button
        onClick={retry}
        className="rounded-lg border border-up/30 bg-up/10 px-3 py-1.5 font-mono text-xs text-up transition hover:bg-up/20 active:scale-95"
      >
        Retry
      </button>
    </div>
  )
}
