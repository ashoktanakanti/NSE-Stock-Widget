import {pct,tone} from '../lib'
// Market breadth across the tracked universe + sector filter chips with avg 1D move
export default function Breadth({quotes,sector,setSector,onSelect}){
  if(!quotes.length)return null
  const ch=quotes.filter(q=>q.change_pct!=null)
  const adv=ch.filter(q=>q.change_pct>0).length,dec=ch.filter(q=>q.change_pct<0).length,flat=ch.length-adv-dec
  const avg=ch.reduce((s,q)=>s+q.change_pct,0)/(ch.length||1)
  const sorted=[...ch].sort((a,b)=>b.change_pct-a.change_pct),top=sorted[0],bot=sorted[sorted.length-1]
  const secs={};for(const q of ch)(secs[q.sector]??=[]).push(q.change_pct)
  const sectors=Object.entries(secs).map(([s,v])=>[s,v.reduce((a,b)=>a+b,0)/v.length,v.length]).sort((a,b)=>b[1]-a[1])
  const Mover=({q,l})=><button onClick={()=>onSelect(q.ticker)} className="flex items-baseline gap-1.5 rounded px-1 transition hover:bg-white/5">
    <span className="text-slate-500">{l}</span><span className="num font-semibold text-slate-200">{q.symbol}</span><span className={`num ${tone(q.change_pct)}`}>{pct(q.change_pct)}</span></button>
  return(<div className="border-b">
    <div className="flex items-center gap-x-5 gap-y-1 no-bar overflow-x-auto whitespace-nowrap px-4 py-2 text-[11px]">
      <div className="flex items-center gap-2">
        <span className="num text-up">{adv}▲</span>
        <div className="flex h-1.5 w-24 overflow-hidden rounded-full bg-white/5" title={`${adv} advancing · ${flat} unchanged · ${dec} declining`}>
          <div className="bg-up transition-all duration-500" style={{width:adv/ch.length*100+'%'}}/><div className="bg-slate-600" style={{width:flat/ch.length*100+'%'}}/><div className="bg-down transition-all duration-500" style={{width:dec/ch.length*100+'%'}}/></div>
        <span className="num text-down">{dec}▼</span></div>
      <div className="flex items-baseline gap-1.5"><span className="text-slate-500">Avg 1D</span><span className={`num font-semibold ${tone(avg)}`}>{pct(avg)}</span></div>
      {top&&<Mover q={top} l="Top"/>}{bot&&bot!==top&&<Mover q={bot} l="Worst"/>}
    </div>
    <div className="no-bar flex gap-1.5 overflow-x-auto px-4 pb-2">
      <Chip on={!sector} onClick={()=>setSector(null)}>All <span className="text-slate-500">{quotes.length}</span></Chip>
      {sectors.map(([s,a,n])=><Chip key={s} on={sector===s} title={`${n} stocks, average 1D move`} onClick={()=>setSector(sector===s?null:s)}>
        {s} <span className={`num ${tone(a)}`}>{pct(a)}</span></Chip>)}
    </div></div>)}
const Chip=({on,children,...p})=><button {...p} className={`shrink-0 rounded-md border px-2 py-1 text-[11px] transition active:scale-95 ${on?'border-up/50 bg-up/10 text-slate-100':'text-slate-400 hover:border-white/20 hover:text-slate-200'}`}>{children}</button>
