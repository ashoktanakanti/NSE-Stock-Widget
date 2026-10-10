import {memo,useEffect,useRef,useState} from 'react'
import {inr,pct,vol,cap,tone,usePrev} from '../lib'
import {Star} from './Icons'
// [key, label, visibility]: 'all' | 'md' (≥768) | 'xl' (≥1280)
const COLS=[['symbol','Symbol','all'],['spark','30D','xl'],['price','Price','all'],['change_pct','1D %','md'],['ret_1m','1M %','xl'],['volume','Volume','md'],['market_cap','Mkt Cap','md'],['range','3M Range','xl']]
const SORTABLE=new Set(['symbol','price','change_pct','ret_1m','volume','market_cap'])
const GRID='grid-cols-[28px_minmax(0,1fr)_auto] md:grid-cols-[28px_minmax(0,1.6fr)_1fr_.8fr_.9fr_1fr] xl:grid-cols-[28px_minmax(0,1.5fr)_84px_1fr_.75fr_.75fr_.8fr_1fr_104px]'
const vis={all:'',md:'hidden md:block',xl:'hidden xl:block'}

export default function StockTable({rows,loading,sort,setSort,selected,onSelect,watch,toggle,empty}){
  const head=k=>SORTABLE.has(k)&&setSort(s=>s.key===k?{key:k,dir:-s.dir}:{key:k,dir:k==='symbol'?1:-1})
  const arrow=k=>sort.key===k&&<span className="text-up">{sort.dir>0?' ▲':' ▼'}</span>
  if(loading)return <div className="space-y-px p-3">{Array.from({length:14},(_,i)=><div key={i} className="skel h-11" style={{opacity:1-i*.06}}/>)}</div>
  return(<div>
    <div className={`sticky top-0 z-10 hidden ${GRID} gap-2 border-b bg-bg/95 px-4 py-2 text-[10px] uppercase tracking-wider text-slate-500 backdrop-blur md:grid`}>
      <span/>{COLS.map(([k,l,v],i)=><button key={k} onClick={()=>head(k)} disabled={!SORTABLE.has(k)}
        className={`${vis[v]} ${i?'text-right':'text-left'} ${SORTABLE.has(k)?'hover:text-slate-200':'cursor-default'}`}>{l}{arrow(k)}</button>)}</div>
    <div className="no-bar flex gap-2 overflow-x-auto border-b px-4 py-2 md:hidden">
      {COLS.filter(([k])=>SORTABLE.has(k)).map(([k,l])=><button key={k} onClick={()=>head(k)} className={`shrink-0 rounded-full border px-3 py-1 text-xs transition active:scale-95 ${sort.key===k?'border-up/50 text-up':'text-slate-400'}`}>{l}{sort.key===k&&(sort.dir>0?' ▲':' ▼')}</button>)}</div>
    {rows.length===0&&(empty||<div className="p-10 text-center text-sm text-slate-500">No stocks match.</div>)}
    {rows.map(r=><Row key={r.ticker} r={r} on={watch.includes(r.ticker)} active={selected===r.ticker} onSelect={onSelect} toggle={toggle}/>)}
  </div>)}

const Row=memo(function Row({r,on,active,onSelect,toggle}){
  const el=useRef(null),prev=usePrev(r.price),[flash,setFlash]=useState('')
  useEffect(()=>{if(prev!=null&&r.price!==prev){setFlash(r.price>prev?'bg-up/15':'bg-down/15');const t=setTimeout(()=>setFlash(''),700);return()=>clearTimeout(t)}},[r.price,prev])
  useEffect(()=>{if(active)el.current?.scrollIntoView({block:'nearest'})},[active])
  return(
  <div ref={el} onClick={()=>onSelect(r.ticker)} role="row" aria-selected={active}
    className={`relative grid ${GRID} cursor-pointer items-center gap-2 border-b px-4 py-2.5 transition-colors duration-300 ${active?'bg-up/[.07]':'hover:bg-white/[.03]'} ${flash}`}>
    {active&&<span className="absolute inset-y-0 left-0 w-0.5 bg-up"/>}
    <button onClick={e=>{e.stopPropagation();toggle(r.ticker)}} className={`transition active:scale-125 ${on?'text-amber-400':'text-slate-600 hover:text-slate-300'}`} aria-label={on?'Remove from watchlist':'Add to watchlist'}><Star on={on}/></button>
    <div className="min-w-0"><div className="num flex items-center gap-1.5 text-sm font-bold">{r.symbol}{r.source==='simulated'&&<span className="rounded bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300" title="Simulated data: Yahoo fetch failed">SIM</span>}</div>
      <div className="truncate text-[11px] text-slate-500">{r.name}</div></div>
    <div className="hidden xl:block"><Spark data={r.spark}/></div>
    <div className="num text-right text-sm">{inr(r.price)}<div className={`text-[11px] md:hidden ${tone(r.change_pct)}`}>{pct(r.change_pct)}</div></div>
    <div className={`num hidden text-right text-sm md:block ${tone(r.change_pct)}`}>{pct(r.change_pct)}</div>
    <div className={`num hidden text-right text-xs xl:block ${tone(r.ret_1m)}`}>{pct(r.ret_1m)}</div>
    <div className="num hidden text-right text-xs text-slate-400 md:block">{vol(r.volume)}</div>
    <div className="num hidden text-right text-xs text-slate-400 md:block">{cap(r.market_cap)}</div>
    <div className="hidden xl:block"><Range lo={r.range3m_low} hi={r.range3m_high} v={r.price}/></div>
  </div>)})

function Spark({data}){
  if(!data||data.length<2)return null
  const mn=Math.min(...data),mx=Math.max(...data),W=84,H=24
  const pts=data.map((v,i)=>`${(i/(data.length-1)*W).toFixed(1)},${(H-2-(v-mn)/(mx-mn||1)*(H-4)).toFixed(1)}`).join(' ')
  return <svg viewBox={`0 0 ${W} ${H}`} className="ml-auto h-6 w-[84px]" preserveAspectRatio="none"><polyline points={pts} fill="none" stroke={data.at(-1)>=data[0]?'#10b981':'#ef4444'} strokeWidth="1.2" vectorEffect="non-scaling-stroke"/></svg>}

// Where today's price sits inside its 3-month low–high band
function Range({lo,hi,v}){
  if(lo==null||hi==null||v==null)return null
  const p=Math.min(100,Math.max(0,(v-lo)/((hi-lo)||1)*100))
  return(<div className="ml-auto w-[96px]" title={`3M low ${inr(lo)} · high ${inr(hi)}`}>
    <div className="relative h-1 rounded-full bg-white/10"><div className="absolute top-1/2 h-2.5 w-0.5 -translate-y-1/2 rounded bg-slate-200" style={{left:`calc(${p}% - 1px)`}}/></div>
    <div className="num mt-1 flex justify-between text-[9px] text-slate-600"><span>{Math.round(lo)}</span><span>{Math.round(hi)}</span></div></div>)}
