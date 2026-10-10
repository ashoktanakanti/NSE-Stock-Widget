import {useEffect,useState} from 'react'
import {api,enc,inr,pct,vol,cap,tone,num,nextSessions} from '../lib'
import {Close,Star,Warn} from './Icons'
import PriceChart from './PriceChart'
const RANGES=[['1M',22],['3M',63],['6M',130]]
const FEATURE_LABEL={lag_1:'Close t−1',lag_2:'Close t−2',lag_3:'Close t−3',rolling_mean_5:'5D mean',rolling_std_5:'5D volatility',change_pct:'1D change',return_1d:'1D return',volume_norm:'Volume'}

export default function ForecastPanel({quote,onClose,watched,toggle}){
  const [f,setF]=useState(null),[hist,setHist]=useState(null),[range,setRange]=useState(63)
  useEffect(()=>{if(!quote)return;setF(null);setHist(null);let live=true
    api('/api/predict/'+enc(quote.ticker)).then(d=>live&&setF(d)).catch(()=>live&&setF({error:'Forecast request failed. Is the API running?'}))
    api('/api/history/'+enc(quote.ticker)+'?limit=130').then(d=>live&&setHist(d)).catch(()=>live&&setHist([]))
    return()=>{live=false}},[quote?.ticker,quote?.fetched_at])
  if(!quote)return <div className="hidden h-full flex-col items-center justify-center gap-2 text-sm text-slate-500 lg:flex">
    <span>Select a stock for chart & forecast</span><span className="text-[11px] text-slate-600"><Kbd>↑</Kbd> <Kbd>↓</Kbd> to move · <Kbd>s</Kbd> to star</span></div>
  const fc=f?.forecasts||[],m=f?.metrics||{},bars=(hist||[]).slice(-range)
  const lastDate=hist?.length?hist.at(-1).date:null,fcDates=lastDate?nextSessions(lastDate,fc.length):[]
  const chg=quote.prev_close!=null?quote.price-quote.prev_close:null
  const imp=Object.entries(f?.feature_importance||{}),impMax=Math.max(...imp.map(([,v])=>v),1e-9)
  const tgt=fc.at(-1),tgtPct=tgt!=null&&f?.current_price?(tgt/f.current_price-1)*100:null
  return(<div className="h-full overflow-y-auto bg-card pb-24 animate-sheet lg:animate-none lg:pb-0">
    <div className="sticky top-0 z-10 flex items-start gap-3 border-b bg-card/95 p-4 backdrop-blur">
      <div className="min-w-0 flex-1"><div className="num flex items-center gap-2 text-lg font-bold">{quote.symbol}
        <span className="rounded bg-up/15 px-1.5 text-[10px] font-medium text-up">NSE</span>
        {quote.source==='simulated'&&<span className="rounded bg-amber-500/15 px-1.5 text-[10px] font-medium text-amber-300">SIMULATED</span>}
        <button onClick={()=>toggle(quote.ticker)} className={`transition active:scale-125 ${watched?'text-amber-400':'text-slate-600 hover:text-slate-300'}`} aria-label="Toggle watchlist"><Star on={watched}/></button></div>
        <div className="truncate text-xs text-slate-500">{quote.name} · {quote.sector}</div></div>
      <div className="text-right"><div className="num text-xl font-bold">{inr(quote.price)}</div>
        <div className={`num text-xs ${tone(quote.change_pct)}`}>{chg!=null&&(chg>=0?'+':'')+num(chg)} ({pct(quote.change_pct)})</div></div>
      <button onClick={onClose} className="-mr-1 rounded p-1 text-slate-500 transition hover:bg-white/5 hover:text-white lg:hidden" aria-label="Close"><Close/></button></div>

    <div className="grid grid-cols-4 gap-px bg-white/[.06]">
      {[['Prev close',inr(quote.prev_close)],['Open',inr(quote.open_price)],['High',inr(quote.high_price),'text-up'],['Low',inr(quote.low_price),'text-down'],
        ['Volume',vol(quote.volume)],['Mkt cap',cap(quote.market_cap)],['P/E',quote.pe_ratio?Number(quote.pe_ratio).toFixed(1):'—'],['1M',pct(quote.ret_1m),tone(quote.ret_1m)]].map(([l,v,c])=>
      <div key={l} className="bg-card px-3 py-2"><div className="text-[9px] uppercase tracking-wider text-slate-500">{l}</div><div className={`num truncate text-[12px] font-semibold ${c||''}`}>{v}</div></div>)}</div>
    <W52 lo={quote.week52_low} hi={quote.week52_high} v={quote.price}/>

    <div className="border-t p-4">
      <div className="mb-2 flex items-center justify-between"><span className="text-[10px] uppercase tracking-wider text-slate-500">Daily close · dashed = forecast</span>
        <div className="flex rounded-md border p-0.5">{RANGES.map(([l,n])=><button key={l} onClick={()=>setRange(n)} className={`rounded px-2 py-0.5 font-mono text-[10px] transition ${range===n?'bg-white/10 text-slate-100':'text-slate-500 hover:text-slate-300'}`}>{l}</button>)}</div></div>
      <PriceChart bars={bars} fc={f?.error?[]:fc} fcDates={fcDates} mae={m.cv_mae}/></div>

    <div className="border-t p-4">
      <div className="mb-2 flex items-baseline justify-between"><span className="text-[10px] uppercase tracking-wider text-slate-500">5-session Ridge forecast</span>
        {tgtPct!=null&&<span className="text-[11px] text-slate-500">T+5 <span className={`num font-semibold ${tone(tgtPct)}`}>{pct(tgtPct)}</span></span>}</div>
      {!f&&<div className="space-y-1">{[0,1,2,3,4].map(i=><div key={i} className="skel h-8"/>)}</div>}
      {f?.error&&<div className="flex gap-2 rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300"><Warn className="mt-px h-3.5 w-3.5 shrink-0"/>{f.error}</div>}
      <div className="space-y-1">{fc.map((p,i)=>{const base=i?fc[i-1]:f.current_price,d=(p-base)/base*100,band=(m.cv_mae||0)*Math.sqrt(i+1)
        return <div key={i} className="grid animate-fade grid-cols-[44px_56px_1fr_auto_64px] items-center gap-2 rounded bg-white/[.03] px-3 py-1.5" style={{animationDelay:i*30+'ms',animationFillMode:'backwards'}}>
          <span className="font-mono text-[11px] text-slate-500">T+{i+1}</span><span className="text-[11px] text-slate-500">{fcDates[i]?new Date(fcDates[i]+'T00:00:00Z').toLocaleDateString('en-IN',{weekday:'short',day:'2-digit',timeZone:'UTC'}):''}</span>
          <span className="num text-sm font-semibold">{inr(p)}</span><span className="num text-[10px] text-slate-600">±{num(band)}</span><span className={`num text-right text-xs ${tone(d)}`}>{pct(d)}</span></div>})}</div>
      {f&&!f.error&&<>
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[['CV MAE',m.cv_mae!=null?'₹'+num(m.cv_mae):'—','Avg out-of-sample error per day'],['Train RMSE',m.train_rmse!=null?'₹'+num(m.train_rmse):'—','In-sample fit'],['Samples',m.n_samples??'—','Daily rows used']].map(([l,v,t])=>
            <div key={l} className="rounded border p-2" title={t}><div className="text-[9px] uppercase tracking-wider text-slate-500">{l}</div><div className="num text-sm">{v}</div></div>)}</div>
        {imp.length>0&&<div className="mt-4"><div className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">Feature weight (|coef|, scaled)</div>
          {imp.slice(0,5).map(([k,v])=><div key={k} className="grid grid-cols-[96px_1fr_44px] items-center gap-2 py-0.5 text-[11px]">
            <span className="text-slate-400">{FEATURE_LABEL[k]||k}</span><div className="h-1 rounded-full bg-white/5"><div className="h-1 rounded-full bg-slate-400 transition-all duration-500" style={{width:v/impMax*100+'%'}}/></div><span className="num text-right text-slate-500">{v.toFixed(1)}</span></div>)}</div>}
      </>}
      <p className="mt-4 text-[10px] leading-relaxed text-slate-600">Linear model on ~6 months of daily closes. Band = ±CV MAE·√t. Not investment advice.</p></div>
  </div>)}

function W52({lo,hi,v}){
  if(lo==null||hi==null)return null
  const p=Math.min(100,Math.max(0,(v-lo)/((hi-lo)||1)*100)),off=(v/hi-1)*100
  return(<div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-t px-4 py-2.5 text-[11px]">
    <span className="num text-slate-500">52W {num(lo)}</span>
    <div className="relative h-1 rounded-full bg-white/10"><div className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-slate-100 transition-all duration-500" style={{left:`calc(${p}% - 1px)`}}/></div>
    <span className="num text-slate-500">{num(hi)} <span className={tone(off)}>({pct(off)})</span></span></div>)}
const Kbd=({children})=><kbd className="rounded border px-1 font-mono text-[10px]">{children}</kbd>
