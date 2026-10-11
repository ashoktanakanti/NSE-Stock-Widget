import { useLayoutEffect, useRef, useState } from 'react'
import { num, pct, inr, tone } from '../lib'
// Daily close line + dashed forecast with a widening ±MAE band, price axis, crosshair
export default function PriceChart({ bars, fc = [], fcDates = [], mae, height = 180 }) {
  const box = useRef(null)
  const [w, setW] = useState(0)
  const [hover, setHover] = useState(null)
  // Re-attach when the wrapper node changes (skeleton -> chart)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    setW(el.clientWidth)
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [bars.length < 2])
  if (bars.length < 2)
    return (
      <div ref={box}>
        <div className="skel" style={{ height }} />
      </div>
    )
  const P = { l: 4, r: 54, t: 8, b: 18 }
  const H = height
  const W = Math.max(w, 200)
  const band = fc.map((_, i) => (mae || 0) * Math.sqrt(i + 1))
  const vals = [
    ...bars.map((b) => b.price),
    ...fc.map((v, i) => v + band[i]),
    ...fc.map((v, i) => v - band[i]),
  ]
  let mn = Math.min(...vals)
  let mx = Math.max(...vals)
  const pad = (mx - mn || mx * 0.01) * 0.08
  mn -= pad
  mx += pad
  const n = bars.length + fc.length
  const x = (i) => P.l + (i / (n - 1)) * (W - P.l - P.r)
  const y = (v) => P.t + (1 - (v - mn) / (mx - mn)) * (H - P.t - P.b)
  const line = bars
    .map((b, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(b.price).toFixed(1)}`)
    .join('')
  const last = bars.length - 1
  const lp = bars[last].price
  const up = lp >= bars[0].price
  const c = up ? '#10b981' : '#ef4444'
  const fcLine = fc.length
    ? `M${x(last)},${y(lp)}` +
      fc.map((v, i) => `L${x(last + i + 1).toFixed(1)},${y(v).toFixed(1)}`).join('')
    : ''
  const bandPath = fc.length
    ? `M${x(last)},${y(lp)}` +
      fc.map((v, i) => `L${x(last + i + 1)},${y(v + band[i])}`).join('') +
      fc
        .map((_, j) => {
          const i = fc.length - 1 - j
          return `L${x(last + i + 1)},${y(fc[i] - band[i])}`
        })
        .join('') +
      'Z'
    : ''
  const ticks = Array.from({ length: 4 }, (_, i) => mn + ((mx - mn) * (i + 0.5)) / 4)
  const dates = [...bars.map((b) => b.date), ...fcDates]
  const xl = [0, Math.floor((n - 1) / 2), n - 1]
  const pts = [...bars.map((b) => b.price), ...fc]
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const i = Math.round(((e.clientX - r.left - P.l) / (W - P.l - P.r)) * (n - 1))
    setHover(Math.max(0, Math.min(n - 1, i)))
  }
  const hv = hover != null ? pts[hover] : null
  const isFc = hover != null && hover > last
  const fmtD = (d) =>
    d
      ? new Date(d + 'T00:00:00Z').toLocaleDateString('en-IN', {
          day: '2-digit',
          month: 'short',
          timeZone: 'UTC',
        })
      : ''
  return (
    <div ref={box} className="relative select-none">
      <svg
        width={W}
        height={H}
        className="block touch-none"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="pc-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={c} stopOpacity=".14" />
            <stop offset="1" stopColor={c} stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="rgba(255,255,255,.05)" />
            <text x={W - P.r + 6} y={y(t) + 3} className="fill-slate-500 font-mono text-[10px]">
              {num(t)}
            </text>
          </g>
        ))}
        {xl.map((i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 4}
            textAnchor={i ? (i === n - 1 ? 'end' : 'middle') : 'start'}
            className={`font-mono text-[10px] ${i > last ? 'fill-slate-400' : 'fill-slate-500'}`}
          >
            {fmtD(dates[i])}
          </text>
        ))}
        <path d={`${line}L${x(last)},${H - P.b}L${x(0)},${H - P.b}Z`} fill="url(#pc-fill)" />
        <path d={line} fill="none" stroke={c} strokeWidth="1.6" strokeLinejoin="round" />
        {bandPath && <path d={bandPath} fill="rgba(148,163,184,.10)" />}
        {fcLine && (
          <path d={fcLine} fill="none" stroke="#94a3b8" strokeWidth="1.6" strokeDasharray="4 3" />
        )}
        {fc.length > 0 && (
          <line
            x1={x(last)}
            x2={x(last)}
            y1={P.t}
            y2={H - P.b}
            stroke="rgba(255,255,255,.12)"
            strokeDasharray="2 3"
          />
        )}
        <line
          x1={P.l}
          x2={W - P.r}
          y1={y(lp)}
          y2={y(lp)}
          stroke={c}
          strokeOpacity=".35"
          strokeDasharray="1 3"
        />
        <rect x={W - P.r + 1} y={y(lp) - 8} width={P.r - 2} height={16} rx="3" fill={c} />
        <text
          x={W - P.r + 6}
          y={y(lp) + 3.5}
          className="fill-black font-mono text-[10px] font-bold"
        >
          {num(lp)}
        </text>
        {hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={P.t} y2={H - P.b} stroke="rgba(255,255,255,.3)" />
            <circle
              cx={x(hover)}
              cy={y(hv)}
              r="3.5"
              fill={isFc ? '#94a3b8' : c}
              stroke="#121620"
              strokeWidth="2"
            />
          </g>
        )}
      </svg>
      {hover != null && (
        <div
          className="pointer-events-none absolute top-1 rounded border bg-bg/95 px-2 py-1 font-mono text-[10px] shadow-lg"
          style={{ left: Math.min(Math.max(x(hover) - 60, 0), W - P.r - 120) }}
        >
          <span className="text-slate-500">
            {fmtD(dates[hover])}
            {isFc ? ' · fcst' : ''}
          </span>{' '}
          <span className="text-slate-100">{inr(hv)}</span>{' '}
          <span className={tone(hv - bars[0].price)}>{pct((hv / bars[0].price - 1) * 100)}</span>
        </div>
      )}
    </div>
  )
}
