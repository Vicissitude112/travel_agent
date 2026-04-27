"""基于 LangGraph 的旅行规划工作流。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypedDict

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
from ..services.amap_service import get_amap_service
from ..services.image_service import get_image_service
from ..services.llm_service import get_llm_service
from .state import TripPlannerAgentState

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - 依赖未安装时允许后端用顺序降级启动
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment]


class TripGraphState(TypedDict, total=False):
    request: Any
    normalized_request: Any
    attractions: Any
    hotels: Any
    weather_info: Any
    trip_plan: Any
    map_data: Any
    errors: Any


CITY_COORDS: Dict[str, Location] = {
    "北京": Location(longitude=116.4074, latitude=39.9042),
    "上海": Location(longitude=121.4737, latitude=31.2304),
    "广州": Location(longitude=113.2644, latitude=23.1291),
    "深圳": Location(longitude=114.0579, latitude=22.5431),
    "杭州": Location(longitude=120.1551, latitude=30.2741),
    "南京": Location(longitude=118.7969, latitude=32.0603),
    "成都": Location(longitude=104.0665, latitude=30.5728),
    "西安": Location(longitude=108.9398, latitude=34.3416),
    "重庆": Location(longitude=106.5516, latitude=29.5630),
}


class LangGraphTripPlanner:
    """生产化旅行规划器：LangGraph 编排，节点内用服务和 Pydantic 模型约束数据。"""

    def __init__(self) -> None:
        logger.info("初始化 LangGraph 旅行规划工作流")
        self.amap_service = get_amap_service()
        self.image_service = get_image_service()
        self.llm_service = get_llm_service()
        self.workflow = self._build_workflow()
        self.engine_name = "langgraph" if self.workflow else "sequential-fallback"

    def _build_workflow(self) -> Any:
        if StateGraph is None:
            logger.warning("langgraph未安装，工作流将使用顺序降级执行")
            return None

        graph = StateGraph(TripGraphState)
        graph.add_node("parse_input", self.parse_input_node)
        graph.add_node("search_attractions", self.search_attractions_node)
        graph.add_node("query_weather", self.query_weather_node)
        graph.add_node("recommend_hotels", self.recommend_hotels_node)
        graph.add_node("complete_images", self.complete_images_node)
        graph.add_node("plan_itinerary", self.plan_itinerary_node)
        graph.add_node("build_map_data", self.build_map_data_node)
        graph.add_node("validate_output", self.validate_output_node)

        graph.add_edge(START, "parse_input")
        graph.add_edge("parse_input", "search_attractions")
        graph.add_edge("search_attractions", "query_weather")
        graph.add_edge("query_weather", "recommend_hotels")
        graph.add_edge("recommend_hotels", "complete_images")
        graph.add_edge("complete_images", "plan_itinerary")
        graph.add_edge("plan_itinerary", "build_map_data")
        graph.add_edge("build_map_data", "validate_output")
        graph.add_edge("validate_output", END)
        return graph.compile()

    def plan_trip(self, request: TripRequest) -> TripPlan:
        logger.info(
            "Agent工作流开始 city={} start={} end={} days={} preferences={}",
            request.city,
            request.start_date,
            request.end_date,
            request.travel_days,
            request.preferences,
        )
        initial_state = TripPlannerAgentState(request=request).model_dump()
        if self.workflow:
            result = self.workflow.invoke(initial_state)
        else:
            result = self._run_sequential(initial_state)

        state = TripPlannerAgentState.model_validate(result)
        if not state.trip_plan:
            logger.warning("工作流未生成有效行程，使用最终兜底计划")
            state.trip_plan = self._build_rule_based_plan(
                state.normalized_request or request,
                state.attractions or self._fallback_attractions(request.city, request.preferences),
                state.hotels or self._fallback_hotels(request.city, request.accommodation),
                state.weather_info or self._fallback_weather(request),
            )
            state.trip_plan.map_data = self._build_map_data(state.trip_plan)

        logger.info(
            "Agent工作流完成 city={} days={} attractions={} hotels={} errors={}",
            state.trip_plan.city,
            len(state.trip_plan.days),
            sum(len(day.attractions) for day in state.trip_plan.days),
            sum(1 for day in state.trip_plan.days if day.hotel),
            len(state.errors),
        )
        return state.trip_plan

    def _run_sequential(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for node in (
            self.parse_input_node,
            self.search_attractions_node,
            self.query_weather_node,
            self.recommend_hotels_node,
            self.complete_images_node,
            self.plan_itinerary_node,
            self.build_map_data_node,
            self.validate_output_node,
        ):
            state = node(state)
        return state

    def parse_input_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.request
        logger.info("节点: 输入解析与参数标准化 city={}", request.city)
        try:
            start = datetime.strptime(request.start_date, "%Y-%m-%d")
            end = datetime.strptime(request.end_date, "%Y-%m-%d")
            if end < start:
                end = start + timedelta(days=max(request.travel_days, 1) - 1)
                agent_state.errors.append("结束日期早于开始日期，已按旅行天数自动修正。")
            calculated_days = (end - start).days + 1
            normalized_days = max(1, min(30, calculated_days))
            agent_state.normalized_request = request.model_copy(
                update={
                    "city": request.city.strip(),
                    "start_date": start.strftime("%Y-%m-%d"),
                    "end_date": (start + timedelta(days=normalized_days - 1)).strftime("%Y-%m-%d"),
                    "travel_days": normalized_days,
                    "preferences": [item.strip() for item in request.preferences if item.strip()],
                    "free_text_input": (request.free_text_input or "").strip(),
                }
            )
        except Exception as exc:
            logger.exception("输入标准化失败 error={}", exc)
            agent_state.errors.append(f"输入标准化失败：{exc}")
            agent_state.normalized_request = request
        return agent_state.model_dump()

    def search_attractions_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 景点搜索 city={} preferences={}", request.city, request.preferences)
        try:
            pois = self.amap_service.search_attractions(request.city, request.preferences, limit=max(8, request.travel_days * 3))
            attractions = [self._poi_to_attraction(poi, request.preferences) for poi in pois]
            if not attractions:
                attractions = self._fallback_attractions(request.city, request.preferences)
                agent_state.errors.append("景点搜索无结果，已使用本地降级景点。")
            agent_state.attractions = attractions[: max(6, request.travel_days * 3)]
        except Exception as exc:
            logger.exception("景点搜索节点失败 error={}", exc)
            agent_state.errors.append(f"景点搜索失败：{exc}")
            agent_state.attractions = self._fallback_attractions(request.city, request.preferences)
        return agent_state.model_dump()

    def query_weather_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 天气查询 city={}", request.city)
        try:
            weather = self.amap_service.get_weather(request.city)
            agent_state.weather_info = self._align_weather_dates(request, weather)
        except Exception as exc:
            logger.exception("天气查询节点失败 error={}", exc)
            agent_state.errors.append(f"天气查询失败：{exc}")
            agent_state.weather_info = self._fallback_weather(request)
        return agent_state.model_dump()

    def recommend_hotels_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 酒店推荐 city={} accommodation={}", request.city, request.accommodation)
        try:
            pois = self.amap_service.search_hotels(request.city, request.accommodation, limit=8)
            hotels = [self._poi_to_hotel(poi, request.accommodation) for poi in pois]
            if not hotels:
                hotels = self._fallback_hotels(request.city, request.accommodation)
                agent_state.errors.append("酒店搜索无结果，已使用本地降级酒店。")
            agent_state.hotels = hotels
        except Exception as exc:
            logger.exception("酒店推荐节点失败 error={}", exc)
            agent_state.errors.append(f"酒店推荐失败：{exc}")
            agent_state.hotels = self._fallback_hotels(request.city, request.accommodation)
        return agent_state.model_dump()

    def complete_images_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 图片补全 attractions={} hotels={}", len(agent_state.attractions), len(agent_state.hotels))
        try:
            agent_state.attractions = self.image_service.enrich_attractions(agent_state.attractions, request.city)
            agent_state.hotels = self.image_service.enrich_hotels(agent_state.hotels, request.city)
        except Exception as exc:
            logger.exception("图片补全节点失败 error={}", exc)
            agent_state.errors.append(f"图片补全失败：{exc}")
        return agent_state.model_dump()

    def plan_itinerary_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 行程规划 city={} days={}", request.city, request.travel_days)
        plan = self.llm_service.build_trip_plan(
            request=request,
            attractions=agent_state.attractions,
            hotels=agent_state.hotels,
            weather_info=agent_state.weather_info,
        )
        if plan is None:
            plan = self._build_rule_based_plan(request, agent_state.attractions, agent_state.hotels, agent_state.weather_info)
        agent_state.trip_plan = plan
        return agent_state.model_dump()

    def build_map_data_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        logger.info("节点: 地图数据构建")
        if agent_state.trip_plan:
            agent_state.map_data = self._build_map_data(agent_state.trip_plan)
            agent_state.trip_plan.map_data = agent_state.map_data
        return agent_state.model_dump()

    def validate_output_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        logger.info("节点: 结果校验与格式化")
        if not agent_state.trip_plan:
            return agent_state.model_dump()

        plan = TripPlan.model_validate(agent_state.trip_plan)
        if not plan.budget:
            plan.budget = self._calculate_budget(plan)
        if not plan.map_data:
            plan.map_data = self._build_map_data(plan)
        plan.weather_info = self._align_weather_dates(
            agent_state.normalized_request or agent_state.request,
            plan.weather_info or agent_state.weather_info,
        )
        agent_state.trip_plan = plan
        return agent_state.model_dump()

    def _poi_to_attraction(self, poi: POIInfo, preferences: List[str]) -> Attraction:
        reason = "、".join(preferences) if preferences else "城市经典体验"
        return Attraction(
            name=poi.name,
            address=poi.address,
            location=poi.location,
            visit_duration=120 if "博物馆" in poi.name or "故宫" in poi.name else 90,
            description=f"{poi.name}位于{poi.address or '目的地核心区域'}，适合作为{reason}主题行程的一站。",
            category=poi.type or "景点",
            rating=poi.rating,
            photos=poi.photos,
            poi_id=poi.id,
            ticket_price=0,
            recommendation_reason=f"匹配偏好：{reason}",
        )

    def _poi_to_hotel(self, poi: POIInfo, accommodation: str) -> Hotel:
        nightly_cost = self._estimate_hotel_cost(accommodation)
        return Hotel(
            name=poi.name,
            address=poi.address,
            location=poi.location,
            price_range=f"{max(nightly_cost - 120, 120)}-{nightly_cost + 180}元/晚",
            rating=poi.rating or "",
            distance="靠近主要游览区域",
            type=accommodation or "酒店",
            estimated_cost=nightly_cost,
            photos=poi.photos,
            poi_id=poi.id,
            recommendation_reason="位置便于串联每日景点，适合作为行程住宿点。",
        )

    def _build_rule_based_plan(
        self,
        request: TripRequest,
        attractions: List[Attraction],
        hotels: List[Hotel],
        weather_info: List[WeatherInfo],
    ) -> TripPlan:
        logger.info("使用规则引擎生成降级行程 city={}", request.city)
        dates = self._date_list(request)
        days: List[DayPlan] = []
        attractions = attractions or self._fallback_attractions(request.city, request.preferences)
        hotels = hotels or self._fallback_hotels(request.city, request.accommodation)
        weather_info = self._align_weather_dates(request, weather_info)

        for day_index, current_date in enumerate(dates):
            day_attractions = self._pick_day_attractions(attractions, day_index, request.travel_days)
            hotel = hotels[day_index % len(hotels)] if hotels else None
            days.append(
                DayPlan(
                    date=current_date,
                    day_index=day_index,
                    description=self._day_description(request, day_index, day_attractions),
                    transportation=request.transportation,
                    accommodation=request.accommodation,
                    hotel=hotel,
                    attractions=day_attractions,
                    meals=self._build_meals(request.city, day_index),
                )
            )

        plan = TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=weather_info,
            overall_suggestions=(
                f"建议每天预留30-45分钟机动时间，并在出发前复核{request.city}景区开放时间。"
                "外部服务不可用时，系统会保留结构化行程，便于后续手动调整。"
            ),
        )
        plan.budget = self._calculate_budget(plan)
        return plan

    def _build_map_data(self, plan: TripPlan) -> MapData:
        markers: List[MapMarker] = []
        for day in plan.days:
            for order, attraction in enumerate(day.attractions, start=1):
                markers.append(
                    MapMarker(
                        id=f"day-{day.day_index}-attr-{order}-{attraction.name}",
                        marker_type="attraction",
                        name=attraction.name,
                        address=attraction.address,
                        location=attraction.location,
                        day_index=day.day_index,
                        order=order,
                        rating=attraction.rating,
                        image_url=attraction.image_url,
                        description=attraction.description,
                        extra={"visit_duration": attraction.visit_duration, "ticket_price": attraction.ticket_price},
                    )
                )
            if day.hotel and day.hotel.location:
                markers.append(
                    MapMarker(
                        id=f"day-{day.day_index}-hotel-{day.hotel.name}",
                        marker_type="hotel",
                        name=day.hotel.name,
                        address=day.hotel.address,
                        location=day.hotel.location,
                        day_index=day.day_index,
                        rating=day.hotel.rating,
                        image_url=day.hotel.image_url,
                        description=day.hotel.recommendation_reason,
                        extra={"price_range": day.hotel.price_range, "estimated_cost": day.hotel.estimated_cost},
                    )
                )

        if markers:
            avg_lng = sum(marker.location.longitude for marker in markers) / len(markers)
            avg_lat = sum(marker.location.latitude for marker in markers) / len(markers)
            center = Location(longitude=avg_lng, latitude=avg_lat)
            bounds = [marker.location for marker in markers]
        else:
            center = CITY_COORDS.get(plan.city, Location(longitude=116.4074, latitude=39.9042))
            bounds = [center]
        return MapData(center=center, markers=markers, bounds=bounds)

    def _calculate_budget(self, plan: TripPlan) -> Budget:
        attractions_cost = sum(attraction.ticket_price for day in plan.days for attraction in day.attractions)
        hotels_cost = sum(day.hotel.estimated_cost for day in plan.days if day.hotel)
        meals_cost = sum(meal.estimated_cost for day in plan.days for meal in day.meals)
        transport_cost = max(30, len(plan.days) * 60)
        return Budget(
            total_attractions=attractions_cost,
            total_hotels=hotels_cost,
            total_meals=meals_cost,
            total_transportation=transport_cost,
            total=attractions_cost + hotels_cost + meals_cost + transport_cost,
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

    def _city_center(self, city: str) -> Location:
        if city in CITY_COORDS:
            return CITY_COORDS[city]
        geocoded = self.amap_service.geocode(city, city)
        return geocoded or CITY_COORDS["北京"]

    def _fallback_attractions(self, city: str, preferences: List[str]) -> List[Attraction]:
        center = self._city_center(city)
        names = ["城市博物馆", "历史街区", "城市公园", "艺术中心", "观景地标", "特色市集", "滨水步道", "文化广场"]
        attractions: List[Attraction] = []
        for index, suffix in enumerate(names):
            location = Location(
                longitude=center.longitude + (index % 4 - 1.5) * 0.018,
                latitude=center.latitude + (index // 4 - 0.5) * 0.018,
            )
            topic = "、".join(preferences) if preferences else "当地文化"
            attractions.append(
                Attraction(
                    name=f"{city}{suffix}",
                    address=f"{city}核心游览区",
                    location=location,
                    visit_duration=90 + (index % 2) * 30,
                    description=f"{city}{suffix}适合了解{topic}，可作为外部服务不可用时的占位行程点。",
                    category="降级景点",
                    ticket_price=0 if index % 3 else 30,
                    recommendation_reason=f"围绕{topic}补足行程结构。",
                )
            )
        return attractions

    def _fallback_hotels(self, city: str, accommodation: str) -> List[Hotel]:
        center = self._city_center(city)
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
                    distance="距主要景点约2-4公里",
                    type=accommodation or "酒店",
                    estimated_cost=cost,
                    recommendation_reason="降级推荐酒店，位置便于覆盖主要行程。",
                )
            )
        return hotels

    @staticmethod
    def _pick_day_attractions(attractions: List[Attraction], day_index: int, total_days: int) -> List[Attraction]:
        per_day = 3 if len(attractions) >= total_days * 3 else 2
        start = day_index * per_day
        selected = attractions[start : start + per_day]
        if not selected:
            selected = [attractions[(day_index + i) % len(attractions)] for i in range(min(per_day, len(attractions)))]
        return selected

    @staticmethod
    def _build_meals(city: str, day_index: int) -> List[Meal]:
        return [
            Meal(type="breakfast", name=f"{city}本地早餐", description="选择酒店附近的本地早餐店", estimated_cost=35),
            Meal(type="lunch", name=f"{city}特色午餐", description="安排在上午景点附近，减少折返", estimated_cost=70),
            Meal(type="dinner", name=f"{city}风味晚餐", description="结合夜间活动选择商圈或老街餐厅", estimated_cost=90 + day_index * 10),
        ]

    @staticmethod
    def _day_description(request: TripRequest, day_index: int, attractions: List[Attraction]) -> str:
        names = "、".join(item.name for item in attractions)
        if day_index == 0:
            prefix = "抵达后从轻量景点开始"
        elif day_index == request.travel_days - 1:
            prefix = "最后一天控制交通距离"
        else:
            prefix = "全天深度游览"
        return f"{prefix}，重点安排：{names}。"


_trip_planner: Optional[LangGraphTripPlanner] = None


def get_trip_planner_agent() -> LangGraphTripPlanner:
    global _trip_planner
    if _trip_planner is None:
        _trip_planner = LangGraphTripPlanner()
    return _trip_planner


# 兼容旧引用名称。
MultiAgentTripPlanner = LangGraphTripPlanner
