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

      <main id="trip-plan-content" class="result-layout">
        <section class="content-column">
          <a-card class="summary-card" :bordered="false">
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

          <a-card v-if="tripPlan.weather_info?.length" title="天气摘要" :bordered="false">
            <div class="weather-grid">
              <article v-for="weather in tripPlan.weather_info" :key="weather.date" class="weather-card">
                <strong>{{ weather.date }}</strong>
                <span>{{ weather.day_weather || '多云' }} / {{ weather.night_weather || '多云' }}</span>
                <p>{{ weather.day_temp }}℃ - {{ weather.night_temp }}℃ · {{ weather.wind_direction }} {{ weather.wind_power }}</p>
              </article>
            </div>
          </a-card>

          <section class="days-section">
            <article v-for="(day, dayIdx) in tripPlan.days" :key="day.date" class="day-block">
              <div class="day-title-row">
                <div>
                  <span class="day-index">DAY {{ day.day_index + 1 }}</span>
                  <h2>{{ day.date }}</h2>
                </div>
                <span class="day-transport">{{ day.transportation }}</span>
              </div>
              <p class="day-desc">{{ day.description }}</p>

              <div class="attraction-grid">
                <a-card v-for="(attraction, attrIdx) in day.attractions" :key="`${day.date}-${attraction.name}`" class="place-card" :bordered="false">
                  <div class="image-wrap">
                    <img :src="placeImage(attraction)" :alt="attraction.name" @error="handleImageError" />
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

              <a-card v-if="day.hotel" class="hotel-card" :bordered="false">
                <div class="hotel-layout">
                  <img :src="hotelImage(day.hotel)" :alt="day.hotel.name" @error="handleImageError" />
                  <div>
                    <span class="section-kicker">住宿推荐</span>
                    <h3>{{ day.hotel.name }}</h3>
                    <p>{{ day.hotel.address }}</p>
                    <div class="hotel-meta">
                      <span>{{ day.hotel.type }}</span>
                      <span>{{ day.hotel.price_range }}</span>
                      <span v-if="day.hotel.rating">评分 {{ day.hotel.rating }}</span>
                    </div>
                    <p class="reason">{{ day.hotel.recommendation_reason }}</p>
                  </div>
                </div>
              </a-card>

              <div class="meal-row">
                <span v-for="meal in day.meals" :key="`${day.date}-${meal.type}`" class="meal-chip">
                  {{ mealLabel(meal.type) }} · {{ meal.name }} · ¥{{ meal.estimated_cost || 0 }}
                </span>
              </div>
            </article>
          </section>
        </section>

        <aside class="side-column">
          <a-card title="行程地图" :bordered="false" class="map-card map-export-skip">
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
        </aside>
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
import { computed, nextTick, onMounted, ref } from 'vue'
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
import { normalizeImportedPlan, requestFromPlan, saveHistoryRecord } from '@/utils/storage'

const router = useRouter()
const tripPlan = ref<TripPlan | null>(null)
const originalPlan = ref<TripPlan | null>(null)
const editMode = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const attractionCount = computed(() => tripPlan.value?.days.reduce((sum, day) => sum + day.attractions.length, 0) || 0)
const hotelCount = computed(() => tripPlan.value?.days.filter(day => day.hotel).length || 0)
const imageSourceSummary = computed(() => {
  if (!tripPlan.value) return '-'
  const sources = new Set<string>()
  tripPlan.value.days.forEach(day => {
    day.attractions.forEach(item => item.image?.source && sources.add(item.image.source))
    if (day.hotel?.image?.source) sources.add(day.hotel.image.source)
  })
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
})

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
  return attraction.image_url || attraction.image?.url || placeholder(attraction.name)
}

function hotelImage(hotel: Hotel) {
  return hotel.image_url || hotel.image?.url || placeholder(hotel.name)
}

function placeholder(label: string) {
  return `https://placehold.co/960x600/e6f4ff/1677ff?text=${encodeURIComponent(label || 'Travel')}`
}

function handleImageError(event: Event) {
  const img = event.target as HTMLImageElement
  img.src = placeholder('Travel')
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

function exportAsJson() {
  if (!tripPlan.value) return
  const payload = {
    schema_version: 'travel_agent.trip_plan.v2',
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
  try {
    message.loading({ content: '正在生成图片...', key: 'export', duration: 0 })
    document.body.classList.add('exporting-trip')
    await nextTick()
    const canvas = await html2canvas(element, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true
    })
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
    if (blob) downloadBlob(blob, `${tripPlan.value.city}-旅行方案.png`)
    message.success({ content: '图片导出成功', key: 'export' })
  } catch (error: any) {
    message.error({ content: `图片导出失败：${error.message}`, key: 'export' })
  } finally {
    document.body.classList.remove('exporting-trip')
  }
}

async function exportAsPDF() {
  if (!tripPlan.value) return
  const element = document.getElementById('trip-plan-content')
  if (!element) return
  try {
    message.loading({ content: '正在生成PDF...', key: 'export', duration: 0 })
    document.body.classList.add('exporting-trip')
    await nextTick()
    const canvas = await html2canvas(element, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true
    })
    const pdf = new jsPDF('p', 'mm', 'a4')
    const width = 210
    const height = (canvas.height * width) / canvas.width
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, width, height)
    pdf.save(`${tripPlan.value.city}-旅行方案.pdf`)
    message.success({ content: 'PDF导出成功', key: 'export' })
  } catch (error: any) {
    message.error({ content: `PDF导出失败：${error.message}`, key: 'export' })
  } finally {
    document.body.classList.remove('exporting-trip')
  }
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
  background: #f5f7fb;
}

.result-header {
  max-width: 1480px;
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
  max-width: 1480px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 430px;
  gap: 20px;
}

.content-column,
.side-column {
  display: grid;
  align-content: start;
  gap: 18px;
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

.suggestion {
  margin: 16px 0 0;
  color: #334155;
  line-height: 1.7;
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
.duration,
.meal-chip {
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

.hotel-card {
  margin-top: 14px;
}

.hotel-layout {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
}

.hotel-layout img {
  width: 180px;
  height: 120px;
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

.meal-row {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.map-card {
  position: sticky;
  top: 18px;
}

.map-card :deep(.ant-card-body) {
  padding: 0;
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

:global(.exporting-trip .map-export-skip) {
  display: none !important;
}

@media (max-width: 1180px) {
  .result-layout {
    grid-template-columns: 1fr;
  }

  .map-card {
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
  .attraction-grid {
    grid-template-columns: 1fr;
  }

  .hotel-layout {
    grid-template-columns: 1fr;
  }

  .hotel-layout img {
    width: 100%;
    height: 180px;
  }
}
</style>
