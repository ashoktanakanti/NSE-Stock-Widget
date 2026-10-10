import {useEffect,useRef,useState} from 'react'
export const sym=t=>(t||'').replace('.NS','')
export const inr=n=>n==null?'—':'₹'+Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})
export const num=n=>n==null?'—':Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})
export const pct=n=>n==null?'—':(n>=0?'+':'')+Number(n).toFixed(2)+'%'
export const vol=n=>{n=+n||0;return n>=1e7?(n/1e7).toFixed(2)+'Cr':n>=1e5?(n/1e5).toFixed(1)+'L':n.toLocaleString('en-IN')}
export const cap=n=>{n=+n||0;return !n?'—':n>=1e12?'₹'+(n/1e12).toFixed(2)+'L Cr':'₹'+(n/1e7).toLocaleString('en-IN',{maximumFractionDigits:0})+' Cr'}
export const tone=n=>n>0?'text-up':n<0?'text-down':'text-slate-400'
// M&M.NS must travel as M%26M.NS
export const enc=t=>encodeURIComponent(t)
export const api=async(p,o)=>{const r=await fetch(p,o);if(!r.ok){const e=new Error(r.status);e.status=r.status;throw e}return r.json()}
// Backend stores "YYYY-MM-DD HH:MM:SS+00:00"
export const parseTs=s=>s?new Date(String(s).replace(' ','T')):null
export const istTime=d=>d?d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'}):'—'
export const istDate=d=>d?d.toLocaleDateString('en-IN',{day:'2-digit',month:'short',timeZone:'Asia/Kolkata'}):'—'
export const ago=d=>{if(!d)return '—';const s=(Date.now()-d)/1e3;return s<60?'just now':s<3600?Math.floor(s/60)+'m ago':s<86400?Math.floor(s/3600)+'h ago':Math.floor(s/86400)+'d ago'}
// Next n NSE sessions after a YYYY-MM-DD date (weekends skipped; exchange holidays not modelled)
export const nextSessions=(date,n)=>{const out=[],d=new Date(date+'T00:00:00Z');while(out.length<n){d.setUTCDate(d.getUTCDate()+1);const w=d.getUTCDay();if(w&&w<6)out.push(d.toISOString().slice(0,10))}return out}
export function useLocal(key,init){
  const [v,setV]=useState(()=>{try{return JSON.parse(localStorage.getItem(key))??init}catch{return init}})
  useEffect(()=>{try{localStorage.setItem(key,JSON.stringify(v))}catch{}},[key,v]);return [v,setV]}
// Previous value of a prop across renders (for price-tick flashes)
export function usePrev(v){const r=useRef(v);useEffect(()=>{r.current=v},[v]);return r.current}
