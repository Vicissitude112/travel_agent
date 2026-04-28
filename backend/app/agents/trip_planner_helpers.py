"""旅行规划 Agent 的非节点辅助逻辑。"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

from loguru import logger

from ..models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Hotel,
    Location,
    MapData,
    MapMarker,
    Meal,
    POIInfo,
    TripPlan,
    TripRequest,
    WeatherInfo,
)

if TYPE_CHECKING:
    from ..services.amap_service import AmapService
    from ..services.llm_service import LLMService


class TripPlannerHelperMixin:
    """目的地解析、POI 转换、地图、预算和降级行程逻辑。"""

    # 这些属性由最终组合类 LangGraphTripPlanner.__init__ 注入；
    # 在 Mixin 中声明是为了让 IDE 和类型检查器理解依赖来源。
    amap_service: "AmapService"
    llm_service: "LLMService"

    def _resolve_destination(self, request: TripRequest) -> Tuple[str, Optional[Location]]:
        candidates = [request.city]
        for candidate in list(candidates):
            location = self._geocode_candidate(candidate, request.city)
            if location:
                return candidate, location
            poi = self._first_poi(candidate)
            if poi:
                return poi.name or candidate, poi.location

        llm_guess = self.llm_service.resolve_destination(request.city, request.free_text_input or "")
        if llm_guess and llm_guess not in candidates:
            location = self._geocode_candidate(llm_guess, request.city)
            if location:
                return llm_guess, location
            poi = self._first_poi(llm_guess)
            if poi:
                return poi.name or llm_guess, poi.location
        return request.city, None

    def _geocode_candidate(self, candidate: str, city_scope: str) -> Optional[Location]:
        scopes: List[Optional[str]] = [None]
        if city_scope and city_scope != candidate:
            scopes.append(city_scope)
        for scope in scopes:
            location = self.amap_service.geocode(candidate, scope)
            if location:
                return location
        return None

    def _first_poi(self, keyword: str) -> Optional[POIInfo]:
        pois = self.amap_service.search_poi(keyword, "", citylimit=False, page_size=5)
        return pois[0] if pois else None

    @staticmethod
    def _dedupe_pois(pois: Iterable[POIInfo]) -> List[POIInfo]:
        merged: Dict[str, POIInfo] = {}
        for poi in pois:
            key = poi.id or f"{poi.name}:{poi.address}:{poi.location.longitude:.5f}:{poi.location.latitude:.5f}"
            merged.setdefault(key, poi)
        return list(merged.values())

    def _poi_to_attraction(self, poi: POIInfo, preferences: List[str]) -> Attraction:
        reason = "、".join(preferences) if preferences else "城市经典体验"
        longer_visit_words = ("博物馆", "故宫", "遗址", "公园", "古城")
        return Attraction(
            name=poi.name,
            address=poi.address,
            location=poi.location,
            visit_duration=120 if any(word in poi.name for word in longer_visit_words) else 90,
            description=f"{poi.name}位于{poi.address or '目的地核心区域'}，适合纳入{reason}主题路线。",
            category=poi.type or "景点",
            rating=poi.rating,
            photos=poi.photos,
            poi_id=poi.id,
            ticket_price=0,
            recommendation_reason=f"匹配偏好：{reason}",
        )

    def _poi_to_hotel(self, poi: POIInfo, request: TripRequest, center: Optional[Location]) -> Hotel:
        nightly_cost = self._estimate_hotel_cost(request.accommodation)
        distance = self._distance_text(center, poi.location) if center else "靠近目的地主要出行区域"
        preference_text = self._preference_text(request.preferences)
        budget_note = self._budget_note(request, nightly_cost)
        return Hotel(
            name=poi.name,
            address=poi.address,
            location=poi.location,
            price_range=f"{max(nightly_cost - 120, 120)}-{nightly_cost + 180}元/晚",
            rating=poi.rating or "",
            distance=distance,
            type=request.accommodation or "酒店",
            estimated_cost=nightly_cost,
            photos=poi.photos,
            poi_id=poi.id,
            recommendation_reason=f"位于行程中心附近，减少跨城折返；{preference_text}{budget_note}",
        )

    def _normalize_plan(
        self,
        plan: TripPlan,
        request: TripRequest,
        hotels: List[Hotel],
        daily_meals: List[List[Meal]],
        errors: List[str],
    ) -> TripPlan:
        plan.city = plan.city or request.city
        plan.start_date = request.start_date
        plan.end_date = request.end_date
        plan.hotels = self._dedupe_hotels(plan.hotels or hotels)[:3]
        for day_index, day in enumerate(plan.days):
            day.day_index = day_index
            day.transportation = day.transportation or request.transportation
            day.accommodation = day.accommodation or request.accommodation
            day.hotel = None
            if day_index < len(daily_meals) and len(day.meals) < 3:
                day.meals = daily_meals[day_index]
        if len(plan.days) < request.travel_days:
            dates = self._date_list(request)
            for day_index in range(len(plan.days), request.travel_days):
                attractions = self._pick_day_attractions([], day_index, request.travel_days)
                plan.days.append(
                    DayPlan(
                        date=dates[day_index],
                        day_index=day_index,
                        description="当天景点数据不足，建议补充人工偏好后重新生成。",
                        transportation=request.transportation,
                        accommodation=request.accommodation,
                        hotel=None,
                        attractions=attractions,
                        meals=daily_meals[day_index] if day_index < len(daily_meals) else self._fallback_meals(request.city, day_index, []),
                    )
                )
        if errors:
            error_summary = "；".join(dict.fromkeys(errors))
            if error_summary and error_summary not in plan.overall_suggestions:
                plan.overall_suggestions = f"{plan.overall_suggestions}\n数据提示：{error_summary}".strip()
        plan.budget = self._calculate_budget(plan)
        return plan

    @staticmethod
    def _dedupe_hotels(hotels: Iterable[Hotel]) -> List[Hotel]:
        merged: Dict[str, Hotel] = {}
        for hotel in hotels:
            key = hotel.poi_id or f"{hotel.name}:{hotel.address}"
            merged.setdefault(key, hotel)
        return list(merged.values())

    def _build_rule_based_plan(
        self,
        request: TripRequest,
        attractions: List[Attraction],
        hotels: List[Hotel],
        weather_info: List[WeatherInfo],
        daily_meals: Optional[List[List[Meal]]] = None,
        errors: Optional[List[str]] = None,
    ) -> TripPlan:
        logger.info("使用规则引擎生成降级行程 city={}", request.city)
        dates = self._date_list(request)
        weather_info = self._align_weather_dates(request, weather_info)
        days: List[DayPlan] = []
        daily_meals = daily_meals or []

        for day_index, current_date in enumerate(dates):
            day_attractions = self._pick_day_attractions(attractions, day_index, request.travel_days)
            meals = daily_meals[day_index] if day_index < len(daily_meals) else self._fallback_meals(request.city, day_index, day_attractions)
            days.append(
                DayPlan(
                    date=current_date,
                    day_index=day_index,
                    description=self._day_description(request, day_index, day_attractions),
                    transportation=request.transportation,
                    accommodation=request.accommodation,
                    hotel=None,
                    attractions=day_attractions,
                    meals=meals,
                )
            )

        suggestions = (
            f"建议每天预留30-45分钟机动时间，并在出发前复核{request.city}景区开放时间。"
            "酒店为统一推荐，不按天频繁更换，实际入住可从酒店板块选择一处连续住宿。"
        )
        if errors:
            suggestions = f"{suggestions}\n数据提示：{'；'.join(dict.fromkeys(errors))}"
        plan = TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            hotels=self._dedupe_hotels(hotels)[:3],
            weather_info=weather_info,
            overall_suggestions=suggestions,
        )
        plan.budget = self._calculate_budget(plan)
        return plan

    def _build_map_data(self, plan: TripPlan, fallback_center: Optional[Location] = None) -> Optional[MapData]:
        markers: List[MapMarker] = []
        attraction_order = 1
        for day in plan.days:
            for attraction in day.attractions:
                markers.append(
                    MapMarker(
                        id=f"day-{day.day_index}-attr-{attraction_order}-{attraction.name}",
                        marker_type="attraction",
                        name=attraction.name,
                        address=attraction.address,
                        location=attraction.location,
                        day_index=day.day_index,
                        order=attraction_order,
                        rating=attraction.rating,
                        image_url=attraction.image_url,
                        description=attraction.description,
                        extra={"visit_duration": attraction.visit_duration, "ticket_price": attraction.ticket_price},
                    )
                )
                attraction_order += 1
        for index, hotel in enumerate(plan.hotels, start=1):
            if not hotel.location:
                continue
            markers.append(
                MapMarker(
                    id=f"hotel-{index}-{hotel.name}",
                    marker_type="hotel",
                    name=hotel.name,
                    address=hotel.address,
                    location=hotel.location,
                    day_index=None,
                    order=index,
                    rating=hotel.rating,
                    image_url=hotel.image_url,
                    description=hotel.recommendation_reason,
                    extra={"price_range": hotel.price_range, "estimated_cost": hotel.estimated_cost},
                )
            )

        if markers:
            avg_lng = sum(marker.location.longitude for marker in markers) / len(markers)
            avg_lat = sum(marker.location.latitude for marker in markers) / len(markers)
            center = Location(longitude=avg_lng, latitude=avg_lat)
            return MapData(center=center, markers=markers, bounds=[marker.location for marker in markers])
        if fallback_center:
            return MapData(center=fallback_center, markers=[], bounds=[fallback_center])
        return None

    def _calculate_budget(self, plan: TripPlan) -> Budget:
        attractions_cost = sum(attraction.ticket_price for day in plan.days for attraction in day.attractions)
        nights = max(len(plan.days) - 1, 1) if plan.hotels else 0
        hotel_cost = (plan.hotels[0].estimated_cost if plan.hotels else 0) * nights
        meals_cost = sum(meal.estimated_cost for day in plan.days for meal in day.meals)
        transport_cost = max(30, len(plan.days) * 60)
        return Budget(
            total_attractions=attractions_cost,
            total_hotels=hotel_cost,
            total_meals=meals_cost,
            total_transportation=transport_cost,
            total=attractions_cost + hotel_cost + meals_cost + transport_cost,
        )

    @staticmethod
    def _estimate_hotel_cost(accommodation: str) -> int:
        if "豪华" in accommodation:
            return 900
        if "舒适" in accommodation:
            return 520
        if "民宿" in accommodation:
            return 380
        return 280

    def _filter_hotels_by_budget(self, hotels: List[Hotel], request: TripRequest) -> List[Hotel]:
        budget = self._extract_budget_limit(request.free_text_input or "")
        if not budget:
            return hotels
        nights = max(request.travel_days - 1, 1)
        filtered = [hotel for hotel in hotels if hotel.estimated_cost * nights <= budget * 0.55]
        return filtered or hotels

    @staticmethod
    def _extract_budget_limit(text: str) -> Optional[int]:
        if not text or not any(word in text for word in ("预算", "控制", "以内", "不超过")):
            return None
        match = re.search(r"(\d{3,6})\s*元?", text)
        return int(match.group(1)) if match else None

    def _budget_note(self, request: TripRequest, nightly_cost: int) -> str:
        budget = self._extract_budget_limit(request.free_text_input or "")
        if not budget:
            return ""
        nights = max(request.travel_days - 1, 1)
        total = nightly_cost * nights
        return f"预计{nights}晚约{total}元，已参考用户预算{budget}元。"

    @staticmethod
    def _preference_text(preferences: List[str]) -> str:
        if not preferences:
            return "适合常规观光和连续住宿。"
        if any(item in preferences for item in ("亲子", "休闲")):
            return "适合亲子/休闲偏好，优先考虑交通便利和换乘少。"
        if any(item in preferences for item in ("情侣", "夜游", "购物")):
            return "适合夜游和商圈活动，晚间返程更方便。"
        if "商务" in preferences:
            return "适合商务出行，兼顾交通效率和设施稳定性。"
        return f"适配{('、'.join(preferences))}偏好。"

    @staticmethod
    def _date_list(request: TripRequest) -> List[str]:
        start = datetime.strptime(request.start_date, "%Y-%m-%d")
        return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(request.travel_days)]

    def _align_weather_dates(self, request: TripRequest, weather_info: List[WeatherInfo]) -> List[WeatherInfo]:
        by_date = {item.date: item for item in weather_info if item.date}
        aligned: List[WeatherInfo] = []
        for current_date in self._date_list(request):
            aligned.append(
                by_date.get(
                    current_date,
                    WeatherInfo(
                        date=current_date,
                        day_weather="多云",
                        night_weather="多云",
                        day_temp=24,
                        night_temp=16,
                        wind_direction="微风",
                        wind_power="1-3级",
                    ),
                )
            )
        return aligned

    def _fallback_weather(self, request: TripRequest) -> List[WeatherInfo]:
        return self._align_weather_dates(request, [])

    def _fallback_attractions(self, city: str, preferences: List[str], center: Optional[Location]) -> List[Attraction]:
        if not center:
            return []
        names = ["城市博物馆", "历史街区", "城市公园", "艺术中心", "观景地标", "特色市集", "滨水步道", "文化广场"]
        topic = "、".join(preferences) if preferences else "当地文化"
        attractions: List[Attraction] = []
        for index, suffix in enumerate(names):
            location = Location(
                longitude=center.longitude + (index % 4 - 1.5) * 0.018,
                latitude=center.latitude + (index // 4 - 0.5) * 0.018,
            )
            attractions.append(
                Attraction(
                    name=f"{city}{suffix}",
                    address=f"{city}核心游览区",
                    location=location,
                    visit_duration=90 + (index % 2) * 30,
                    description=f"{city}{suffix}适合了解{topic}，用于外部POI不足时补齐结构化行程。",
                    category="降级景点",
                    ticket_price=0 if index % 3 else 30,
                    recommendation_reason=f"围绕{topic}补足行程结构。",
                )
            )
        return attractions

    def _fallback_hotels(self, city: str, accommodation: str, center: Optional[Location]) -> List[Hotel]:
        if not center:
            return []
        cost = self._estimate_hotel_cost(accommodation)
        hotels: List[Hotel] = []
        for index, name in enumerate(["中心精选酒店", "城市花园酒店", "交通枢纽酒店"]):
            hotels.append(
                Hotel(
                    name=f"{city}{name}",
                    address=f"{city}核心商圈",
                    location=Location(
                        longitude=center.longitude + (index - 1) * 0.012,
                        latitude=center.latitude - 0.015,
                    ),
                    price_range=f"{max(cost - 100, 120)}-{cost + 160}元/晚",
                    rating="4.5",
                    distance="距行程中心约2-4公里",
                    type=accommodation or "酒店",
                    estimated_cost=cost,
                    recommendation_reason="POI酒店搜索不足时的降级推荐，位置围绕行程中心点生成。",
                )
            )
        return hotels

    @staticmethod
    def _pick_day_attractions(attractions: List[Attraction], day_index: int, total_days: int) -> List[Attraction]:
        if not attractions:
            return []
        per_day = 3 if len(attractions) >= total_days * 3 else 2
        start = day_index * per_day
        selected = attractions[start : start + per_day]
        if not selected:
            selected = [attractions[(day_index + i) % len(attractions)] for i in range(min(per_day, len(attractions)))]
        return selected

    @staticmethod
    def _itinerary_center(attractions: List[Attraction]) -> Optional[Location]:
        locations = [item.location for item in attractions if item.location]
        if not locations:
            return None
        return Location(
            longitude=sum(item.longitude for item in locations) / len(locations),
            latitude=sum(item.latitude for item in locations) / len(locations),
        )

    @staticmethod
    def _distance_text(origin: Optional[Location], destination: Optional[Location]) -> str:
        if not origin or not destination:
            return "靠近主要景点区域"
        distance = TripPlannerHelperMixin._haversine_km(origin, destination)
        return f"距行程中心约{distance:.1f}公里"

    @staticmethod
    def _haversine_km(a: Location, b: Location) -> float:
        radius = 6371.0
        lat1 = math.radians(a.latitude)
        lat2 = math.radians(b.latitude)
        dlat = math.radians(b.latitude - a.latitude)
        dlng = math.radians(b.longitude - a.longitude)
        value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))

    @staticmethod
    def _day_description(request: TripRequest, day_index: int, attractions: List[Attraction]) -> str:
        names = "、".join(item.name for item in attractions) if attractions else "待补充景点"
        if day_index == 0:
            prefix = "抵达后从轻量景点开始"
        elif day_index == request.travel_days - 1:
            prefix = "最后一天控制交通距离"
        else:
            prefix = "全天深度游览"
        return f"{prefix}，重点安排：{names}。"
