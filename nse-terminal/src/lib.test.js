import { describe, expect, it } from 'vitest'
import { ago, cap, enc, nextSessions, pct, vol } from './lib'

describe('formatters', () => {
  it('formats volume in lakh and crore', () => {
    expect(vol(12_100_000)).toBe('1.21Cr')
    expect(vol(336_000)).toBe('3.4L')
    expect(vol(950)).toBe('950')
  })

  it('formats market cap', () => {
    expect(cap(15_837_053_321_216)).toBe('₹15.84L Cr')
    expect(cap(120_630_000_000)).toBe('₹12,063 Cr')
    expect(cap(null)).toBe('—')
  })

  it('signs percentages', () => {
    expect(pct(1.234)).toBe('+1.23%')
    expect(pct(-0.5)).toBe('-0.50%')
    expect(pct(null)).toBe('—')
  })

  it('URL-encodes symbols with ampersands', () => {
    expect(enc('M&M.NS')).toBe('M%26M.NS')
  })
})

describe('time helpers', () => {
  it('skips weekends when listing the next sessions', () => {
    // 2026-10-09 is a Friday
    expect(nextSessions('2026-10-09', 3)).toEqual(['2026-10-12', '2026-10-13', '2026-10-14'])
  })

  it('describes elapsed time', () => {
    const now = Date.UTC(2026, 0, 1, 12)
    expect(ago(now - 30_000, now)).toBe('just now')
    expect(ago(now - 5 * 60_000, now)).toBe('5m ago')
    expect(ago(now - 3 * 86_400_000, now)).toBe('3d ago')
  })
})
