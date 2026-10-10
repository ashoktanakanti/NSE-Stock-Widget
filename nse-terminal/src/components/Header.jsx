import {forwardRef} from 'react'
import {Refresh} from './Icons'
import {istTime,parseTs,ago} from '../lib'
const Header=forwardRef(({query,setQuery,status,refreshing,onRefresh},ref)=>{
  const open=status?.market?.open,asOf=parseTs(status?.last_quote_at),checked=parseTs(status?.refresh?.finished_at)
  return(
<header className="sticky top-0 z-30 flex items-center gap-3 border-b bg-bg/90 px-4 py-3 backdrop-blur">
  <div className="shrink-0 font-mono text-sm font-bold tracking-wider">NSE<span className="text-up">/</span>TERMINAL</div>
  <div className="relative mx-auto w-full max-w-md">
    <input ref={ref} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search symbol or company" spellCheck={false}
      className="w-full rounded-lg border bg-card py-2 pl-3 pr-9 text-sm outline-none transition placeholder:text-slate-600 focus:border-up/60"/>
    {query?<button onClick={()=>setQuery('')} className="absolute right-2 top-1/2 -translate-y-1/2 px-1 text-xs text-slate-500 hover:text-slate-200" aria-label="Clear search">esc</button>
      :<kbd className="absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border px-1.5 font-mono text-[10px] text-slate-500 sm:block">/</kbd>}
  </div>
  {status&&<div className="hidden items-center gap-3 text-[11px] text-slate-500 md:flex" title={checked?'Last checked '+ago(checked):''}>
    <span className={`flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10px] tracking-wider ${open?'border-up/30 text-up':'text-slate-400'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${open?'animate-pulse bg-up':'bg-slate-500'}`}/>{open?'MARKET OPEN':'MARKET CLOSED'}</span>
    <span className="num">as of {asOf?asOf.toLocaleDateString('en-IN',{day:'2-digit',month:'short',timeZone:'Asia/Kolkata'})+' '+istTime(asOf):'—'} IST</span>
  </div>}
  <button onClick={onRefresh} disabled={refreshing} title="Fetch live quotes (r)"
    className="flex shrink-0 items-center gap-1.5 rounded-lg border border-up/30 bg-up/10 px-3 py-1.5 font-mono text-xs text-up transition hover:bg-up/20 active:scale-95 disabled:opacity-60">
    <Refresh className={`h-3.5 w-3.5 ${refreshing?'animate-spin':''}`}/><span className="hidden sm:inline">{refreshing?'Fetching':'Refresh'}</span></button>
</header>)})
export default Header
