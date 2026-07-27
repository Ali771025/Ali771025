import { create } from 'zustand'
import type { AlertRecord, Bootstrap, ControlIntent, LiveSnapshot, TopicEvent, TopicName, User } from './types'
import { api, bootstrap as loadBootstrap } from './lib/api'

interface State {
  user?: User; live: LiveSnapshot; history: TopicEvent[]; alerts: AlertRecord[]; intents: ControlIntent[]
  connected: boolean; lastMessageAt?: number; queueDrops: number; error?: string; socket?: WebSocket
  initialize: () => Promise<void>; connect: () => Promise<void>; disconnect: () => void
  refreshIntents: () => Promise<void>; refreshAlerts: () => Promise<void>
}

const emptyLive: LiveSnapshot = { topics: {}, transport: { received: 0, invalid: 0, sequence_gaps: 0, out_of_order: 0, subscribers: 0, uptime_ms: 0 } }

export const useFlightStore = create<State>((set, get) => ({
  live: emptyLive, history: [], alerts: [], intents: [], connected: false, queueDrops: 0,
  initialize: async () => {
    const data: Bootstrap = await loadBootstrap()
    set({ user: data.user, live: data.live, alerts: data.alerts, intents: data.control_intents })
    await get().connect()
  },
  connect: async () => {
    get().socket?.close()
    const { ticket } = await api<{ ticket: string }>('/api/v1/ws-ticket', { method: 'POST' })
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${scheme}//${location.host}/ws/live?ticket=${encodeURIComponent(ticket)}`)
    socket.onopen = () => set({ connected: true, error: undefined })
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data)
      if (event.type === 'snapshot') {
        set({ live: event.data, lastMessageAt: Date.now() })
      } else if (event.type === 'topic_update') {
        const typed = event as TopicEvent & { client_queue_drops?: number }
        set((state) => ({
          live: { ...state.live, topics: { ...state.live.topics, [typed.topic as TopicName]: typed } },
          history: typed.topic === 'telemetry' ? [...state.history.slice(-299), typed] : state.history,
          lastMessageAt: Date.now(), queueDrops: typed.client_queue_drops || 0,
        }))
        if (typed.topic === 'alert') get().refreshAlerts()
      } else if (event.type === 'heartbeat') set({ lastMessageAt: Date.now() })
    }
    socket.onclose = () => {
      set({ connected: false })
      window.setTimeout(() => { if (get().user) get().connect().catch(() => undefined) }, 1800)
    }
    socket.onerror = () => set({ error: 'ارتباط زنده با سرویس قطع شد' })
    set({ socket })
  },
  disconnect: () => { get().socket?.close(); set({ socket: undefined, connected: false, user: undefined }) },
  refreshIntents: async () => set({ intents: await api<ControlIntent[]>('/api/v1/control/intents') }),
  refreshAlerts: async () => set({ alerts: await api<AlertRecord[]>('/api/v1/alerts') }),
}))

