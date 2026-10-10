import {useEffect,useMemo,useRef,useState,useCallback} from 'react'
import Header from './components/Header';import StockTable from './components/StockTable';import Watchlist from './components/Watchlist'
import ForecastPanel from './components/ForecastPanel';import MobileNav from './components/MobileNav';import Breadth from './components/Breadth'
import Profile from './components/Profile';import {Warn} from './components/Icons';import {api,useLocal,parseTs,ago} from './lib'
const STALE_MS=10*60e3

export default function App(){
  const [quotes,setQuotes]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(null),[status,setStatus]=useState(null),[pending,setPending]=useState(false)
  const [query,setQuery]=useState(''),[sort,setSort]=useLocal('nse.sort',{key:'market_cap',dir:-1}),[tab,setTab]=useState('home'),[selected,setSelected]=useState(null),[sector,setSector]=useState(null)
  const [watch,setWatch]=useLocal('nse.watch',[]),search=useRef(null),lastRun=useRef(undefined)
  // Vite's proxy answers 500 when Flask is down, so 5xx reads as unreachable
  const load=useCallback(()=>api('/api/universe').then(d=>{setQuotes(d);setError(null)}).catch(e=>setError(!e.status||e.status>=500?'Cannot reach the API on :5001':`API returned ${e.status}`)).finally(()=>setLoading(false)),[])
  const poll=useCallback(()=>api('/api/status').then(s=>{setStatus(s)
    // Reload the universe whenever a pipeline run (manual, auto or startup) completes
    const f=s.refresh?.finished_at;if(lastRun.current!==undefined&&f!==lastRun.current){load();setPending(false)}lastRun.current=f}).catch(()=>{}),[load])
  const refreshing=pending||!!status?.refresh?.running
  useEffect(()=>{load();poll();const a=setInterval(load,60e3);return()=>clearInterval(a)},[load,poll])
  useEffect(()=>{const b=setInterval(poll,refreshing?1500:15e3);return()=>clearInterval(b)},[poll,refreshing])
  const refresh=async()=>{if(refreshing)return;setPending(true);try{await api('/api/refresh',{method:'POST'});poll()}catch(e){if(e.status!==409)setPending(false)}}
  const toggle=useCallback(t=>setWatch(w=>w.includes(t)?w.filter(x=>x!==t):[...w,t]),[setWatch])

  const rows=useMemo(()=>{const q=query.trim().toLowerCase(),{key,dir}=sort
    let r=quotes.filter(s=>!q||s.symbol.toLowerCase().includes(q)||(s.name||'').toLowerCase().includes(q))
    if(sector)r=r.filter(s=>s.sector===sector)
    if(tab==='watch')r=r.filter(s=>watch.includes(s.ticker))
    // Exact symbol hits float to the top while searching
    const exact=s=>q&&s.symbol.toLowerCase()===q?0:1
    return [...r].sort((a,b)=>exact(a)-exact(b)||(key==='symbol'?dir*a.symbol.localeCompare(b.symbol)
      :a[key]==null?1:b[key]==null?-1:dir*(a[key]-b[key])))},[quotes,query,sort,tab,watch,sector])
  const sel=quotes.find(q=>q.ticker===selected)

  const keys=useRef();keys.current={rows,selected,tab,query}
  useEffect(()=>{const k=e=>{const {rows,selected,query}=keys.current,typing=e.target.tagName==='INPUT'
    if(e.key==='Escape'){if(typing&&query)setQuery('');else if(typing)e.target.blur();else setSelected(null);return}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'||(!typing&&(e.key==='j'||e.key==='k'))){if(!rows.length)return;e.preventDefault()
      const i=rows.findIndex(r=>r.ticker===selected),d=e.key==='ArrowDown'||e.key==='j'?1:-1
      setSelected(rows[i<0?0:Math.max(0,Math.min(rows.length-1,i+d))].ticker);return}
    if(typing||e.metaKey||e.ctrlKey||e.altKey)return
    if(e.key==='/'){e.preventDefault();search.current?.focus()}
    else if(e.key==='s'&&selected)toggle(selected)
    else if(e.key==='r')refresh()
    else if(e.key==='w')setTab(t=>t==='watch'?'home':'watch')}
    addEventListener('keydown',k);return()=>removeEventListener('keydown',k)})

  const tp={rows,loading,sort,setSort,selected,onSelect:setSelected,watch,toggle}
  const asOf=parseTs(status?.last_quote_at),stale=status?.market?.open&&asOf&&Date.now()-asOf>STALE_MS
  const banners=[
    error&&quotes.length>0&&['warn',`${error}. Showing last loaded data.`,'Retry',load],
    status?.tickers_simulated>0&&['warn',`${status.tickers_simulated} stock(s) are showing simulated prices because Yahoo could not be reached when history was loaded. Marked SIM.`],
    stale&&['warn',`Market is open but the latest quote is ${ago(asOf)}. Live fetches may be failing.`,'Refresh',refresh],
  ].filter(Boolean)
  const blank=!loading&&quotes.length===0
  const panel=<ForecastPanel quote={sel} onClose={()=>setSelected(null)} watched={!!sel&&watch.includes(sel.ticker)} toggle={toggle}/>
  return(<div className="flex h-[100dvh] flex-col">
    <Header ref={search} query={query} setQuery={setQuery} status={status} refreshing={refreshing} onRefresh={refresh}/>
    {banners.map(([,msg,act,fn])=><div key={msg} className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/[.07] px-4 py-1.5 text-[11px] text-amber-200">
      <Warn className="h-3.5 w-3.5 shrink-0"/><span className="flex-1">{msg}</span>{act&&<button onClick={fn} className="rounded border border-amber-500/30 px-2 py-0.5 transition hover:bg-amber-500/10">{act}</button>}</div>)}
    {tab!=='profile'&&<Breadth quotes={quotes} sector={sector} setSector={setSector} onSelect={setSelected}/>}
    <div className="hidden border-b px-4 lg:flex">{[['home','All NSE'],['watch','★ Watchlist ('+watch.length+')'],['profile','Data']].map(([k,l])=>
      <button key={k} onClick={()=>setTab(k)} className={`border-b-2 px-3 py-2 text-xs transition ${tab===k?'border-up text-up':'border-transparent text-slate-500 hover:text-slate-200'}`}>{l}</button>)}</div>
    <main className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_400px] 2xl:grid-cols-[minmax(0,1fr)_460px]">
      <section className="min-h-0 overflow-y-auto pb-20 lg:border-r lg:pb-0">
        {blank?<Empty error={error} retry={load}/>
         :tab==='profile'?<Profile status={status} quotes={quotes} watch={watch} setWatch={setWatch}/>
         :tab==='analytics'?<><div className="lg:hidden">{sel?panel:<><div className="border-b px-4 py-3 text-xs text-slate-500">Pick a stock to see its chart and forecast.</div><StockTable {...tp}/></>}</div>
           <div className="hidden lg:block"><StockTable {...tp}/></div></>
         :tab==='watch'?<Watchlist {...tp}/>:<StockTable {...tp}/>}
      </section>
      <aside className={`${sel&&tab!=='analytics'?'fixed inset-0 z-40 flex flex-col bg-black/50 pt-16 backdrop-blur-[2px] lg:static lg:z-auto lg:bg-card lg:pt-0 lg:backdrop-blur-none':'hidden lg:block'} min-h-0 bg-card`}
        onClick={e=>e.target===e.currentTarget&&setSelected(null)}>
        <div className="min-h-0 flex-1 overflow-hidden rounded-t-2xl border-t lg:h-full lg:rounded-none lg:border-0">{panel}</div></aside>
    </main><MobileNav tab={tab} setTab={setTab} count={watch.length}/></div>)}

function Empty({error,retry}){return(<div className="mx-auto max-w-md p-10 text-sm text-slate-400">
  {error?<><div className="mb-2 flex items-center gap-2 font-semibold text-slate-200"><Warn className="text-amber-300"/>{error}</div>
    <p className="mb-3 text-xs text-slate-500">Start the backend from the project folder:</p></>
   :<><div className="mb-2 font-semibold text-slate-200">No market data yet</div><p className="mb-3 text-xs text-slate-500">The database is empty. Seed ~6 months of history, then start the API:</p></>}
  <pre className="mb-4 overflow-x-auto rounded-lg border bg-card p-3 font-mono text-[11px] leading-relaxed text-slate-300">python stock_extractor.py{'\n'}python app.py</pre>
  <button onClick={retry} className="rounded-lg border border-up/30 bg-up/10 px-3 py-1.5 font-mono text-xs text-up transition hover:bg-up/20 active:scale-95">Retry</button></div>)}
