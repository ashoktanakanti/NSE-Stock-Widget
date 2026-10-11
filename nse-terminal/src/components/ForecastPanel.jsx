import { useEffect, useState } from 'react'
import { api, cap, enc, inr, nextSessions, num, pct, tone, vol } from '../lib'
import { Close, Star, Warn } from './Icons'
import PriceChart from './PriceChart'

const RANGES = [
  ['1M', 22],
  ['3M', 63],
  ['6M', 130],
]
const FEATURE_LABEL = {
  ret_1: '1D return',
  ret_2: '2D-ago return',
  dev_mean_5: 'Gap to 5D mean',
  volatility_5: '5D volatility',
  rel_volume: 'Volume vs 20D',
}

/** Detail view for one stock: quote stats, price chart and model forecast. */
export default function ForecastPanel({ quote, onClose, watched, toggle }) {
  const [prediction, setPrediction] = useState(null)
  const [history, setHistory] = useState(null)
  const [range, setRange] = useState(63)

  useEffect(() => {
    if (!quote) return
    setPrediction(null)
    setHistory(null)
    let live = true
    api(`/api/predict/${enc(quote.ticker)}`)
      .then((d) => live && setPrediction(d))
      .catch(() => live && setPrediction({ error: 'Forecast request failed. Is the API running?' }))
    api(`/api/history/${enc(quote.ticker)}?limit=130`)
      .then((d) => live && setHistory(d))
      .catch(() => live && setHistory([]))
    return () => {
      live = false
    }
  }, [quote?.ticker, quote?.fetched_at])

  if (!quote) {
    return (
      <div className="hidden h-full flex-col items-center justify-center gap-2 text-sm text-slate-500 lg:flex">
        <span>Select a stock for chart & forecast</span>
        <span className="text-[11px] text-slate-600">
          <Kbd>↑</Kbd> <Kbd>↓</Kbd> to move · <Kbd>s</Kbd> to star
        </span>
      </div>
    )
  }

  const forecasts = prediction?.error ? [] : prediction?.forecasts || []
  const metrics = prediction?.metrics || {}
  const lastDate = history?.length ? history.at(-1).date : null
  const forecastDates = lastDate ? nextSessions(lastDate, forecasts.length) : []

  return (
    <div className="h-full overflow-y-auto bg-card pb-24 animate-sheet lg:animate-none lg:pb-0">
      <PanelHeader quote={quote} watched={watched} toggle={toggle} onClose={onClose} />
      <QuoteStats quote={quote} />
      <Week52 lo={quote.week52_low} hi={quote.week52_high} price={quote.price} />

      <div className="border-t p-4">
        <div className="mb-2 flex items-center justify-between">
          <SectionLabel>Daily close · dashed = forecast</SectionLabel>
          <div className="flex rounded-md border p-0.5">
            {RANGES.map(([label, days]) => (
              <button
                key={label}
                onClick={() => setRange(days)}
                className={`rounded px-2 py-0.5 font-mono text-[10px] transition ${
                  range === days
                    ? 'bg-white/10 text-slate-100'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <PriceChart
          bars={(history || []).slice(-range)}
          fc={forecasts}
          fcDates={forecastDates}
          mae={metrics.cv_mae}
        />
      </div>

      <div className="border-t p-4">
        <ForecastList
          prediction={prediction}
          forecasts={forecasts}
          dates={forecastDates}
          mae={metrics.cv_mae}
        />
        {prediction && !prediction.error && (
          <>
            <BaselineComparison metrics={metrics} />
            <FeatureWeights importance={prediction.feature_importance} />
          </>
        )}
        <p className="mt-4 text-[10px] leading-relaxed text-slate-600">
          Ridge regression on ~6 months of daily returns. Band = ±CV MAE·√t. Not investment advice.
        </p>
      </div>
    </div>
  )
}

function PanelHeader({ quote, watched, toggle, onClose }) {
  const change = quote.prev_close != null ? quote.price - quote.prev_close : null
  return (
    <div className="sticky top-0 z-10 flex items-start gap-3 border-b bg-card/95 p-4 backdrop-blur">
      <div className="min-w-0 flex-1">
        <div className="num flex items-center gap-2 text-lg font-bold">
          {quote.symbol}
          <span className="rounded bg-up/15 px-1.5 text-[10px] font-medium text-up">NSE</span>
          {quote.source === 'simulated' && (
            <span className="rounded bg-amber-500/15 px-1.5 text-[10px] font-medium text-amber-300">
              SIMULATED
            </span>
          )}
          <button
            onClick={() => toggle(quote.ticker)}
            className={`transition active:scale-125 ${
              watched ? 'text-amber-400' : 'text-slate-600 hover:text-slate-300'
            }`}
            aria-label="Toggle watchlist"
          >
            <Star on={watched} />
          </button>
        </div>
        <div className="truncate text-xs text-slate-500">
          {quote.name} · {quote.sector}
        </div>
      </div>
      <div className="text-right">
        <div className="num text-xl font-bold">{inr(quote.price)}</div>
        <div className={`num text-xs ${tone(quote.change_pct)}`}>
          {change != null && (change >= 0 ? '+' : '') + num(change)} ({pct(quote.change_pct)})
        </div>
      </div>
      <button
        onClick={onClose}
        className="-mr-1 rounded p-1 text-slate-500 transition hover:bg-white/5 hover:text-white lg:hidden"
        aria-label="Close"
      >
        <Close />
      </button>
    </div>
  )
}

function QuoteStats({ quote }) {
  const stats = [
    ['Prev close', inr(quote.prev_close)],
    ['Open', inr(quote.open_price)],
    ['High', inr(quote.high_price), 'text-up'],
    ['Low', inr(quote.low_price), 'text-down'],
    ['Volume', vol(quote.volume)],
    ['Mkt cap', cap(quote.market_cap)],
    ['P/E', quote.pe_ratio ? Number(quote.pe_ratio).toFixed(1) : '—'],
    ['1M', pct(quote.ret_1m), tone(quote.ret_1m)],
  ]
  return (
    <div className="grid grid-cols-4 gap-px bg-white/[.06]">
      {stats.map(([label, value, color]) => (
        <div key={label} className="bg-card px-3 py-2">
          <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
          <div className={`num truncate text-[12px] font-semibold ${color || ''}`}>{value}</div>
        </div>
      ))}
    </div>
  )
}

function ForecastList({ prediction, forecasts, dates, mae }) {
  const target = forecasts.at(-1)
  const targetPct =
    target != null && prediction?.current_price
      ? (target / prediction.current_price - 1) * 100
      : null

  return (
    <>
      <div className="mb-2 flex items-baseline justify-between">
        <SectionLabel>5-session forecast</SectionLabel>
        {targetPct != null && (
          <span className="text-[11px] text-slate-500">
            T+5 <span className={`num font-semibold ${tone(targetPct)}`}>{pct(targetPct)}</span>
          </span>
        )}
      </div>

      {!prediction && (
        <div className="space-y-1">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="skel h-8" />
          ))}
        </div>
      )}

      {prediction?.error && (
        <div className="flex gap-2 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
          <Warn className="mt-px h-3.5 w-3.5 shrink-0" />
          {prediction.error}
        </div>
      )}

      <div className="space-y-1">
        {forecasts.map((price, i) => {
          const base = i ? forecasts[i - 1] : prediction.current_price
          const stepPct = ((price - base) / base) * 100
          const band = (mae || 0) * Math.sqrt(i + 1)
          const day = dates[i]
            ? new Date(`${dates[i]}T00:00:00Z`).toLocaleDateString('en-IN', {
                weekday: 'short',
                day: '2-digit',
                timeZone: 'UTC',
              })
            : ''
          return (
            <div
              key={i}
              className="grid animate-fade grid-cols-[44px_56px_1fr_auto_64px] items-center gap-2 rounded bg-white/[.03] px-3 py-1.5"
              style={{ animationDelay: `${i * 30}ms`, animationFillMode: 'backwards' }}
            >
              <span className="font-mono text-[11px] text-slate-500">T+{i + 1}</span>
              <span className="text-[11px] text-slate-500">{day}</span>
              <span className="num text-sm font-semibold">{inr(price)}</span>
              <span className="num text-[10px] text-slate-600">±{num(band)}</span>
              <span className={`num text-right text-xs ${tone(stepPct)}`}>{pct(stepPct)}</span>
            </div>
          )
        })}
      </div>
    </>
  )
}

/** Out-of-sample error of the model vs the naive "tomorrow = today" guess. */
function BaselineComparison({ metrics }) {
  const { cv_mae: model, naive_mae: naive, skill, beats_naive: wins, n_samples: n } = metrics
  if (model == null || naive == null) return null
  const verdict = wins
    ? `Model beats the naive guess by ${(skill * 100).toFixed(1)}% on this stock.`
    : `The naive guess wins on this stock: the model is ${(-skill * 100).toFixed(1)}% worse.`

  return (
    <div className="mt-4">
      <SectionLabel>Walk-forward error vs baseline</SectionLabel>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center">
        <Metric
          label="Model MAE"
          value={`₹${num(model)}`}
          title="Mean absolute error on unseen days"
        />
        <Metric
          label="Naive MAE"
          value={`₹${num(naive)}`}
          title="Error of predicting tomorrow's close = today's close"
          highlight={!wins}
        />
        <Metric label="Days" value={n ?? '—'} title="Daily rows used" />
      </div>
      <p className={`mt-2 text-[11px] ${wins ? 'text-up' : 'text-amber-300'}`}>{verdict}</p>
    </div>
  )
}

function FeatureWeights({ importance }) {
  // Flask serialises keys alphabetically, so rank here
  const entries = Object.entries(importance || {}).sort((a, b) => b[1] - a[1])
  if (!entries.length) return null
  const total = entries.reduce((sum, [, v]) => sum + v, 0) || 1
  return (
    <div className="mt-4">
      <SectionLabel>Feature weight (share of |coef|)</SectionLabel>
      <div className="mt-1.5">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="grid grid-cols-[104px_1fr_40px] items-center gap-2 py-0.5 text-[11px]"
          >
            <span className="text-slate-400">{FEATURE_LABEL[key] || key}</span>
            <div className="h-1 rounded-full bg-white/5">
              <div
                className="h-1 rounded-full bg-slate-400 transition-all duration-500"
                style={{ width: `${(value / total) * 100}%` }}
              />
            </div>
            <span className="num text-right text-slate-500">
              {Math.round((value / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Week52({ lo, hi, price }) {
  if (lo == null || hi == null) return null
  const position = Math.min(100, Math.max(0, ((price - lo) / (hi - lo || 1)) * 100))
  const offHigh = (price / hi - 1) * 100
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-t px-4 py-2.5 text-[11px]">
      <span className="num text-slate-500">52W {num(lo)}</span>
      <div className="relative h-1 rounded-full bg-white/10">
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-slate-100 transition-all duration-500"
          style={{ left: `calc(${position}% - 1px)` }}
        />
      </div>
      <span className="num text-slate-500">
        {num(hi)} <span className={tone(offHigh)}>({pct(offHigh)})</span>
      </span>
    </div>
  )
}

function Metric({ label, value, title, highlight }) {
  return (
    <div className={`rounded border p-2 ${highlight ? 'border-amber-500/40' : ''}`} title={title}>
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="num text-sm">{value}</div>
    </div>
  )
}

const SectionLabel = ({ children }) => (
  <span className="text-[10px] uppercase tracking-wider text-slate-500">{children}</span>
)

const Kbd = ({ children }) => (
  <kbd className="rounded border px-1 font-mono text-[10px]">{children}</kbd>
)
