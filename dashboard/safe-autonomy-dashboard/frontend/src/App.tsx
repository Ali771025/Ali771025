import { FormEvent, useEffect, useState } from 'react'
import { Plane, Radio, ShieldCheck } from 'lucide-react'
import Dashboard from './components/Dashboard'
import { getToken, login, setToken } from './lib/api'
import { useFlightStore } from './store'

function Login() {
  const initialize = useFlightStore((state) => state.initialize)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await login(username, password); await initialize() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'ورود ناموفق بود'); setToken(null) }
    finally { setBusy(false) }
  }

  return <main className="login-shell">
    <section className="login-brand">
      <div className="brand-mark"><Plane size={32} /></div>
      <p className="eyebrow">SAFE AUTONOMY · FLIGHT OPS</p>
      <h1>مرکز یکپارچه<br />عملیات پرواز</h1>
      <p>پایش بلادرنگ، تحلیل مأموریت و کنترل نظارت‌شده برای تیم پرواز</p>
      <div className="login-features">
        <span><Radio size={17}/> تله‌متری کم‌تأخیر</span>
        <span><ShieldCheck size={17}/> کنترل دومرحله‌ای</span>
      </div>
    </section>
    <form className="login-card" onSubmit={submit}>
      <div><p className="eyebrow">ورود امن</p><h2>کنسول عملیات</h2><p className="muted">با حساب کارشناس یا مدیر پرواز وارد شوید.</p></div>
      <label>نام کاربری<input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" /></label>
      <label>گذرواژه<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" /></label>
      {error && <p className="form-error">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? 'در حال اتصال…' : 'ورود به داشبورد'}</button>
      <small>اطلاعات ورود پیش‌فرض فقط برای توسعه است و باید در استقرار تغییر کند.</small>
    </form>
  </main>
}

export default function App() {
  const user = useFlightStore((state) => state.user)
  const initialize = useFlightStore((state) => state.initialize)
  const [checked, setChecked] = useState(false)
  useEffect(() => {
    if (!getToken()) { setChecked(true); return }
    initialize().catch(() => setToken(null)).finally(() => setChecked(true))
  }, [initialize])
  if (!checked) return <div className="boot-screen"><span className="spinner"/> در حال برقراری ارتباط امن…</div>
  return user ? <Dashboard /> : <Login />
}

