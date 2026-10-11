import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './lib'

const UNIVERSE_POLL_MS = 60_000
const STATUS_POLL_MS = 15_000
const STATUS_POLL_BUSY_MS = 2_000
const RETRY_MS = 5_000

function describeError(e) {
  // Vite's dev proxy answers 500 when Flask is down, so 5xx reads as unreachable
  return !e.status || e.status >= 500 ? 'Cannot reach the API' : `API returned ${e.status}`
}

/** Quotes for the whole universe plus pipeline status, kept fresh by polling. */
export function useMarketData() {
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState(null)
  const [pending, setPending] = useState(false)
  const lastRun = useRef(undefined)

  const load = useCallback(async () => {
    try {
      setQuotes(await api('/api/universe'))
      setError(null)
    } catch (e) {
      setError(describeError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const poll = useCallback(async () => {
    try {
      const s = await api('/api/status')
      setStatus(s)
      // Reload quotes whenever a pipeline run (manual, auto or startup) finishes
      const finished = s.refresh?.finished_at
      if (lastRun.current !== undefined && finished !== lastRun.current) {
        load()
        setPending(false)
      }
      lastRun.current = finished
    } catch {
      // Status is best-effort; load() reports connectivity errors
    }
  }, [load])

  const refreshing = pending || Boolean(status?.refresh?.running)
  const busy = refreshing || Boolean(status?.seeding)

  useEffect(() => {
    load()
    poll()
    const id = setInterval(load, UNIVERSE_POLL_MS)
    return () => clearInterval(id)
  }, [load, poll])

  // Retry quickly after a failed load (cold starts on free hosting, restarts)
  useEffect(() => {
    if (!error) return
    const id = setInterval(load, RETRY_MS)
    return () => clearInterval(id)
  }, [error, load])

  useEffect(() => {
    const id = setInterval(poll, busy ? STATUS_POLL_BUSY_MS : STATUS_POLL_MS)
    return () => clearInterval(id)
  }, [poll, busy])

  const refresh = useCallback(async () => {
    if (refreshing) return
    setPending(true)
    try {
      await api('/api/refresh', { method: 'POST' })
      poll()
    } catch (e) {
      if (e.status !== 409) setPending(false) // 409 = a run is already in progress
    }
  }, [refreshing, poll])

  return { quotes, loading, error, status, refreshing, load, refresh }
}

/**
 * Global shortcuts: / search, Esc clear/close, ↑↓ or j/k move, s star,
 * r refresh, w watchlist. Handlers are read through a ref so the listener
 * is attached once.
 */
export function useShortcuts(handlers) {
  const ref = useRef(handlers)
  ref.current = handlers

  useEffect(() => {
    function onKey(e) {
      const h = ref.current
      const typing = e.target.tagName === 'INPUT'

      if (e.key === 'Escape') {
        if (typing && h.query) h.clearQuery()
        else if (typing) e.target.blur()
        else h.clearSelection()
        return
      }

      const down = e.key === 'ArrowDown' || (!typing && e.key === 'j')
      const up = e.key === 'ArrowUp' || (!typing && e.key === 'k')
      if (down || up) {
        e.preventDefault()
        h.move(down ? 1 : -1)
        return
      }

      if (typing || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === '/') {
        e.preventDefault()
        h.focusSearch()
      } else if (e.key === 's') h.star()
      else if (e.key === 'r') h.refresh()
      else if (e.key === 'w') h.toggleWatchView()
    }

    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [])
}
