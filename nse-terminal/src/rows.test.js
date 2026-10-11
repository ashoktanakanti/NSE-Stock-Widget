import { describe, expect, it } from 'vitest'
import { compareRows, visibleRows } from './rows'

const q = (symbol, extra = {}) => ({ symbol, ticker: `${symbol}.NS`, name: symbol, ...extra })
const symbols = (rows) => rows.map((r) => r.symbol)

const quotes = [
  q('ITC', { price: 266, change_pct: 4.3, sector: 'FMCG' }),
  q('TCS', { price: 2156, change_pct: -6.1, sector: 'IT' }),
  q('INFY', { price: 1023, change_pct: 1.2, sector: 'IT' }),
  q('NEWCO', { price: 50, change_pct: null, sector: 'IT' }),
]

describe('sorting', () => {
  it('biggest movers ranks by absolute 1D change', () => {
    const rows = visibleRows(quotes, { sort: { key: 'move', dir: -1 } })
    expect(symbols(rows)).toEqual(['TCS', 'ITC', 'INFY', 'NEWCO'])
  })

  it('price low to high and high to low', () => {
    expect(symbols(visibleRows(quotes, { sort: { key: 'price', dir: 1 } }))).toEqual([
      'NEWCO',
      'ITC',
      'INFY',
      'TCS',
    ])
    expect(symbols(visibleRows(quotes, { sort: { key: 'price', dir: -1 } }))[0]).toBe('TCS')
  })

  it('missing values sink to the bottom in both directions', () => {
    for (const dir of [1, -1]) {
      const rows = visibleRows(quotes, { sort: { key: 'change_pct', dir } })
      expect(rows.at(-1).symbol).toBe('NEWCO')
    }
  })

  it('A–Z uses symbol order', () => {
    expect(compareRows(q('A'), q('B'), { key: 'symbol', dir: 1 })).toBeLessThan(0)
  })
})

describe('filtering', () => {
  it('matches symbol or company name, case-insensitive', () => {
    const rows = visibleRows([q('SBIN', { name: 'State Bank of India' }), q('TCS')], {
      query: 'bank',
      sort: { key: 'symbol', dir: 1 },
    })
    expect(symbols(rows)).toEqual(['SBIN'])
  })

  it('puts an exact symbol match first', () => {
    const rows = visibleRows([q('ITCHOTELS', { price: 900 }), q('ITC', { price: 266 })], {
      query: 'itc',
      sort: { key: 'price', dir: -1 },
    })
    expect(rows[0].symbol).toBe('ITC')
  })

  it('combines sector and watchlist filters', () => {
    const rows = visibleRows(quotes, {
      sector: 'IT',
      watchOnly: true,
      watch: ['INFY.NS', 'ITC.NS'],
      sort: { key: 'symbol', dir: 1 },
    })
    expect(symbols(rows)).toEqual(['INFY'])
  })
})
