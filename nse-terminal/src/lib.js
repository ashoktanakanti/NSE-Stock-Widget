import { useEffect, useRef, useState } from 'react'

// ---- Formatting (Indian conventions: lakh / crore, en-IN grouping) ----

const TWO_DP = { minimumFractionDigits: 2, maximumFractionDigits: 2 }

export function num(n) {
  return n == null ? '—' : Number(n).toLocaleString('en-IN', TWO_DP)
}

export function inr(n) {
  return n == null ? '—' : `₹${num(n)}`
}

export function pct(n) {
  if (n == null) return '—'
  return `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
}

/** Share volume: 1.2Cr (crore = 10^7), 3.4L (lakh = 10^5). */
export function vol(n) {
  n = Number(n) || 0
  if (n >= 1e7) return `${(n / 1e7).toFixed(2)}Cr`
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)}L`
  return n.toLocaleString('en-IN')
}

/** Market cap in rupees: ₹15.84L Cr above 1 lakh crore, else ₹12,345 Cr. */
export function cap(n) {
  n = Number(n) || 0
  if (!n) return '—'
  if (n >= 1e12) return `₹${(n / 1e12).toFixed(2)}L Cr`
  return `₹${(n / 1e7).toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr`
}

/** Tailwind text colour for a signed change. */
export function tone(n) {
  if (n > 0) return 'text-up'
  if (n < 0) return 'text-down'
  return 'text-slate-400'
}

// ---- Time ----

// Backend timestamps look like "YYYY-MM-DD HH:MM:SS+00:00"
export function parseTs(s) {
  return s ? new Date(String(s).replace(' ', 'T')) : null
}

export function istTime(d) {
  if (!d) return '—'
  return d.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  })
}

export function istDate(d) {
  if (!d) return '—'
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata' })
}

export function ago(d, now = Date.now()) {
  if (!d) return '—'
  const s = (now - d) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

/** Next n NSE sessions after a YYYY-MM-DD date (weekends skipped; holidays not modelled). */
export function nextSessions(date, n) {
  const out = []
  const d = new Date(`${date}T00:00:00Z`)
  while (out.length < n) {
    d.setUTCDate(d.getUTCDate() + 1)
    const weekday = d.getUTCDay()
    if (weekday !== 0 && weekday !== 6) out.push(d.toISOString().slice(0, 10))
  }
  return out
}

// ---- API ----

// Symbols like M&M.NS must travel as M%26M.NS
export const enc = (ticker) => encodeURIComponent(ticker)

export async function api(path, options) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

// ---- Hooks ----

/** useState persisted to localStorage (falls back to memory if storage is blocked). */
export function useLocal(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(key)) ?? initial
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // private mode / storage disabled: keep in-memory value
    }
  }, [key, value])
  return [value, setValue]
}

/** Previous value of a prop across renders (drives the price-tick flash). */
export function usePrev(value) {
  const ref = useRef(value)
  useEffect(() => {
    ref.current = value
  }, [value])
  return ref.current
}
