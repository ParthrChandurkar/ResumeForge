import { useCallback, useEffect, useState } from 'react'
import { Clock3, FilePlus2, FileText, FolderCog, History, LogOut, PanelLeftClose, Sparkles, UserRound } from 'lucide-react'
import { api } from './api'
import TailorForm from './components/TailorForm'
import ResultsPanel from './components/ResultsPanel'
import HistoryPanel from './components/HistoryPanel'
import Login from './components/Login'
import TemplateSetup from './components/TemplateSetup'
import ThemeToggle from './components/ThemeToggle'

const blankForm = { company_name: '', role_title: '', location: '', job_id: '', hiring_manager: '', template_id: '', job_description: '', extra_instructions: '' }

export default function App() {
  const [user, setUser] = useState(undefined)
  const [templates, setTemplates] = useState([])
  const [history, setHistory] = useState([])
  const [form, setForm] = useState(blankForm)
  const [result, setResult] = useState(null)
  const [view, setView] = useState('new')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('resumeforge_theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('resumeforge_theme', theme)
  }, [theme])
  const toggleTheme = () => setTheme(current => current === 'dark' ? 'light' : 'dark')

  const loadWorkspace = useCallback(async (currentUser) => {
    if (!currentUser) return
    try {
      const [templateData, historyData] = await Promise.all([api.templates(), api.history()])
      setTemplates(templateData); setHistory(historyData)
      const resumes = templateData.filter(item => item.kind === 'resume')
      setForm(current => ({ ...current, template_id: resumes.some(item => item.id === current.template_id) ? current.template_id : (resumes[0]?.id || '') }))
    } catch (err) { setError(err.message) }
  }, [])

  useEffect(() => { (async () => { try { const me = await api.auth.me(); setUser(me); await loadWorkspace(me) } catch { setUser(null) } })() }, [loadWorkspace])

  const onLogin = async (loggedIn) => { setUser(loggedIn); await loadWorkspace(loggedIn) }
  const refreshUser = async () => { const me = await api.auth.me(); setUser(me); await loadWorkspace(me) }
  const logout = async () => { try { await api.auth.logout() } finally { setUser(null); setTemplates([]); setHistory([]); setResult(null) } }

  const generate = async (event) => {
    event.preventDefault(); setLoading(true); setError('')
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, typeof value === 'string' && !value.trim() ? null : value]))
      for (const key of ['company_name', 'role_title', 'job_description', 'template_id']) payload[key] = form[key].trim()
      const data = await api.tailor(payload)
      setResult(data); setHistory(await api.history()); setView('result')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const openRun = async (id) => {
    setLoading(true); setError('')
    try { setResult(await api.run(id)); setView('result'); setSidebarOpen(false) }
    catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }
  const newTailor = () => { const resumes=templates.filter(item=>item.kind==='resume'); setForm({...blankForm,template_id:resumes[0]?.id||''}); setResult(null); setView('new'); setError(''); setSidebarOpen(false) }
  const deleteRun = async (id) => { if (!window.confirm('Delete this tailored document set from your private history?')) return; try { await api.deleteRun(id); setHistory(items => items.filter(item => item.id !== id)); if (result?.id === id) newTailor() } catch (err) { setError(err.message) } }

  if (user === undefined) return <><ThemeToggle theme={theme} onToggle={toggleTheme}/><div className="grid min-h-screen place-items-center bg-slate-950 text-white"><Sparkles className="animate-pulse" size={30}/></div></>
  if (!user) return <><ThemeToggle theme={theme} onToggle={toggleTheme}/><Login onLogin={onLogin}/></>
  if (!user.setup_complete) return <><ThemeToggle theme={theme} onToggle={toggleTheme}/><TemplateSetup user={user} templates={templates} onComplete={refreshUser} onLogout={logout}/></>

  return <><ThemeToggle theme={theme} onToggle={toggleTheme}/><div className="min-h-screen bg-[#f5f6f8] text-slate-950">
    {sidebarOpen && <button aria-label="Close sidebar" className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden" onClick={() => setSidebarOpen(false)} />}
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-[270px] flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="flex h-20 items-center gap-3 border-b border-slate-100 px-6"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 text-white"><FileText size={20}/></span><div><p className="font-display text-lg font-bold tracking-tight">ResumeForge</p><p className="text-[10px] font-bold uppercase tracking-[.22em] text-slate-400">Private studio</p></div><button className="ml-auto text-slate-400 lg:hidden" onClick={() => setSidebarOpen(false)}><PanelLeftClose size={19}/></button></div>
      <div className="p-4"><button onClick={newTailor} className="primary-btn w-full"><FilePlus2 size={17}/> New tailoring</button></div>
      <div className="px-3"><p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">Workspace</p><button onClick={newTailor} className={`nav-item ${view === 'new' ? 'nav-active' : ''}`}><Sparkles size={17}/> Tailor documents</button><button onClick={() => { setView('history'); setSidebarOpen(false) }} className={`nav-item ${view === 'history' ? 'nav-active' : ''}`}><History size={17}/> History <span className="ml-auto text-[11px] text-slate-400">{history.length}</span></button><button onClick={() => { setView('templates'); setSidebarOpen(false) }} className={`nav-item ${view === 'templates' ? 'nav-active' : ''}`}><FolderCog size={17}/> My templates</button></div>
      <div className="mt-6 min-h-0 flex-1 overflow-y-auto px-3 pb-4"><p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">Recent</p>{history.slice(0, 6).map(item => <button key={item.id} onClick={() => openRun(item.id)} className="group flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50"><Clock3 size={14} className="mt-1 shrink-0 text-slate-300"/><span className="min-w-0"><span className="block truncate text-xs font-bold text-slate-700">{item.role_title}</span><span className="mt-0.5 block truncate text-[11px] text-slate-400">{item.company_name}</span></span></button>)}</div>
      <div className="border-t border-slate-100 p-4"><div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-white text-slate-500"><UserRound size={17}/></span><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-slate-700">{user.name}</p><p className="truncate text-[10px] text-slate-400">{user.email}</p></div><button title="Sign out" onClick={logout} className="text-slate-400 hover:text-red-500"><LogOut size={16}/></button></div></div>
    </aside>
    <main className="min-h-screen lg:ml-[270px]"><header className="sticky top-0 z-30 flex h-16 items-center border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden"><button onClick={() => setSidebarOpen(true)} className="mr-3 rounded-lg p-2 text-slate-500 hover:bg-slate-100"><PanelLeftClose className="rotate-180" size={19}/></button><span className="font-display font-bold">ResumeForge</span></header>{error && <div className="fixed right-4 top-4 z-[80] max-w-md rounded-xl border border-red-200 bg-white p-4 text-sm text-red-700 shadow-xl lg:right-8"><button onClick={() => setError('')} className="float-right ml-4 text-red-400">×</button>{error}</div>}{view === 'new' && <TailorForm form={form} setForm={setForm} templates={templates.filter(item=>item.kind==='resume')} coverTemplate={templates.find(item=>item.kind==='cover_letter')} onSubmit={generate} loading={loading} />}{view === 'result' && result && <ResultsPanel result={result} onNew={newTailor} onResultUpdate={setResult} />}{view === 'history' && <HistoryPanel items={history} onOpen={openRun} onDelete={deleteRun} loading={loading} />}{view === 'templates' && <TemplateSetup user={user} templates={templates} onComplete={refreshUser} onLogout={logout} embedded/>}</main>
  </div></>
}
