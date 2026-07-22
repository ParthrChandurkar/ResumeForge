import { Building2, ExternalLink, LoaderCircle, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

export default function CompanyHistory({result,onUpdate}) {
  const [loading,setLoading]=useState(false),[error,setError]=useState('')
  const requested=useRef(false)
  const load=async()=>{
    if(loading)return
    setLoading(true);setError('')
    try{onUpdate(await api.companyResearch(result.id))}catch(err){setError(err.message)}finally{setLoading(false)}
  }
  useEffect(()=>{if(!result.company_research&&!requested.current){requested.current=true;load()}},[result.id])
  const data=result.company_research
  if(!data)return <EmptyState icon={Building2} loading={loading} error={error} onClick={load} label="Research company" text="Gemini is checking current web sources and building a company case study."/>
  const facts=[['Founded',data.founded],['Headquarters',data.headquarters],['CEO & leadership',data.ceo_leadership],['Industry',data.industry]]
  return <div className="space-y-5">
    <section className="surface p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-indigo-500">Company case study</p><h2 className="mt-1 font-display text-2xl font-black">{result.company_name}</h2></div><button onClick={load} disabled={loading} className="toolbar-btn">{loading?<LoaderCircle size={15} className="animate-spin"/>:<RefreshCw size={15}/>} Refresh</button></div><p className="mt-4 text-sm leading-7 text-slate-600">{data.overview}</p>{error&&<p className="mt-3 text-sm text-red-600">{error}</p>}</section>
    <div className="grid gap-4 sm:grid-cols-2">{facts.map(([label,value])=><Fact key={label} title={label} text={value}/>)}</div>
    <div className="grid gap-5 xl:grid-cols-2"><Fact title="What the company does" text={data.what_they_do}/><Fact title="Business model" text={data.business_model}/><List title="Products & services" items={data.products_services}/><List title="Technology & engineering" items={data.technology_stack}/><List title="Investors & ownership" items={data.investors_ownership}/><List title="Competitors" items={data.competitors}/><List title="Recent developments" items={data.recent_developments}/><List title="Culture & values" items={data.culture_and_values}/></div>
    <List title="Useful interview and application angles" items={data.interview_angles} accent/>
    <section className="surface p-6"><h3 className="font-display text-lg font-bold">Sources</h3><div className="mt-3 grid gap-2 sm:grid-cols-2">{data.sources?.length?data.sources.map((source,i)=><a key={`${source.url}-${i}`} href={source.url} target="_blank" rel="noreferrer" className="flex min-w-0 items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-indigo-600 hover:bg-indigo-50"><ExternalLink size={13} className="shrink-0"/><span className="truncate">{source.title||source.url}</span></a>):<p className="text-sm text-slate-400">No source links were returned.</p>}</div></section>
  </div>
}

function Fact({title,text}){return <section className="surface p-5"><h3 className="text-xs font-black uppercase tracking-[.12em] text-slate-400">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{text||'Not publicly disclosed'}</p></section>}
function List({title,items=[],accent=false}){return <section className={`surface p-5 ${accent?'border-indigo-200 bg-indigo-50/40':''}`}><h3 className="font-display text-lg font-bold">{title}</h3><ul className="mt-3 space-y-2">{items?.length?items.map((item,i)=><li key={i} className="flex gap-2 text-sm leading-6 text-slate-600"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500"/>{item}</li>):<li className="text-sm text-slate-400">Not publicly disclosed.</li>}</ul></section>}
export function EmptyState({icon:Icon,loading,error,onClick,label,text}){return <section className="surface grid min-h-[360px] place-items-center p-8 text-center"><div><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600"><Icon size={25}/></span><h2 className="mt-4 font-display text-xl font-bold">{loading?'Working on it…':label}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{error||text}</p><button onClick={onClick} disabled={loading} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-bold text-white disabled:opacity-60">{loading&&<LoaderCircle size={16} className="animate-spin"/>}{loading?'Generating…':label}</button></div></section>}
