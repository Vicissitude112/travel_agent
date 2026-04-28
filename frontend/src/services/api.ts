import axios from 'axios'
import type { TripFormData, TripPlanResponse } from '@/types'

const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const API_BASE_URL = configuredBaseUrl || 'http://127.0.0.1:8000'
const API_FALLBACK_BASE_URLS = Array.from(
  new Set([API_BASE_URL, 'http://127.0.0.1:8000', 'http://localhost:8000'])
)

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000, // 3分钟超时，考虑到生成旅行计划可能需要较长时间
  headers: {
    'Content-Type': 'application/json'
  }
})

function isNetworkError(error: any) {
  return !error.response && (error.code === 'ERR_NETWORK' || error.message === 'Network Error')
}

function formatApiError(error: any, baseUrl: string) {
  if (error.response?.data?.detail) return error.response.data.detail
  if (isNetworkError(error)) return `无法连接后端服务：${baseUrl}`
  return error.message || '请求失败'
}

async function requestWithNetworkFallback<T>(
  requestFactory: (baseUrl: string) => Promise<T>
): Promise<T> {
  let lastError: any = null

  for (const baseUrl of API_FALLBACK_BASE_URLS) {
    try {
      return await requestFactory(baseUrl)
    } catch (error: any) {
      lastError = error
      // 只有浏览器连不上服务时才换地址；后端已返回错误时直接抛出，避免重复生成行程。
      if (!isNetworkError(error)) {
        throw new Error(formatApiError(error, baseUrl))
      }
    }
  }

  throw new Error(
    `${formatApiError(lastError, API_FALLBACK_BASE_URLS[0])}。请确认 FastAPI 已启动，并检查 frontend/.env 的 VITE_API_BASE_URL。`
  )
}

export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  return requestWithNetworkFallback(async (baseUrl) => {
    const client = baseUrl === API_BASE_URL ? apiClient : axios.create({
      baseURL: baseUrl,
      timeout: 180000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    const response = await client.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  })
}

export async function healthCheck(): Promise<any> {
  return requestWithNetworkFallback(async (baseUrl) => {
    const client = baseUrl === API_BASE_URL ? apiClient : axios.create({ baseURL: baseUrl, timeout: 10000 })
    const response = await client.get('/health')
    return response.data
  })
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function proxiedImageUrl(url?: string | null, folder = 'default') {
  if (!url) return ''
  if (url.startsWith('data:') || url.startsWith('blob:')) return url
  if (url.startsWith(API_BASE_URL)) return url
  return `${API_BASE_URL}/api/poi/image-proxy?url=${encodeURIComponent(url)}&folder=${encodeURIComponent(folder)}`
}

export default apiClient
