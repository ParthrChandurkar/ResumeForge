import { LoaderCircle, LockKeyhole, MessageCircle, Send, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'

export default function RevisionChat({result,onUpdate}) {
  const [instruction,setInstruction]=useState(''),[target,setTarget]=useState('resume'),[loading,setLoading]=useState(false),[error,setError]=useState('')
  const messages=result.revision_messages||[]
  const submit=async(event)=>{
    event.preventDefault()
    if(instruction.trim().length<3||loading)return
    setLoading(true);setError('')
    try{const updated=await api.revise(result.id,instruction.trim(),target);setInstruction('');onUpdate(updated)}
    catch(err){setError(err.message)}finally{setLoading(false)}
  }
  return <aside className="no-print surface overflow-hidden 2xl:sticky 2xl:top-5">
    <div className="border-b border-slate-100 bg-gradient-to-br from-slate-950 to-indigo-950 p-5 text-white"><div className="flex items-center gap-2 text-sm font-black"><MessageCircle size={17}/> Refine with Gemini</div><p className="mt-2 text-xs leading-5 text-slate-300">Describe a text change and the tailored documents update immediately.</p><div className="mt-3 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-indigo-200"><LockKeyhole size={12}/> Layout and links locked</div></div>
    <div className="max-h-[360px] space-y-3 overflow-y-auto p-4">{messages.length?messages.map((message,index)=><div key={`${message.created_at}-${index}`} className={`rounded-xl px-3 py-2.5 text-xs leading-5 ${message.role==='user'?'ml-6 bg-indigo-600 text-white':'mr-6 bg-slate-100 text-slate-700'}`}><span className="mb-1 block text-[9px] font-black uppercase tracking-wider opacity-60">{message.role==='user'?'You':'Gemini'}</span>{message.content}</div>):<div className="py-6 text-center"><Sparkles className="mx-auto text-indigo-300" size={22}/><p className="mt-3 text-xs leading-5 text-slate-400">Try “Make the profile more concise” or “Emphasize AWS in the first two bullets.”</p></div>}</div>
    <form onSubmit={submit} className="border-t border-slate-100 p-4">{error&&<p className="mb-2 rounded-lg bg-red-50 p-2 text-[11px] leading-4 text-red-600">{error}</p>}<label><span className="label">Change</span><select value={target} onChange={event=>setTarget(event.target.value)} className="input mb-3 py-2.5 text-xs"><option value="resume">Resume only</option><option value="cover_letter">Cover letter only</option><option value="both">Both documents</option></select></label><textarea value={instruction} onChange={event=>setInstruction(event.target.value)} maxLength={2000} rows={4} className="input resize-none text-xs leading-5" placeholder="Tell Gemini exactly what to change…"/><button disabled={loading||instruction.trim().length<3} className="primary-btn mt-3 w-full">{loading?<LoaderCircle className="animate-spin" size={16}/>:<Send size={15}/>} {loading?'Applying changes…':'Apply changes'}</button><p className="mt-2 text-center text-[10px] leading-4 text-slate-400">Uses the same private Gemini configuration. Facts, structure and hyperlink positions stay protected.</p></form>
  </aside>
}
