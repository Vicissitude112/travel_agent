<template>
  <div class="home-page">
    <section class="planner-header">
      <div>
        <p class="eyebrow">LangGraph Multi-Agent Travel System</p>
        <h1>基于 LangGraph 多智能体协作的 AI 旅行规划系统</h1>
        <p class="subtitle">输入目的地、日期和偏好，生成包含景点、酒店、天气、图片和地图的结构化行程。</p>
      </div>
      <a-space>
        <a-button @click="showHistoryDrawer = true">
          <HistoryOutlined />
          历史记录
        </a-button>
        <a-button @click="triggerImport">
          <UploadOutlined />
          导入 JSON
        </a-button>
      </a-space>
      <input ref="fileInputRef" class="hidden-input" type="file" accept="application/json,.json" @change="handleImportFile" />
    </section>

    <main class="workspace">
      <a-card class="planner-card" :bordered="false">
        <a-form :model="formData" layout="vertical" @finish="handleSubmit">
          <div class="form-grid">
            <a-form-item name="city" label="目的地" :rules="[{ required: true, message: '请输入目的地城市' }]">
              <a-input v-model:value="formData.city" size="large" placeholder="例如：北京、成都、杭州" />
            </a-form-item>

            <a-form-item label="出行日期" required>
              <a-range-picker v-model:value="dateRange" size="large" style="width: 100%" />
            </a-form-item>

            <a-form-item label="出行天数">
              <div class="days-counter">
                <strong>{{ travelDays }}</strong>
                <span>天</span>
              </div>
            </a-form-item>

            <a-form-item label="交通方式">
              <a-segmented v-model:value="formData.transportation" :options="transportationOptions" size="large" />
            </a-form-item>

            <a-form-item label="住宿偏好">
              <a-select v-model:value="formData.accommodation" size="large">
                <a-select-option value="经济型酒店">经济型酒店</a-select-option>
                <a-select-option value="舒适型酒店">舒适型酒店</a-select-option>
                <a-select-option value="豪华酒店">豪华酒店</a-select-option>
                <a-select-option value="民宿">民宿</a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <a-form-item label="旅行偏好">
            <a-checkbox-group v-model:value="formData.preferences" class="preference-grid">
              <a-checkbox v-for="item in preferenceOptions" :key="item" :value="item">{{ item }}</a-checkbox>
            </a-checkbox-group>
          </a-form-item>

          <a-form-item label="额外要求">
            <a-textarea
              v-model:value="formData.free_text_input"
              :rows="4"
              placeholder="例如：希望少走路、想看展览、需要亲子友好、预算控制在 3000 元内"
            />
          </a-form-item>

          <div v-if="loading" class="loading-panel">
            <a-progress :percent="loadingProgress" :stroke-color="{ '0%': '#0ea5e9', '100%': '#f97316' }" />
            <span>{{ loadingStatus }}</span>
          </div>

          <div class="form-actions">
            <a-button type="primary" size="large" html-type="submit" :loading="loading">
              <PlayCircleOutlined />
              生成旅行方案
            </a-button>
            <a-button size="large" @click="resetForm">
              <ReloadOutlined />
              重置
            </a-button>
          </div>
        </a-form>
      </a-card>

      <aside class="history-panel">
        <div class="panel-title">
          <span>最近记录</span>
          <a-button v-if="historyRecords.length" size="small" danger @click="clearAllHistory">
            清空
          </a-button>
        </div>
        <a-empty v-if="!historyRecords.length" description="暂无历史记录" />
        <div v-else class="history-list">
          <article v-for="record in historyRecords.slice(0, 6)" :key="record.id" class="history-item">
            <div>
              <strong>{{ record.destination }}</strong>
              <p>{{ formatTime(record.generated_at) }} · {{ record.travel_days }}天</p>
            </div>
            <a-space>
              <a-tooltip title="查看详情">
                <a-button shape="circle" @click="openHistory(record)">
                  <EyeOutlined />
                </a-button>
              </a-tooltip>
              <a-tooltip title="恢复输入">
                <a-button shape="circle" @click="restoreForm(record)">
                  <ReloadOutlined />
                </a-button>
              </a-tooltip>
              <a-tooltip title="删除">
                <a-button shape="circle" danger @click="removeHistory(record.id)">
                  <DeleteOutlined />
                </a-button>
              </a-tooltip>
            </a-space>
          </article>
        </div>
      </aside>
    </main>

    <a-drawer v-model:open="showHistoryDrawer" title="历史记录" width="420">
      <a-empty v-if="!historyRecords.length" description="暂无历史记录" />
      <div v-else class="drawer-history">
        <article v-for="record in historyRecords" :key="record.id" class="history-item">
          <div>
            <strong>{{ record.destination }}</strong>
            <p>{{ formatTime(record.generated_at) }} · {{ record.travel_days }}天</p>
          </div>
          <a-space>
            <a-button size="small" @click="openHistory(record)">查看</a-button>
            <a-button size="small" @click="restoreForm(record)">恢复</a-button>
            <a-button size="small" danger @click="removeHistory(record.id)">删除</a-button>
          </a-space>
        </article>
      </div>
      <template #footer>
        <a-button v-if="historyRecords.length" danger block @click="clearAllHistory">清空全部历史记录</a-button>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  DeleteOutlined,
  EyeOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  UploadOutlined
} from '@ant-design/icons-vue'
import dayjs, { Dayjs } from 'dayjs'
import { generateTripPlan } from '@/services/api'
import type { TripFormData, TripHistoryRecord } from '@/types'
import {
  clearHistoryRecords,
  deleteHistoryRecord,
  loadHistory,
  normalizeImportedPlan,
  requestFromPlan,
  saveHistoryRecord
} from '@/utils/storage'

const router = useRouter()
const fileInputRef = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const showHistoryDrawer = ref(false)
const historyRecords = ref<TripHistoryRecord[]>([])
const dateRange = ref<[Dayjs, Dayjs] | null>([dayjs().add(7, 'day'), dayjs().add(9, 'day')])

const formData = reactive({
  city: '',
  transportation: '公共交通',
  accommodation: '舒适型酒店',
  preferences: ['历史文化'],
  free_text_input: ''
})

const transportationOptions = ['公共交通', '自驾', '步行', '混合']
const preferenceOptions = ['历史文化', '自然风光', '美食', '购物', '艺术展览', '亲子', '休闲', '夜游']

const travelDays = computed(() => {
  if (!dateRange.value) return 1
  const days = dateRange.value[1].diff(dateRange.value[0], 'day') + 1
  return Math.max(1, Math.min(days, 30))
})

watch(dateRange, value => {
  if (!value) return
  const days = value[1].diff(value[0], 'day') + 1
  if (days <= 0) {
    message.warning('结束日期不能早于开始日期')
    dateRange.value = null
  } else if (days > 30) {
    message.warning('旅行天数不能超过30天')
    dateRange.value = [value[0], value[0].add(29, 'day')]
  }
})

onMounted(() => {
  refreshHistory()
})

function buildRequest(): TripFormData | null {
  if (!dateRange.value) {
    message.error('请选择出行日期')
    return null
  }
  return {
    city: formData.city.trim(),
    start_date: dateRange.value[0].format('YYYY-MM-DD'),
    end_date: dateRange.value[1].format('YYYY-MM-DD'),
    travel_days: travelDays.value,
    transportation: formData.transportation,
    accommodation: formData.accommodation,
    preferences: formData.preferences,
    free_text_input: formData.free_text_input.trim()
  }
}

async function handleSubmit() {
  const request = buildRequest()
  if (!request) return

  loading.value = true
  loadingProgress.value = 8
  loadingStatus.value = '正在解析需求'
  const progressTimer = window.setInterval(() => {
    if (loadingProgress.value < 88) {
      loadingProgress.value += 8
      if (loadingProgress.value < 30) loadingStatus.value = '正在搜索景点'
      else if (loadingProgress.value < 48) loadingStatus.value = '正在查询天气'
      else if (loadingProgress.value < 66) loadingStatus.value = '正在补全图片和酒店'
      else loadingStatus.value = '正在生成行程'
    }
  }, 600)

  try {
    const response = await generateTripPlan(request)
    if (!response.success || !response.data) {
      throw new Error(response.message || '生成失败')
    }
    window.clearInterval(progressTimer)
    loadingProgress.value = 100
    loadingStatus.value = '已完成'
    sessionStorage.setItem('tripPlan', JSON.stringify(response.data))
    saveHistoryRecord(request, response.data)
    refreshHistory()
    message.success('旅行方案已生成')
    router.push('/result')
  } catch (error: any) {
    window.clearInterval(progressTimer)
    message.error(error.message || '生成旅行方案失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  formData.city = ''
  formData.transportation = '公共交通'
  formData.accommodation = '舒适型酒店'
  formData.preferences = ['历史文化']
  formData.free_text_input = ''
  dateRange.value = [dayjs().add(7, 'day'), dayjs().add(9, 'day')]
}

function refreshHistory() {
  historyRecords.value = loadHistory()
}

function openHistory(record: TripHistoryRecord) {
  sessionStorage.setItem('tripPlan', JSON.stringify(record.plan))
  router.push('/result')
}

function restoreForm(record: TripHistoryRecord) {
  formData.city = record.request.city
  formData.transportation = record.request.transportation
  formData.accommodation = record.request.accommodation
  formData.preferences = [...record.request.preferences]
  formData.free_text_input = record.request.free_text_input
  dateRange.value = [dayjs(record.request.start_date), dayjs(record.request.end_date)]
  showHistoryDrawer.value = false
  message.success('已恢复历史输入')
}

function removeHistory(id: string) {
  deleteHistoryRecord(id)
  refreshHistory()
}

function clearAllHistory() {
  Modal.confirm({
    title: '清空全部历史记录？',
    content: '该操作只会清除本机浏览器中的 localStorage 历史记录。',
    okText: '清空',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => {
      clearHistoryRecords()
      refreshHistory()
    }
  })
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
    const request = requestFromPlan(plan)
    sessionStorage.setItem('tripPlan', JSON.stringify(plan))
    saveHistoryRecord(request, plan)
    refreshHistory()
    message.success('JSON导入成功')
    router.push('/result')
  } catch (error: any) {
    message.error(`JSON解析失败：${error.message}`)
  }
}

function formatTime(value: string) {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  padding: 32px;
  background: #f5f7fb;
  color: #0f172a;
}

.planner-header {
  max-width: 1320px;
  margin: 0 auto 24px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-end;
}

.eyebrow {
  margin: 0 0 8px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.2;
}

.subtitle {
  max-width: 720px;
  margin: 10px 0 0;
  color: #475569;
}

.workspace {
  max-width: 1320px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 20px;
}

.planner-card,
.history-panel {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.form-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.3fr 160px;
  gap: 18px;
}

.days-counter {
  height: 40px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
}

.days-counter strong {
  color: #ea580c;
  font-size: 22px;
}

.preference-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.preference-grid :deep(.ant-checkbox-wrapper) {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #ffffff;
}

.loading-panel {
  margin-bottom: 18px;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
}

.loading-panel span {
  display: block;
  margin-top: 8px;
  color: #075985;
  font-weight: 600;
}

.form-actions {
  display: flex;
  gap: 12px;
}

.form-actions .ant-btn-primary {
  background: #0f766e;
}

.history-panel {
  padding: 18px;
  background: #ffffff;
}

.panel-title {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 800;
}

.history-list,
.drawer-history {
  display: grid;
  gap: 12px;
}

.history-item {
  padding: 14px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.history-item p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.hidden-input {
  display: none;
}

@media (max-width: 1080px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .history-panel {
    display: none;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .home-page {
    padding: 18px;
  }

  .planner-header {
    align-items: flex-start;
    flex-direction: column;
  }

  h1 {
    font-size: 28px;
  }

  .preference-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
