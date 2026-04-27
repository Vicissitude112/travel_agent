<template>
  <div class="result-page">
    <template v-if="tripPlan">
      <header class="result-header">
        <div>
          <a-button @click="goBack">
            <ArrowLeftOutlined />
            返回
          </a-button>
          <h1>{{ tripPlan.city }}旅行方案</h1>
          <p>{{ tripPlan.start_date }} 至 {{ tripPlan.end_date }} · {{ tripPlan.days.length }}天</p>
        </div>
        <a-space wrap>
          <a-button v-if="!editMode" @click="toggleEditMode">
            <EditOutlined />
            编辑
          </a-button>
          <a-button v-if="editMode" type="primary" @click="saveChanges">
            <SaveOutlined />
            保存
          </a-button>
          <a-button v-if="editMode" @click="cancelEdit">
            <CloseOutlined />
            取消
          </a-button>
          <a-button @click="triggerImport">
            <UploadOutlined />
            导入 JSON
          </a-button>
          <a-dropdown>
            <template #overlay>
              <a-menu>
                <a-menu-item key="json" @click="exportAsJson">
                  <CodeOutlined />
                  导出 JSON
                </a-menu-item>
                <a-menu-item key="image" @click="exportAsImage">
                  <FileImageOutlined />
                  导出图片
                </a-menu-item>
                <a-menu-item key="pdf" @click="exportAsPDF">
                  <FilePdfOutlined />
                  导出 PDF
                </a-menu-item>
              </a-menu>
            </template>
            <a-button type="primary">
              <DownloadOutlined />
              导出
            </a-button>
          </a-dropdown>
        </a-space>
        <input ref="fileInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="handleImportFile" />
      </header>

      <main class="result-layout">
        <nav class="quick-nav export-skip">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="{ active: activeSection === item.id }"
            type="button"
            @click="scrollToSection(item.id)"
          >
            {{ item.label }}
          </button>
          <div v-if="dayNavItems.length" class="day-nav">
            <button
              v-for="item in dayNavItems"
              :key="item.id"
              :class="{ active: activeSection === item.id }"
              type="button"
              @click="scrollToSection(item.id)"
            >
              {{ item.label }}
            </button>
          </div>
        </nav>

        <div id="trip-plan-content" class="export-layout">
          <section class="content-column">
            <a-card id="budget-summary" class="summary-card" :bordered="false">
              <div class="summary-grid">
                <div>
                  <span class="metric-label">目的地</span>
                  <strong>{{ tripPlan.city }}</strong>
                </div>
                <div>
                  <span class="metric-label">景点</span>
                  <strong>{{ attractionCount }}</strong>
                </div>
                <div>
                  <span class="metric-label">酒店</span>
                  <strong>{{ hotelCount }}</strong>
                </div>
                <div v-if="tripPlan.budget">
                  <span class="metric-label">预算</span>
                  <strong>¥{{ tripPlan.budget.total }}</strong>
                </div>
              </div>
              <p class="suggestion">{{ tripPlan.overall_suggestions }}</p>
            </a-card>

            <a-card v-if="tripPlan.budget" title="预算明细" :bordered="false">
              <div class="budget-grid">
                <div class="budget-item">
                  <span>门票</span>
                  <strong>¥{{ tripPlan.budget.total_attractions }}</strong>
                </div>
                <div class="budget-item">
                  <span>酒店</span>
                  <strong>¥{{ tripPlan.budget.total_hotels }}</strong>
                </div>
                <div class="budget-item">
                  <span>餐饮</span>
                  <strong>¥{{ tripPlan.budget.total_meals }}</strong>
                </div>
                <div class="budget-item">
                  <span>交通</span>
                  <strong>¥{{ tripPlan.budget.total_transportation }}</strong>
                </div>
              </div>
            </a-card>

            <a-card v-if="tripPlan.weather_info?.length" id="weather-summary" title="天气摘要" :bordered="false">
              <div class="weather-grid">
                <article v-for="weather in tripPlan.weather_info" :key="weather.date" class="weather-card">
                  <strong>{{ weather.date }}</strong>
                  <span>{{ weather.day_weather || '多云' }} / {{ weather.night_weather || '多云' }}</span>
                  <p>{{ weather.day_temp }}℃ - {{ weather.night_temp }}℃ · {{ weather.wind_direction }} {{ weather.wind_power }}</p>
                </article>
              </div>
            </a-card>

            <section id="daily-itinerary" class="days-section">
              <article
                v-for="(day, dayIdx) in tripPlan.days"
                :id="`day-${day.day_index + 1}`"
                :key="day.date"
                class="day-block"
              >
                <div class="day-title-row">
                  <div>
                    <span class="day-index">DAY {{ day.day_index + 1 }}</span>
                    <h2>{{ day.date }}</h2>
                  </div>
                  <span class="day-transport">{{ day.transportation }}</span>
                </div>
                <p class="day-desc">{{ day.description }}</p>

                <div class="attraction-grid">
                  <a-card
                    v-for="(attraction, attrIdx) in day.attractions"
                    :key="`${day.date}-${attraction.name}`"
                    class="place-card"
                    :bordered="false"
                  >
                    <div class="image-wrap">
                      <img
                        :src="placeImage(attraction)"
                        :data-export-src="originalPlaceImage(attraction)"
                        :data-export-label="attraction.name"
                        :alt="attraction.name"
                        loading="eager"
                        decoding="sync"
                        @error="handleImageError"
                      />
                      <span class="place-order">{{ attrIdx + 1 }}</span>
                      <span v-if="attraction.ticket_price" class="ticket">¥{{ attraction.ticket_price }}</span>
                    </div>
                    <div class="place-body">
                      <div class="place-head">
                        <h3>{{ attraction.name }}</h3>
                        <span v-if="attraction.rating" class="rating">{{ attraction.rating }}</span>
                      </div>
                      <p class="address">{{ attraction.address }}</p>
                      <p>{{ attraction.description }}</p>
                      <p v-if="attraction.recommendation_reason" class="reason">{{ attraction.recommendation_reason }}</p>
                      <span class="duration">{{ attraction.visit_duration }} 分钟</span>
                    </div>
                    <div v-if="editMode" class="edit-actions">
                      <a-button size="small" :disabled="attrIdx === 0" @click="moveAttraction(dayIdx, attrIdx, 'up')">
                        <ArrowUpOutlined />
                      </a-button>
                      <a-button size="small" :disabled="attrIdx === day.attractions.length - 1" @click="moveAttraction(dayIdx, attrIdx, 'down')">
                        <ArrowDownOutlined />
                      </a-button>
                      <a-button size="small" danger @click="deleteAttraction(dayIdx, attrIdx)">
                        <DeleteOutlined />
                      </a-button>
                    </div>
                  </a-card>
                </div>

                <div class="meal-grid">
                  <article v-for="meal in day.meals" :key="`${day.date}-${meal.type}`" class="meal-card">
                    <span>{{ mealLabel(meal.type) }}</span>
                    <strong>{{ meal.name }}</strong>
                    <p>{{ meal.description }}</p>
                    <small>{{ meal.address || '按当天路线就近安排' }} · ¥{{ meal.estimated_cost || 0 }} · {{ meal.source || 'rule' }}</small>
                  </article>
                </div>
              </article>
            </section>

            <section id="hotels-section" class="hotel-section">
              <a-card title="酒店推荐" :bordered="false">
                <p class="section-note">以下酒店为统一推荐，建议选择其中一处连续入住，避免每天换酒店造成时间损耗。</p>
                <div class="hotel-grid">
                  <article v-for="hotel in planHotels" :key="`${hotel.name}-${hotel.address}`" class="hotel-card">
                    <img
                      :src="hotelImage(hotel)"
                      :data-export-src="originalHotelImage(hotel)"
                      :data-export-label="hotel.name"
                      :alt="hotel.name"
                      loading="eager"
                      decoding="sync"
                      @error="handleImageError"
                    />
                    <div>
                      <span class="section-kicker">统一住宿推荐</span>
                      <h3>{{ hotel.name }}</h3>
                      <p>{{ hotel.address }}</p>
                      <div class="hotel-meta">
                        <span>{{ hotel.type }}</span>
                        <span>{{ hotel.price_range }}</span>
                        <span>{{ hotel.distance }}</span>
                        <span v-if="hotel.rating">评分 {{ hotel.rating }}</span>
                      </div>
                      <p class="reason">{{ hotel.recommendation_reason }}</p>
                    </div>
                  </article>
                </div>
                <a-empty v-if="!planHotels.length" description="暂无可用酒店推荐" />
              </a-card>
            </section>
          </section>

          <aside class="side-column">
            <div class="side-stack">
              <a-card title="行程地图" :bordered="false" class="map-card export-skip">
                <TripMap :plan="tripPlan" />
              </a-card>
              <a-card title="数据状态" :bordered="false" class="status-card">
                <div class="status-row">
                  <span>图片</span>
                  <strong>{{ imageSourceSummary }}</strong>
                </div>
                <div class="status-row">
                  <span>地图点位</span>
                  <strong>{{ tripPlan.map_data?.markers?.length || 0 }}</strong>
                </div>
                <div class="status-row">
                  <span>可导入导出</span>
                  <strong>JSON / 图片 / PDF</strong>
                </div>
              </a-card>
            </div>
          </aside>
        </div>
      </main>
    </template>

    <a-result v-else status="404" title="没有可展示的旅行方案" sub-title="请从首页生成方案，或导入JSON文件。">
      <template #extra>
        <a-space>
          <a-button type="primary" @click="goBack">返回首页</a-button>
          <a-button @click="triggerImport">导入 JSON</a-button>
        </a-space>
        <input ref="fileInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="handleImportFile" />
      </template>
    </a-result>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowUpOutlined,
  CloseOutlined,
  CodeOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  SaveOutlined,
  UploadOutlined
} from '@ant-design/icons-vue'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import TripMap from '@/components/TripMap.vue'
import type { Attraction, Hotel, TripPlan } from '@/types'
import { proxiedImageUrl } from '@/services/api'
import { normalizeImportedPlan, requestFromPlan, saveHistoryRecord } from '@/utils/storage'

const router = useRouter()
const tripPlan = ref<TripPlan | null>(null)
const originalPlan = ref<TripPlan | null>(null)
const editMode = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const activeSection = ref('budget-summary')

let observer: IntersectionObserver | null = null

const attractionCount = computed(() => tripPlan.value?.days.reduce((sum, day) => sum + day.attractions.length, 0) || 0)
const planHotels = computed<Hotel[]>(() => {
  if (!tripPlan.value) return []
  if (tripPlan.value.hotels?.length) return tripPlan.value.hotels
  const merged = new Map<string, Hotel>()
  tripPlan.value.days.forEach(day => {
    if (day.hotel) merged.set(`${day.hotel.name}-${day.hotel.address}`, day.hotel)
  })
  return Array.from(merged.values())
})
const hotelCount = computed(() => planHotels.value.length)
const dayNavItems = computed(() => tripPlan.value?.days.map(day => ({
  id: `day-${day.day_index + 1}`,
  label: `Day ${day.day_index + 1}`
})) || [])
const navItems = computed(() => {
  const items = [
    { id: 'budget-summary', label: '预算摘要' },
    { id: 'daily-itinerary', label: '每日行程' },
    { id: 'hotels-section', label: '酒店推荐' }
  ]
  if (tripPlan.value?.weather_info?.length) {
    items.splice(1, 0, { id: 'weather-summary', label: '天气摘要' })
  }
  return items
})
const imageSourceSummary = computed(() => {
  if (!tripPlan.value) return '-'
  const sources = new Set<string>()
  tripPlan.value.days.forEach(day => {
    day.attractions.forEach(item => item.image?.source && sources.add(item.image.source))
  })
  planHotels.value.forEach(hotel => hotel.image?.source && sources.add(hotel.image.source))
  return Array.from(sources).join(' / ') || 'default'
})

onMounted(() => {
  const raw = sessionStorage.getItem('tripPlan')
  if (raw) {
    try {
      tripPlan.value = JSON.parse(raw)
    } catch {
      sessionStorage.removeItem('tripPlan')
    }
  }
  refreshObserver()
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

watch(tripPlan, () => refreshObserver(), { deep: true })

function goBack() {
  router.push('/')
}

function toggleEditMode() {
  originalPlan.value = clonePlan(tripPlan.value)
  editMode.value = true
}

function saveChanges() {
  if (!tripPlan.value) return
  editMode.value = false
  sessionStorage.setItem('tripPlan', JSON.stringify(tripPlan.value))
  saveHistoryRecord(requestFromPlan(tripPlan.value), tripPlan.value)
  message.success('修改已保存，并写入历史记录')
}

function cancelEdit() {
  tripPlan.value = clonePlan(originalPlan.value)
  editMode.value = false
}

function moveAttraction(dayIndex: number, attrIndex: number, direction: 'up' | 'down') {
  if (!tripPlan.value) return
  const attractions = tripPlan.value.days[dayIndex].attractions
  const nextIndex = direction === 'up' ? attrIndex - 1 : attrIndex + 1
  if (nextIndex < 0 || nextIndex >= attractions.length) return
  ;[attractions[attrIndex], attractions[nextIndex]] = [attractions[nextIndex], attractions[attrIndex]]
  tripPlan.value.map_data = null
}

function deleteAttraction(dayIndex: number, attrIndex: number) {
  if (!tripPlan.value) return
  const attractions = tripPlan.value.days[dayIndex].attractions
  if (attractions.length <= 1) {
    message.warning('每天至少保留一个景点')
    return
  }
  attractions.splice(attrIndex, 1)
  tripPlan.value.map_data = null
}

function placeImage(attraction: Attraction) {
  return originalPlaceImage(attraction) || placeholderDataUri(attraction.name)
}

function hotelImage(hotel: Hotel) {
  return originalHotelImage(hotel) || placeholderDataUri(hotel.name)
}

function originalPlaceImage(attraction: Attraction) {
  return attraction.image_url || attraction.image?.url || ''
}

function originalHotelImage(hotel: Hotel) {
  return hotel.image_url || hotel.image?.url || ''
}

function placeholderDataUri(label: string) {
  const safeLabel = escapeXml((label || 'Travel').slice(0, 18))
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">
      <rect width="960" height="600" fill="#e2e8f0"/>
      <text x="480" y="306" fill="#334155" font-family="Arial, sans-serif" font-size="44" font-weight="700" text-anchor="middle">${safeLabel}</text>
    </svg>
  `
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function escapeXml(value: string) {
  return value.replace(/[<>&'"]/g, char => ({
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;',
    "'": '&apos;',
    '"': '&quot;'
  }[char] || char))
}

function handleImageError(event: Event) {
  const img = event.target as HTMLImageElement
  if (img.dataset.fallbackApplied === 'true') return
  img.dataset.fallbackApplied = 'true'
  img.src = placeholderDataUri(img.alt || 'Travel')
}

function mealLabel(type: string) {
  const labels: Record<string, string> = {
    breakfast: '早餐',
    lunch: '午餐',
    dinner: '晚餐',
    snack: '小吃'
  }
  return labels[type] || type
}

function clonePlan(plan: TripPlan | null): TripPlan | null {
  return plan ? JSON.parse(JSON.stringify(plan)) : null
}

function refreshObserver() {
  observer?.disconnect()
  observer = null
  nextTick(() => {
    const ids = [...navItems.value.map(item => item.id), ...dayNavItems.value.map(item => item.id)]
    observer = new IntersectionObserver(
      entries => {
        const visible = entries
          .filter(entry => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) activeSection.value = visible[0].target.id
      },
      { rootMargin: '-18% 0px -68% 0px', threshold: [0.1, 0.4, 0.7] }
    )
    ids.forEach(id => {
      const element = document.getElementById(id)
      if (element) observer?.observe(element)
    })
  })
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  activeSection.value = id
}

function exportAsJson() {
  if (!tripPlan.value) return
  const payload = {
    schema_version: 'travel_agent.trip_plan.v3',
    exported_at: new Date().toISOString(),
    data: tripPlan.value
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  downloadBlob(blob, `${tripPlan.value.city}-旅行方案.json`)
}

async function exportAsImage() {
  if (!tripPlan.value) return
  const element = document.getElementById('trip-plan-content')
  if (!element) return
  let restoreImages = () => {}
  try {
    message.loading({ content: '正在加载图片并生成导出图...', key: 'export', duration: 0 })
    document.body.classList.add('exporting-trip')
    restoreImages = await prepareExportElement(element)
    const canvas = await renderExportCanvas(element)
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('浏览器未能生成PNG文件')
    downloadBlob(blob, `${tripPlan.value.city}-旅行方案.png`)
    message.success({ content: '图片导出成功', key: 'export' })
  } catch (error: any) {
    message.error({ content: `图片导出失败：${error.message || '请检查图片源是否可访问'}`, key: 'export' })
  } finally {
    restoreImages()
    document.body.classList.remove('exporting-trip')
  }
}

async function exportAsPDF() {
  if (!tripPlan.value) return
  const element = document.getElementById('trip-plan-content')
  if (!element) return
  let restoreImages = () => {}
  try {
    message.loading({ content: '正在加载图片并生成PDF...', key: 'export', duration: 0 })
    document.body.classList.add('exporting-trip')
    restoreImages = await prepareExportElement(element)
    const canvas = await renderExportCanvas(element)
    const pdf = new jsPDF('p', 'mm', 'a4')
    const pageWidth = 210
    const pageHeight = 297
    const imageHeight = (canvas.height * pageWidth) / canvas.width
    const imageData = canvas.toDataURL('image/png')

    let position = 0
    let heightLeft = imageHeight
    pdf.addImage(imageData, 'PNG', 0, position, pageWidth, imageHeight)
    heightLeft -= pageHeight
    while (heightLeft > 0) {
      position = heightLeft - imageHeight
      pdf.addPage()
      pdf.addImage(imageData, 'PNG', 0, position, pageWidth, imageHeight)
      heightLeft -= pageHeight
    }

    pdf.save(`${tripPlan.value.city}-旅行方案.pdf`)
    message.success({ content: 'PDF导出成功', key: 'export' })
  } catch (error: any) {
    message.error({ content: `PDF导出失败：${error.message || '请检查图片源是否可访问'}`, key: 'export' })
  } finally {
    restoreImages()
    document.body.classList.remove('exporting-trip')
  }
}

async function prepareExportElement(element: HTMLElement) {
  await nextTick()
  const images = Array.from(element.querySelectorAll('img')) as HTMLImageElement[]
  const snapshots = images.map(img => ({
    img,
    src: img.getAttribute('src') || '',
    fallbackApplied: img.dataset.fallbackApplied
  }))
  await Promise.all(images.map(async img => {
    const rawSrc = img.dataset.exportSrc || img.currentSrc || img.src
    img.loading = 'eager'
    img.src = await toExportableImage(rawSrc, img.dataset.exportLabel || img.alt || 'Travel')
  }))
  await nextTick()
  await Promise.all(images.map(waitForImage))
  return () => {
    snapshots.forEach(({ img, src, fallbackApplied }) => {
      img.src = src
      if (fallbackApplied === undefined) delete img.dataset.fallbackApplied
      else img.dataset.fallbackApplied = fallbackApplied
    })
  }
}

function waitForImage(img: HTMLImageElement) {
  if (img.complete && img.naturalWidth > 0) return Promise.resolve()
  return new Promise<void>(resolve => {
    const done = () => resolve()
    const timer = window.setTimeout(done, 10000)
    img.onload = () => {
      window.clearTimeout(timer)
      done()
    }
    img.onerror = () => {
      window.clearTimeout(timer)
      done()
    }
  })
}

async function toExportableImage(rawUrl: string, label: string) {
  if (!rawUrl || rawUrl.startsWith('data:')) return rawUrl || placeholderDataUri(label)
  try {
    const response = await fetch(proxiedImageUrl(rawUrl), { cache: 'force-cache' })
    if (!response.ok) throw new Error(`图片代理返回 ${response.status}`)
    const blob = await response.blob()
    if (!blob.type.startsWith('image/')) throw new Error('代理结果不是图片')
    return await blobToDataUrl(blob)
  } catch (error) {
    console.warn('导出图片转换失败，使用占位图：', rawUrl, error)
    return placeholderDataUri(label)
  }
}

function blobToDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

function renderExportCanvas(element: HTMLElement) {
  return html2canvas(element, {
    scale: 2,
    backgroundColor: '#ffffff',
    useCORS: true,
    allowTaint: false,
    logging: false,
    windowWidth: element.scrollWidth,
    windowHeight: element.scrollHeight
  })
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function triggerImport() {
  fileInputRef.value?.click()
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  try {
    const payload = JSON.parse(await file.text())
    const plan = normalizeImportedPlan(payload)
    if (!plan) {
      message.error('JSON结构不符合旅行方案格式')
      return
    }
    tripPlan.value = plan
    sessionStorage.setItem('tripPlan', JSON.stringify(plan))
    saveHistoryRecord(requestFromPlan(plan), plan)
    message.success('JSON导入成功')
  } catch (error: any) {
    message.error(`JSON解析失败：${error.message}`)
  }
}
</script>

<style scoped>
.result-page {
  min-height: 100vh;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(14, 116, 144, 0.08), transparent 34%),
    linear-gradient(315deg, rgba(234, 88, 12, 0.08), transparent 30%),
    #f5f7fb;
}

.result-header {
  max-width: 1660px;
  margin: 0 auto 20px;
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-end;
}

.result-header h1 {
  margin: 14px 0 4px;
  font-size: 30px;
}

.result-header p {
  margin: 0;
  color: #64748b;
}

.result-layout {
  max-width: 1660px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  gap: 20px;
}

.export-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 430px;
  gap: 20px;
  align-items: start;
}

.content-column,
.side-column {
  display: grid;
  align-content: start;
  gap: 18px;
}

.quick-nav {
  position: sticky;
  top: 18px;
  align-self: start;
  padding: 12px;
  display: grid;
  gap: 8px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.07);
}

.quick-nav button {
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #334155;
  text-align: left;
  font-weight: 700;
  cursor: pointer;
}

.quick-nav button.active {
  background: #0f766e;
  color: #ffffff;
}

.day-nav {
  margin-top: 4px;
  padding-top: 8px;
  display: grid;
  gap: 6px;
  border-top: 1px solid #e2e8f0;
}

.day-nav button {
  padding-left: 20px;
  font-size: 13px;
}

:deep(.ant-card) {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.07);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-grid div,
.budget-item,
.weather-card {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.metric-label,
.section-kicker {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.summary-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 22px;
}

.suggestion,
.section-note {
  margin: 16px 0 0;
  color: #334155;
  line-height: 1.7;
  white-space: pre-line;
}

.budget-grid,
.weather-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.budget-item strong {
  display: block;
  margin-top: 6px;
  color: #ea580c;
  font-size: 22px;
}

.weather-card span,
.weather-card p {
  display: block;
  margin: 6px 0 0;
  color: #475569;
}

.days-section {
  display: grid;
  gap: 18px;
}

.day-block {
  scroll-margin-top: 18px;
  padding: 20px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.07);
}

.day-title-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.day-index {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.day-title-row h2 {
  margin: 4px 0 0;
}

.day-transport,
.duration {
  border-radius: 999px;
  padding: 6px 10px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 12px;
  font-weight: 700;
}

.day-desc {
  color: #475569;
}

.attraction-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.place-card {
  overflow: hidden;
}

.image-wrap {
  position: relative;
  margin: -24px -24px 0;
  height: 220px;
  overflow: hidden;
  background: #e2e8f0;
}

.image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.place-order,
.ticket {
  position: absolute;
  top: 12px;
  border-radius: 999px;
  color: #ffffff;
  font-weight: 800;
}

.place-order {
  left: 12px;
  min-width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  background: #2563eb;
}

.ticket {
  right: 12px;
  padding: 6px 10px;
  background: #ea580c;
}

.place-body {
  padding-top: 16px;
}

.place-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.place-head h3,
.hotel-card h3 {
  margin: 0;
}

.rating {
  color: #b45309;
  font-weight: 800;
}

.address,
.reason {
  color: #64748b;
}

.edit-actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
}

.meal-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.meal-card {
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.meal-card span {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.meal-card strong {
  display: block;
  margin-top: 4px;
}

.meal-card p {
  min-height: 42px;
  margin: 6px 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.meal-card small {
  color: #64748b;
}

.hotel-section {
  scroll-margin-top: 18px;
}

.hotel-grid {
  margin-top: 16px;
  display: grid;
  gap: 14px;
}

.hotel-card {
  padding: 14px;
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.hotel-card img {
  width: 200px;
  height: 132px;
  border-radius: 8px;
  object-fit: cover;
}

.hotel-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hotel-meta span {
  padding: 5px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
}

.side-stack {
  position: sticky;
  top: 18px;
  display: grid;
  gap: 18px;
}

.map-card :deep(.ant-card-body) {
  padding: 0;
}

.status-card {
  position: static;
}

.status-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #e2e8f0;
}

.status-row:last-child {
  border-bottom: 0;
}

.hidden-input {
  display: none;
}

:global(.exporting-trip .export-skip) {
  display: none !important;
}

:global(.exporting-trip .export-layout) {
  grid-template-columns: 1fr !important;
}

@media (max-width: 1280px) {
  .result-layout {
    grid-template-columns: 1fr;
  }

  .quick-nav {
    position: sticky;
    top: 0;
    z-index: 5;
    grid-auto-flow: column;
    grid-auto-columns: max-content;
    overflow-x: auto;
  }

  .day-nav {
    margin-top: 0;
    padding-top: 0;
    grid-auto-flow: column;
    border-top: 0;
  }
}

@media (max-width: 1180px) {
  .export-layout {
    grid-template-columns: 1fr;
  }

  .side-stack {
    position: static;
  }
}

@media (max-width: 760px) {
  .result-page {
    padding: 16px;
  }

  .result-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .budget-grid,
  .weather-grid,
  .attraction-grid,
  .meal-grid {
    grid-template-columns: 1fr;
  }

  .hotel-card {
    grid-template-columns: 1fr;
  }

  .hotel-card img {
    width: 100%;
    height: 180px;
  }
}
</style>
