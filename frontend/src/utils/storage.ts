import type { TripFormData, TripHistoryRecord, TripPlan } from '@/types'

const HISTORY_KEY = 'travel_agent.history.v1'
const MAX_HISTORY = 20

export function loadHistory(): TripHistoryRecord[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function persistHistory(records: TripHistoryRecord[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(records.slice(0, MAX_HISTORY)))
}

export function saveHistoryRecord(request: TripFormData, plan: TripPlan): TripHistoryRecord {
  const record: TripHistoryRecord = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    generated_at: new Date().toISOString(),
    destination: plan.city || request.city,
    travel_days: plan.days?.length || request.travel_days,
    request,
    plan
  }
  const next = [record, ...loadHistory()].slice(0, MAX_HISTORY)
  persistHistory(next)
  return record
}

export function deleteHistoryRecord(id: string) {
  persistHistory(loadHistory().filter(item => item.id !== id))
}

export function clearHistoryRecords() {
  localStorage.removeItem(HISTORY_KEY)
}

export function validateTripPlan(value: unknown): value is TripPlan {
  if (!value || typeof value !== 'object') return false
  const plan = value as TripPlan
  return Boolean(plan.city && plan.start_date && plan.end_date && Array.isArray(plan.days))
}

export function normalizeImportedPlan(payload: unknown): TripPlan | null {
  if (validateTripPlan(payload)) return payload
  if (payload && typeof payload === 'object') {
    const maybeResponse = payload as { data?: unknown; plan?: unknown }
    if (validateTripPlan(maybeResponse.data)) return maybeResponse.data
    if (validateTripPlan(maybeResponse.plan)) return maybeResponse.plan
  }
  return null
}

export function requestFromPlan(plan: TripPlan): TripFormData {
  return {
    city: plan.city,
    start_date: plan.start_date,
    end_date: plan.end_date,
    travel_days: plan.days.length || 1,
    transportation: plan.days[0]?.transportation || '公共交通',
    accommodation: plan.days[0]?.accommodation || '舒适型酒店',
    preferences: [],
    free_text_input: '从历史记录或JSON导入恢复'
  }
}
