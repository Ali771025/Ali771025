import { FormEvent, ReactNode, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, BarChart3, BatteryCharging, Bot, Check, ChevronLeft, CircleGauge,
  Crosshair, Database, Gauge, LogOut, Map, Navigation, Plane, Radio, Route, Satellite,
  Send, Settings2, ShieldAlert, ShieldCheck, Signal, SlidersHorizontal, Video, X, Zap,
} from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ackAlert, api, createIntent, decideIntent, setToken } from '../lib/api'
import { useFlightStore } from '../store'
import type { AlertRecord, ControlIntent, Telemetry, TopicEvent } from '../types'

type Tab = 'overview' | 'mission' | 'vision' | 'control' | 'alerts' | 'assistant'
const tabs: {id: Tab; label: string; icon: typeof Activity}[] = [
  { id: 'overview', label: 'نمای عملیات', icon: Activity }, { id: 'mission', label: 'مأموریت و مسیر', icon: Map },
  { id: 'vision', label: 'بینایی و ردیابی', icon: Video }, { id: 'control', label: 'کنترل پرواز', icon: SlidersHorizontal },
  { id: 'alerts', label: 'هشدارها', icon: AlertTriangle }, { id: 'assistant', label: 'دستیار هوشمند', icon: Bot },
]

const n = (value: unknown, fallback = 0) => typeof value === 'number' ? value : fallback
const format = (value: unknown, digits = 0) => n(value).toLocaleString('fa-IR', { maximumFractionDigits: digits })
const time = (value: number) => new Intl.DateTimeFormat('fa-IR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(value)

function StatusDot({ok}: {ok: boolean}) { return <span className={`status-dot ${ok ? 'ok' : 'bad'}`} /> }

function Section({title, action, children, className = ''}: {title: string; action?: ReactNode; children: ReactNode; className?: string}) {
  return <section className={`panel ${className}`}><header className="panel-header"><h3>{title}</h3>{action}</header>{children}</section>
}

function Kpi({label, value, unit, icon: Icon, tone = 'cyan', detail}: {label: string; value: string; unit?: string; icon: typeof Gauge; tone?: string; detail?: string}) {
  return <article className="kpi-card"><div className={`kpi-icon ${tone}`}><Icon size={19}/></div><div><span>{label}</span><strong>{value} <small>{unit}</small></strong>{detail && <em>{detail}</em>}</div></article>
}

function TelemetryChart({history}: {history: TopicEvent[]}) {
  const data = history.map(item => {
    const payload = item.payload as Telemetry
    return { time: time(item.received_at_ms), altitude: n(payload.relative_altitude_m), speed: n(payload.groundspeed_mps), battery: n(payload.battery_percent) }
  })
  return <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{top: 8, right: 4, left: -18, bottom: 0}}>
    <defs><linearGradient id="alt" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22d3ee" stopOpacity={.38}/><stop offset="95%" stopColor="#22d3ee" stopOpacity={0}/></linearGradient></defs>
    <CartesianGrid stroke="#1d3049" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="time" hide/><YAxis tick={{fill:'#6f829a',fontSize:10}} axisLine={false} tickLine={false}/>
    <Tooltip contentStyle={{background:'#0c192a',border:'1px solid #213653',borderRadius:10,direction:'rtl'}}/><Area type="monotone" dataKey="altitude" name="ارتفاع نسبی" stroke="#22d3ee" fill="url(#alt)" strokeWidth={2}/>
  </AreaChart></ResponsiveContainer></div>
}

function MissionMap({routes, telemetry}: {routes: Record<string, unknown>; telemetry: Telemetry}) {
  const items = Array.isArray(routes.routes) ? routes.routes as Array<Record<string, unknown>> : []
  const colors = ['#22d3ee','#f59e0b','#a78bfa']
  const polylines = items.slice(0,3).map((route, index) => {
    const points = Array.isArray(route.points) ? route.points as Array<Record<string, number>> : []
    return { id: String(route.id || index), color: colors[index], points: points.map(p => `${10 + n(p.x)*4.2},${90 - n(p.y)*3.6}`).join(' ') }
  })
  return <div className="map-stage">
    <svg viewBox="0 0 460 220" role="img" aria-label="نقشه مسیر مأموریت">
      <defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M 24 0 L 0 0 0 24" fill="none" stroke="#1d314a" strokeWidth=".8"/></pattern></defs>
      <rect width="460" height="220" fill="url(#grid)"/><path d="M10 156 C90 106 122 182 201 128 S350 88 460 112" fill="none" stroke="#16394d" strokeWidth="22" opacity=".7"/>
      <path d="M 80 30 L 152 54 L 135 115 L 63 102 Z M 285 125 L 354 146 L 331 203 L 272 182 Z" fill="#16283b" stroke="#28415d" strokeDasharray="4 3"/>
      {polylines.map(line => <polyline key={line.id} points={line.points || '28,184 90,155 168,128 245,102 340,62 420,36'} fill="none" stroke={line.color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity=".9"/>)}
      <g transform={`translate(${28 + (n(telemetry.mission_progress)*3.8)},${184 - n(telemetry.mission_progress)*1.45}) rotate(${n(telemetry.heading_deg)})`}><circle r="13" fill="#22d3ee" opacity=".14"/><path d="M0 -9 L6 8 L0 5 L-6 8 Z" fill="#67e8f9"/></g>
    </svg>
    <div className="map-legend"><span><i className="cyan-bg"/> مسیر منتخب</span><span><i className="amber-bg"/> جایگزین A*</span><span><Navigation size={13}/> پیشرفت {format(telemetry.mission_progress)}٪</span></div>
  </div>
}

function ModuleHealth({payload}: {payload: Record<string, unknown>}) {
  const defaults = { GPS: 'HEALTHY', IMU: 'HEALTHY', YOLO: 'HEALTHY', GStreamer: 'HEALTHY', RAG: 'READY', 'Knowledge Graph': 'READY' }
  const modules = Object.entries(Object.keys(payload).length ? payload : defaults)
  return <div className="module-list">{modules.slice(0,8).map(([name, value]) => { const ok = String(value).match(/HEALTHY|READY|ONLINE|true/i); return <div key={name}><StatusDot ok={Boolean(ok)}/><span>{name}</span><small>{String(value)}</small></div>})}</div>
}

function MediaPanel({vision}: {vision: Record<string, unknown>}) {
  const streamUrl = import.meta.env.VITE_VIDEO_STREAM_URL as string | undefined
  const tracks = Array.isArray(vision.tracks) ? vision.tracks as Array<Record<string, number|string>> : []
  return <div className="video-stage">
    {streamUrl ? <video src={streamUrl} autoPlay muted playsInline/> : <div className="video-placeholder"><Crosshair size={46}/><strong>ورودی ویدیو آماده اتصال</strong><span>WebRTC / HLS خروجی GStreamer</span></div>}
    {tracks.slice(0,12).map((track, index) => <div key={String(track.id || index)} className="track-box" style={{left:`${n(track.x)*100}%`,top:`${n(track.y)*100}%`,width:`${n(track.w,.15)*100}%`,height:`${n(track.h,.18)*100}%`}}><b>#{String(track.id || index)} {String(track.label || 'object')}</b></div>)}
    <div className="video-hud top">YOLO · TRACKING <StatusDot ok={true}/></div><div className="video-hud bottom">{tracks.length.toLocaleString('fa-IR')} مسیر فعال · {format(vision.fps,1)} FPS</div>
  </div>
}

function Alerts({alerts, full = false}: {alerts: AlertRecord[]; full?: boolean}) {
  const refresh = useFlightStore(state => state.refreshAlerts)
  async function acknowledge(id: string) { await ackAlert(id); await refresh() }
  const shown = full ? alerts : alerts.slice(0,4)
  return <div className="alert-list">{shown.length ? shown.map(alert => <article key={alert.id} className={`alert-item ${alert.severity.toLowerCase()}`}>
    <div className="alert-symbol">{alert.severity === 'CRITICAL' ? <ShieldAlert/> : <AlertTriangle/>}</div><div><strong>{alert.title}</strong><p>{alert.detail}</p><small>{alert.source} · {time(alert.created_at_ms)}</small></div>
    {alert.acknowledged_at_ms ? <span className="ack"><Check size={14}/> تأیید شد</span> : <button onClick={() => acknowledge(alert.id)}>بررسی شد</button>}
  </article>) : <div className="empty-state"><ShieldCheck/><span>هشدار فعالی وجود ندارد</span></div>}</div>
}

const actionLabels: Record<string,string> = { ARM:'مسلح‌سازی', DISARM:'خلع سلاح', TAKEOFF:'برخاست', HOLD:'توقف در موقعیت', RESUME_MISSION:'ادامه مأموریت', RETURN_TO_HOME:'بازگشت به خانه', LAND:'فرود', ABORT_MISSION:'لغو مأموریت' }

function ControlPanel({intents, role, full = false}: {intents: ControlIntent[]; role: string; full?: boolean}) {
  const refresh = useFlightStore(state => state.refreshIntents)
  const [selected, setSelected] = useState('HOLD'); const [reason, setReason] = useState('اقدام نظارت‌شده توسط تیم عملیات'); const [busy, setBusy] = useState(false); const [error,setError] = useState('')
  const actions = Object.keys(actionLabels)
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(''); try { await createIntent(selected, reason); await refresh() } catch(e) { setError(e instanceof Error ? e.message : 'فرمان ثبت نشد') } finally { setBusy(false) } }
  async function decide(id: string, decision: 'approve'|'cancel') { setBusy(true); try { await decideIntent(id, decision); await refresh() } catch(e) { setError(e instanceof Error ? e.message : 'عملیات ناموفق') } finally { setBusy(false) } }
  return <div className={`control-grid ${full ? 'full' : ''}`}>
    <form className="command-form" onSubmit={submit}><div className="safety-banner"><ShieldCheck/><div><strong>کنترل نظارت‌شده</strong><span>مدل هوشمند هیچ مجوز فرمان ندارد</span></div></div>
      <label>عملیات<select value={selected} onChange={e=>setSelected(e.target.value)}>{actions.map(action=><option value={action} key={action}>{actionLabels[action]}</option>)}</select></label>
      <label>دلیل عملیاتی<textarea value={reason} onChange={e=>setReason(e.target.value)} minLength={5}/></label>
      {error && <p className="form-error">{error}</p>}<button className="command-button" disabled={busy}>{busy ? 'در حال بررسی…' : 'ثبت درخواست کنترل'}</button><small>فرمان‌های بحرانی به تأیید مدیر پرواز نیاز دارند و پس از ۳۰ ثانیه منقضی می‌شوند.</small>
    </form>
    <div className="intent-list"><h4>گردش کار فرمان‌ها</h4>{intents.slice(0, full?12:5).map(intent=><article key={intent.id}><div><strong>{actionLabels[intent.action] || intent.action}</strong><span>{intent.reason}</span><small>{intent.requested_by} · {time(intent.created_at_ms)}</small></div><div className="intent-actions"><b className={`intent-status ${intent.status.toLowerCase()}`}>{intent.status}</b>{intent.status==='PENDING_APPROVAL' && role==='FLIGHT_MANAGER' && <><button onClick={()=>decide(intent.id,'approve')}><Check/></button><button onClick={()=>decide(intent.id,'cancel')}><X/></button></>}</div></article>)}</div>
  </div>
}

function ChatAssistant() {
  const [messages,setMessages] = useState<Array<{from:'user'|'model'; text:string; action?:string}>>([{from:'model',text:'برای تحلیل وضعیت پرواز، نقشه، هشدارها یا مسیر جایگزین سؤال کنید. پاسخ من فقط مشورتی است.'}])
  const [text,setText] = useState(''); const [conversationId,setConversationId] = useState<string>(); const [busy,setBusy] = useState(false)
  async function submit(event: FormEvent) { event.preventDefault(); if(!text.trim()||busy)return; const question=text; setText(''); setMessages(m=>[...m,{from:'user',text:question}]); setBusy(true); try { const result=await api<{conversation_id:string;answer:string;suggested_action:string}>('/api/v1/chat',{method:'POST',body:JSON.stringify({conversation_id:conversationId,message:question})}); setConversationId(result.conversation_id); setMessages(m=>[...m,{from:'model',text:result.answer,action:result.suggested_action}]) } catch(e) { setMessages(m=>[...m,{from:'model',text:e instanceof Error?e.message:'پاسخ دریافت نشد'}]) } finally {setBusy(false)} }
  return <div className="chat-shell"><div className="chat-notice"><ShieldCheck/> خروجی مدل مشورتی است و هرگز به درگاه کنترل ارسال نمی‌شود.</div><div className="messages">{messages.map((message,index)=><div key={index} className={`message ${message.from}`}><span>{message.from==='model'?<Bot/>:'شما'}</span><p>{message.text}</p>{message.action&&<b>پیشنهاد: {message.action}</b>}</div>)}{busy&&<div className="message model typing">در حال تحلیل شواهد زنده…</div>}</div><form onSubmit={submit} className="chat-form"><input value={text} onChange={e=>setText(e.target.value)} placeholder="مثلاً: ریسک‌های فعلی مأموریت چیست؟"/><button><Send/></button></form></div>
}

export default function Dashboard() {
  const {user,live,history,alerts,intents,connected,lastMessageAt,queueDrops,disconnect} = useFlightStore()
  const [tab,setTab] = useState<Tab>('overview'); const [mobileNav,setMobileNav]=useState(false)
  const telemetry = (live.topics.telemetry?.payload || {}) as Telemetry
  const assessment = (live.topics.flight_assessment?.payload || {}) as Record<string,unknown>
  const vision = (live.topics.vision?.payload || {}) as Record<string,unknown>
  const routes = (live.topics.route_candidates?.payload || {}) as Record<string,unknown>
  const modules = (live.topics.module_health?.payload || {}) as Record<string,unknown>
  const stale = !lastMessageAt || Date.now()-lastMessageAt>2500
  const risk = String(assessment.risk_level || (alerts.some(a=>a.severity==='CRITICAL'&&!a.acknowledged_at_ms)?'CRITICAL':'NOMINAL'))
  const pageTitle = tabs.find(item=>item.id===tab)?.label
  const chartHistory = useMemo(()=>history.length?history:(live.topics.telemetry?[live.topics.telemetry]:[]),[history,live.topics.telemetry])
  function logout(){ disconnect(); setToken(null) }
  return <div className="app-shell">
    <aside className={mobileNav?'open':''}><div className="sidebar-brand"><div className="brand-mark small"><Plane/></div><div><b>SAFE AUTONOMY</b><span>FLIGHT OPERATIONS</span></div><button onClick={()=>setMobileNav(false)}><X/></button></div>
      <nav>{tabs.map(item=><button key={item.id} className={tab===item.id?'active':''} onClick={()=>{setTab(item.id);setMobileNav(false)}}><item.icon/><span>{item.label}</span><ChevronLeft/></button>)}</nav>
      <div className="sidebar-system"><p><Database/> وضعیت سامانه</p><div><span>درگاه کنترل</span><b className="green">SIMULATION</b></div><div><span>پایگاه داده</span><b>SQLITE · WAL</b></div><div><span>اختیار مدل</span><b className="amber">ADVISORY</b></div></div>
      <button className="logout" onClick={logout}><LogOut/> خروج از سامانه</button>
    </aside>
    <main className="dashboard-main"><header className="topbar"><button className="mobile-menu" onClick={()=>setMobileNav(true)}><Settings2/></button><div><p className="eyebrow">مرکز فرماندهی پرواز</p><h1>{pageTitle}</h1></div><div className="topbar-status"><span className={`connection ${connected&&!stale?'online':'offline'}`}><StatusDot ok={connected&&!stale}/>{connected&&!stale?'داده زنده':'داده منقضی'}</span><span><Radio/> {format(live.topics.telemetry?.latency_ms)} ms</span><span><Signal/> افت {format(live.transport.sequence_gaps+queueDrops)}</span></div><div className="user-chip"><div>{user?.display_name}<small>{user?.role==='FLIGHT_MANAGER'?'سطح مدیر':'سطح کارشناس'}</small></div><b>{user?.display_name.charAt(0)}</b></div></header>
      <div className="content">
        {tab==='overview' && <><div className="kpi-grid"><Kpi label="وضعیت پرواز" value={String(assessment.phase || telemetry.flight_mode || 'STANDBY')} icon={Plane} tone="cyan" detail={`ریسک: ${risk}`}/><Kpi label="ارتفاع نسبی" value={format(telemetry.relative_altitude_m,1)} unit="m" icon={BarChart3} tone="violet" detail={`عمودی ${format(telemetry.vertical_speed_mps,1)} m/s`}/><Kpi label="سرعت زمینی" value={format(telemetry.groundspeed_mps,1)} unit="m/s" icon={Gauge} tone="blue" detail={`سمت ${format(telemetry.heading_deg)}°`}/><Kpi label="باتری" value={format(telemetry.battery_percent)} unit="٪" icon={BatteryCharging} tone={n(telemetry.battery_percent,100)<25?'red':'green'} detail={`${format(telemetry.battery_voltage_v,1)} V`}/><Kpi label="لینک داده" value={format(telemetry.link_quality)} unit="٪" icon={Signal} tone="amber" detail={`${format(telemetry.satellites)} ماهواره`}/></div>
          <div className="overview-grid"><Section title="نقشه و مسیر مأموریت" action={<span className="section-badge"><Route/> A* · {format((routes.routes as unknown[])?.length)} مسیر</span>} className="map-panel"><MissionMap routes={routes} telemetry={telemetry}/></Section><Section title="روند ارتفاع پرواز" action={<span className="muted">پنجره زنده</span>}><TelemetryChart history={chartHistory}/></Section><Section title="سلامت ماژول‌ها"><ModuleHealth payload={modules}/></Section><Section title="هشدارهای اولویت‌دار"><Alerts alerts={alerts}/></Section><Section title="فرمان‌های در انتظار" className="wide"><ControlPanel intents={intents} role={user!.role}/></Section></div></>}
        {tab==='mission' && <div className="page-grid two"><Section title="تحلیل نقشه و مسیرهای جایگزین"><MissionMap routes={routes} telemetry={telemetry}/></Section><Section title="وضعیت مأموریت"><div className="mission-summary"><CircleGauge/><strong>{format(telemetry.mission_progress)}٪</strong><span>پیشرفت مأموریت</span><dl><div><dt>فاز</dt><dd>{String(assessment.phase||'نامشخص')}</dd></div><div><dt>ریسک</dt><dd>{risk}</dd></div><div><dt>ETA</dt><dd>{format(assessment.eta_seconds)} ثانیه</dd></div><div><dt>مسیر منتخب</dt><dd>{String(routes.selected_route_id||'primary')}</dd></div></dl></div></Section><Section title="نمودار ارتفاع" className="wide"><TelemetryChart history={chartHistory}/></Section></div>}
        {tab==='vision' && <div className="page-grid two"><Section title="استریم دوربین و ردیابی" className="wide"><MediaPanel vision={vision}/></Section><Section title="خلاصه بینایی"><div className="vision-stats"><Kpi label="نرخ پردازش" value={format(vision.fps,1)} unit="FPS" icon={Zap}/><Kpi label="ردیابی فعال" value={format((vision.tracks as unknown[])?.length)} icon={Crosshair}/></div></Section><Section title="سلامت خط ویدیو"><ModuleHealth payload={{GStreamer:modules.GStreamer||'READY',YOLO:modules.YOLO||'READY',Tracker:modules.Tracker||'READY',Encoder:modules.Encoder||'READY'}}/></Section></div>}
        {tab==='control' && <div className="page-grid"><Section title="پنل کنترل پهپاد" action={<span className="section-badge amber"><ShieldCheck/> تأیید دومرحله‌ای</span>}><ControlPanel intents={intents} role={user!.role} full/></Section></div>}
        {tab==='alerts' && <div className="page-grid"><Section title="مرکز هشدار و رخداد" action={<span className="section-badge"><AlertTriangle/> {format(alerts.filter(a=>!a.acknowledged_at_ms).length)} باز</span>}><Alerts alerts={alerts} full/></Section></div>}
        {tab==='assistant' && <div className="page-grid"><Section title="گفت‌وگو با مدل تحلیل پرواز" action={<span className="section-badge amber"><Bot/> ADVISORY ONLY</span>}><ChatAssistant/></Section></div>}
      </div>
    </main>
  </div>
}
