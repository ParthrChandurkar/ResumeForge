import { Check, Clipboard, MessageSquareText, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { EmptyState } from './CompanyHistory'

export default function ShortMessage({result,onUpdate}){
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[copied,setCopied]=useState(false)
  const requested=useRef(false)
  const generate=async()=>{if(loading)return;setLoading(true);setError('');try{onUpdate(await api.shortMessage(result.id))}catch(err){setError(err.message)}finally{setLoading(false)}}
  useEffect(()=>{if(!result.short_message&&!requested.current){requested.current=true;generate()}},[result.id])
  const copy=async()=>{await navigator.clipboard.writeText(result.short_message);setCopied(true);setTimeout(()=>setCopied(false),1600)}
  if(!result.short_message)return <EmptyState icon={MessageSquareText} loading={loading} error={error} onClick={generate} label="Generate short message" text="Create a concise 4–5 line message for a company application form."/>
  return <section className="surface p-6 sm:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-indigo-500">Application form response</p><h2 className="mt-1 font-display text-2xl font-black">Short message</h2><p className="mt-1 text-sm text-slate-400">Evidence-based, role-specific, and ready to paste.</p></div><div className="flex gap-2"><button onClick={generate} disabled={loading} className="toolbar-btn"><RefreshCw size={15} className={loading?'animate-spin':''}/> Regenerate</button><button onClick={copy} className="toolbar-btn">{copied?<Check size={15} className="text-emerald-500"/>:<Clipboard size={15}/>} {copied?'Copied':'Copy'}</button></div></div>{error&&<p className="mt-4 text-sm text-red-600">{error}</p>}<div className="mt-7 whitespace-pre-line rounded-2xl border border-indigo-100 bg-indigo-50/50 p-6 text-[15px] leading-8 text-slate-700">{result.short_message}</div></section>
}
