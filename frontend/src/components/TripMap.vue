<template>
  <div class="trip-map">
    <div v-if="!apiKey" class="map-empty">
      <div class="map-empty-title">地图暂不可用</div>
      <div class="map-empty-subtitle">请在前端环境变量中配置 VITE_AMAP_WEB_JS_KEY</div>
    </div>
    <div v-show="apiKey" ref="containerRef" class="map-container"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { MapMarker, TripPlan } from '@/types'

const props = defineProps<{
  plan: TripPlan | null
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const apiKey = import.meta.env.VITE_AMAP_WEB_JS_KEY || ''
const securityCode = import.meta.env.VITE_AMAP_SECURITY_JS_CODE || ''

let map: any = null
let amap: any = null
let markers: any[] = []
let infoWindow: any = null

const markerData = computed<MapMarker[]>(() => {
  if (props.plan?.map_data?.markers?.length) return props.plan.map_data.markers
  if (!props.plan) return []

  const fallback: MapMarker[] = []
  props.plan.days.forEach(day => {
    day.attractions.forEach((attraction, index) => {
      fallback.push({
        id: `day-${day.day_index}-attr-${index}`,
        marker_type: 'attraction',
        name: attraction.name,
        address: attraction.address,
        location: attraction.location,
        day_index: day.day_index,
        order: index + 1,
        rating: attraction.rating,
        image_url: attraction.image_url || attraction.image?.url,
        description: attraction.description
      })
    })
    if (day.hotel?.location) {
      fallback.push({
        id: `day-${day.day_index}-hotel`,
        marker_type: 'hotel',
        name: day.hotel.name,
        address: day.hotel.address,
        location: day.hotel.location,
        day_index: day.day_index,
        rating: day.hotel.rating,
        image_url: day.hotel.image_url || day.hotel.image?.url,
        description: day.hotel.recommendation_reason
      })
    }
  })
  return fallback
})

onMounted(async () => {
  await initMap()
})

onBeforeUnmount(() => {
  if (map) map.destroy()
})

watch(
  () => markerData.value,
  () => {
    renderMarkers()
  },
  { deep: true }
)

async function initMap() {
  if (!apiKey || !containerRef.value) return
  if (securityCode) {
    ;(window as any)._AMapSecurityConfig = { securityJsCode: securityCode }
  }

  await nextTick()
  amap = await AMapLoader.load({
    key: apiKey,
    version: '2.0',
    plugins: ['AMap.Marker', 'AMap.InfoWindow', 'AMap.Scale', 'AMap.ToolBar']
  })

  const center = props.plan?.map_data?.center
  map = new amap.Map(containerRef.value, {
    zoom: 11,
    center: center ? [center.longitude, center.latitude] : [116.4074, 39.9042],
    viewMode: '2D',
    resizeEnable: true
  })
  map.addControl(new amap.Scale())
  map.addControl(new amap.ToolBar({ position: 'RT' }))
  infoWindow = new amap.InfoWindow({ offset: new amap.Pixel(0, -28) })
  renderMarkers()
}

function renderMarkers() {
  if (!map || !amap) return

  // 每次行程变化都先清理旧 Marker，避免编辑行程后地图残留旧点。
  if (markers.length) {
    map.remove(markers)
    markers = []
  }

  markerData.value.forEach((item, index) => {
    const marker = new amap.Marker({
      position: [item.location.longitude, item.location.latitude],
      title: item.name,
      content: buildMarkerContent(item, index),
      offset: new amap.Pixel(-14, -28)
    })

    marker.on('click', () => {
      infoWindow.setContent(buildInfoWindow(item))
      infoWindow.open(map, marker.getPosition())
    })
    markers.push(marker)
  })

  if (markers.length) {
    map.add(markers)
    // 自动缩放到所有景点和酒店，修复原项目只有路线或点挤在一角的问题。
    map.setFitView(markers, false, [40, 40, 40, 40])
  }
}

function buildMarkerContent(item: MapMarker, index: number) {
  const label = item.marker_type === 'hotel' ? 'H' : String(item.order || index + 1)
  const markerClass = item.marker_type === 'hotel' ? 'hotel-marker' : 'attraction-marker'
  return `<div class="trip-marker ${markerClass}">${label}</div>`
}

function buildInfoWindow(item: MapMarker) {
  const image = item.image_url
    ? `<img src="${item.image_url}" style="width:220px;height:120px;object-fit:cover;border-radius:8px;margin-bottom:8px;" />`
    : ''
  const rating = item.rating ? `<div style="font-size:12px;color:#b45309;">评分：${item.rating}</div>` : ''
  const day = item.day_index !== undefined && item.day_index !== null ? `<div style="font-size:12px;color:#64748b;">第${item.day_index + 1}天</div>` : ''
  return `
    <div style="width:240px;padding:4px 2px 2px;">
      ${image}
      <div style="font-weight:700;color:#0f172a;margin-bottom:4px;">${item.name}</div>
      <div style="font-size:12px;color:#475569;line-height:1.5;">${item.address || ''}</div>
      ${rating}
      ${day}
      <div style="font-size:12px;color:#64748b;line-height:1.5;margin-top:4px;">${item.description || ''}</div>
    </div>
  `
}
</script>

<style scoped>
.trip-map {
  position: relative;
  min-height: 460px;
  height: 100%;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #eef4f8;
}

.map-container {
  width: 100%;
  height: 100%;
  min-height: 460px;
}

.map-empty {
  min-height: 460px;
  display: grid;
  place-items: center;
  text-align: center;
  color: #475569;
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    linear-gradient(0deg, rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    #f8fafc;
  background-size: 24px 24px;
}

.map-empty-title {
  font-weight: 700;
  color: #0f172a;
}

.map-empty-subtitle {
  margin-top: 6px;
  font-size: 13px;
}

:global(.trip-marker) {
  min-width: 28px;
  height: 28px;
  padding: 0 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #ffffff;
  border-radius: 16px;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.24);
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
}

:global(.attraction-marker) {
  background: #2563eb;
}

:global(.hotel-marker) {
  background: #dc2626;
}
</style>
