export interface Location {
  longitude: number
  latitude: number
}

export interface ImageInfo {
  url: string
  source: string
  attribution?: string | null
  thumb_url?: string | null
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number | null
  photos?: string[]
  poi_id?: string
  image?: ImageInfo | null
  image_url?: string | null
  ticket_price?: number
  recommendation_reason?: string
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string | null
  location?: Location | null
  description?: string | null
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location | null
  price_range: string
  rating?: string | number | null
  distance: string
  type: string
  estimated_cost?: number
  photos?: string[]
  poi_id?: string
  image?: ImageInfo | null
  image_url?: string | null
  recommendation_reason?: string
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel | null
  attractions: Attraction[]
  meals: Meal[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface MapMarker {
  id: string
  marker_type: 'attraction' | 'hotel'
  name: string
  address: string
  location: Location
  day_index?: number | null
  order?: number | null
  rating?: string | number | null
  image_url?: string | null
  description?: string | null
  extra?: Record<string, unknown>
}

export interface MapData {
  center: Location
  markers: MapMarker[]
  bounds: Location[]
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget | null
  map_data?: MapData | null
}

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan | null
}

export interface TripHistoryRecord {
  id: string
  generated_at: string
  destination: string
  travel_days: number
  request: TripFormData
  plan: TripPlan
}
