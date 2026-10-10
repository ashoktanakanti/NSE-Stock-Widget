import {Home,Star,Chart,User} from './Icons'
const T=[['home',Home,'Home'],['watch',Star,'Watchlist'],['analytics',Chart,'Analytics'],['profile',User,'Profile']]
export default function MobileNav({tab,setTab,count}){return(
<nav className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-4 border-t bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
  {T.map(([k,Icon,l])=><button key={k} onClick={()=>setTab(k)} className={`relative flex flex-col items-center gap-0.5 py-2 text-[10px] transition active:scale-95 ${tab===k?'text-up':'text-slate-500'}`}>
    <Icon className="h-5 w-5"/>{l}
    {k==='watch'&&count>0&&<span className="num absolute left-1/2 top-1 ml-1.5 min-w-[16px] rounded-full bg-up px-1 text-center text-[9px] font-bold leading-4 text-black">{count}</span>}
    {tab===k&&<span className="absolute top-0 h-0.5 w-8 rounded-full bg-up"/>}</button>)}</nav>)}
