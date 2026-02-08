export const NAMESPACE = 'instant-coffee'

export const KEYS = {
  state: `${NAMESPACE}:state`,
  records: `${NAMESPACE}:records`,
  events: `${NAMESPACE}:events`,
}

export type EventType =
  | 'page_view'
  | 'click'
  | 'add_to_cart'
  | 'remove_from_cart'
  | 'checkout_start'
  | 'order_submitted'
  | 'payment_success'
  | 'save_plan'
  | 'share_link'
  | 'add_bookmark'
  | 'search'
  | 'reading_progress'
  | 'task_created'
  | 'task_moved'
  | 'task_completed'
  | 'lead_submitted'
  | 'cta_click'

export interface DataRecord {
  id: string
  type: string
  data: Record<string, any>
  timestamp: string
}

export interface DataEvent {
  id: string
  type: EventType
  timestamp: string
  payload: Record<string, any>
  page?: string
}

export interface DataStoreSnapshot {
  state: Record<string, any>
  records: DataRecord[]
  events: DataEvent[]
}

const memoryStore: DataStoreSnapshot = {
  state: {},
  records: [],
  events: [],
}

const isBrowser = typeof window !== 'undefined'

function safeParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value)
  } catch {
    return 'null'
  }
}

function generateId() {
  if (isBrowser && 'crypto' in window && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `id_${Math.random().toString(36).slice(2, 10)}`
}

export class DataStore {
  getSnapshot(): DataStoreSnapshot {
    if (!isBrowser) {
      return memoryStore
    }

    return {
      state: safeParse<Record<string, any>>(localStorage.getItem(KEYS.state), {}),
      records: safeParse<DataRecord[]>(localStorage.getItem(KEYS.records), []),
      events: safeParse<DataEvent[]>(localStorage.getItem(KEYS.events), []),
    }
  }

  setState(nextState: Record<string, any>) {
    const snapshot = this.getSnapshot()
    const updated = { ...snapshot.state, ...nextState }

    if (isBrowser) {
      localStorage.setItem(KEYS.state, safeStringify(updated))
    } else {
      memoryStore.state = updated
    }
  }

  clearState() {
    if (isBrowser) {
      localStorage.removeItem(KEYS.state)
    } else {
      memoryStore.state = {}
    }
  }

  addRecord(type: string, data: Record<string, any>) {
    const snapshot = this.getSnapshot()
    const record: DataRecord = {
      id: generateId(),
      type,
      data,
      timestamp: new Date().toISOString(),
    }

    const nextRecords = [...snapshot.records, record]
    if (isBrowser) {
      localStorage.setItem(KEYS.records, safeStringify(nextRecords))
    } else {
      memoryStore.records = nextRecords
    }

    return record
  }

  logEvent(type: EventType, payload: Record<string, any>, page?: string) {
    const snapshot = this.getSnapshot()
    const event: DataEvent = {
      id: generateId(),
      type,
      payload,
      page,
      timestamp: new Date().toISOString(),
    }

    const nextEvents = [...snapshot.events, event]
    if (isBrowser) {
      localStorage.setItem(KEYS.events, safeStringify(nextEvents))
    } else {
      memoryStore.events = nextEvents
    }

    return event
  }
}

export function initDataTabBridge(store: DataStore) {
  if (!isBrowser) return

  const allowedOrigin = new URL(document.referrer || location.origin).origin

  window.addEventListener('message', (event) => {
    if (event.origin !== allowedOrigin) return
    if (event.data?.type !== 'DATA_TAB_REQUEST') return

    const snapshot = store.getSnapshot()
    window.parent?.postMessage(
      {
        type: 'DATA_TAB_RESPONSE',
        payload: snapshot,
      },
      allowedOrigin
    )
  })
}
