import { Moon, Sun } from 'lucide-react'

export default function ThemeToggle({theme,onToggle}) {
  const dark = theme === 'dark'
  return <button
    type="button"
    onClick={onToggle}
    className="theme-toggle fixed right-4 top-4 z-[90] inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white/90 px-3 text-xs font-bold text-slate-600 shadow-lg shadow-slate-200/40 backdrop-blur hover:border-indigo-300 hover:text-indigo-600 sm:right-6 sm:top-5"
    aria-label={`Switch to ${dark ? 'light' : 'dark'} theme`}
    title={`Switch to ${dark ? 'light' : 'dark'} theme`}
  >
    {dark ? <Sun size={16}/> : <Moon size={16}/>}
    <span className="hidden sm:inline">{dark ? 'Light' : 'Dark'}</span>
  </button>
}
