import {useEffect,useState} from 'react'
import {api,parseTs,istDate,istTime,ago} from '../lib'
// Data-pipeline health, local preferences and keyboard shortcuts
export default function Profile({status,quotes,watch,setWatch}){
  const [log,setLog]=useState(null)
  useEffect(()=>{api('/api/log').then(setLog).catch(()=>setLog([]))},[status?.refresh?.finished_at])
  const r=status?.refresh||{},fin=parseTs(r.finished_at)
  const stat=[['Market',status?.market?.open?'Open':'Closed',status?.market?.open?'text-up':''],['Tracked',status?`${status.tickers_with_data}/${status.tickers_tracked}`:'—'],
    ['Simulated',status?.tickers_simulated??'—',status?.tickers_simulated?'text-amber-300':''],['Auto-refresh',status?`${status.auto_refresh_seconds}s, market hours`:'—'],
    ['Last fetch',fin?ago(fin):r.running?'running…':'—'],['Last result',r.ok!=null?`${r.ok} ok · ${r.err} failed`:'—',r.err?'text-amber-300':'']]
  return(<div className="mx-auto max-w-2xl space-y-6 p-4 lg:p-6">
    <Section title="Data pipeline"><div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-white/[.06] sm:grid-cols-3">
      {stat.map(([l,v,c])=><div key={l} className="bg-card px-3 py-2.5"><div className="text-[9px] uppercase tracking-wider text-slate-500">{l}</div><div className={`num text-sm ${c||''}`}>{v}</div></div>)}</div>
      <p className="mt-2 text-[11px] text-slate-600">Source: Yahoo Finance (delayed). Quotes are stamped with the exchange's last trade time.</p></Section>
    <Section title="Recent runs"><div className="overflow-hidden rounded-lg border">
      {log==null?<div className="skel m-2 h-20"/>:log.length===0?<div className="p-4 text-xs text-slate-500">No runs yet.</div>:
      log.map(l=>{const t=parseTs(l.run_at);return <div key={l.id} className="grid grid-cols-[1fr_auto_auto] gap-4 border-b px-3 py-2 text-xs last:border-0">
        <span className="num text-slate-400">{istDate(t)} {istTime(t)}</span><span className="num text-slate-500">{l.tickers_ok} ok · {l.tickers_err} err</span>
        <span className={`font-mono text-[10px] ${l.status==='OK'?'text-up':'text-amber-300'}`}>{l.status}</span></div>})}</div></Section>
    <Section title="Watchlist"><div className="flex items-center justify-between rounded-lg border px-3 py-2.5 text-xs">
      <span className="text-slate-400">{watch.length} of {quotes.length} stocks saved on this device</span>
      <button disabled={!watch.length} onClick={()=>confirm('Clear your watchlist?')&&setWatch([])} className="rounded border px-2 py-1 text-slate-400 transition hover:border-down/40 hover:text-down disabled:opacity-40">Clear</button></div></Section>
    <Section title="Keyboard"><div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-slate-400">
      {[['/','Search'],['Esc','Clear / close'],['↑ ↓  or  j k','Move selection'],['s','Star selected'],['r','Refresh quotes'],['w','Toggle watchlist view']].map(([k,l])=>
        <div key={l} className="flex justify-between gap-3"><span>{l}</span><kbd className="rounded border px-1.5 font-mono text-[10px] text-slate-500">{k}</kbd></div>)}</div></Section>
  </div>)}
const Section=({title,children})=><section><h2 className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">{title}</h2>{children}</section>
