// 16px stroke icons, currentColor
const I=({d,className='h-4 w-4',fill='none'})=><svg viewBox="0 0 24 24" className={className} fill={fill} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{d}</svg>
export const Home=p=><I {...p} d={<><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></>}/>
export const Star=({on,...p})=><I {...p} fill={on?'currentColor':'none'} d={<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>}/>
export const Chart=p=><I {...p} d={<><path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/></>}/>
export const Pulse=p=><I {...p} d={<path d="M3 12h4l3-8 4 16 3-8h4"/>}/>
export const Refresh=p=><I {...p} d={<><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></>}/>
export const Close=p=><I {...p} d={<path d="M6 6l12 12M18 6 6 18"/>}/>
export const Warn=p=><I {...p} d={<><path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/></>}/>
export const User=p=><I {...p} d={<><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></>}/>
