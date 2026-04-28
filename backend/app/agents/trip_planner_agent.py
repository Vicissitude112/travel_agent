"""基于 LangGraph 多智能体协作的旅行规划工作流。"""

from __future__ import annotations

import operator
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from loguru import logger

from ..models.schemas import (
    Meal,
    POIInfo,
    TripPlan,
    TripRequest,
)
from ..services.amap_service import get_amap_service
from ..services.image_service import get_image_service
from ..services.llm_service import get_llm_service
from .state import TripPlannerAgentState
from .trip_food import TripFoodMixin
from .trip_planner_helpers import TripPlannerHelperMixin

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - 依赖未安装时允许后端用顺序降级启动
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment]


class TripGraphState(TypedDict, total=False):
    request: Any
    normalized_request: Any
    resolved_destination: Any
    destination_location: Any
    attractions: Any
    hotels: Any
    daily_meals: Any
    weather_info: Any
    trip_plan: Any
    map_data: Any
    errors: Annotated[List[str], operator.add]


class LangGraphTripPlanner(TripPlannerHelperMixin, TripFoodMixin):
    """多智能体旅行规划器。

    工作流不再把酒店塞进每天的行程，而是按“目的地解析 -> POI/天气/餐饮并行
    研究 -> 统一酒店推荐 -> 行程整合 -> 地图和格式校验”的方式协作。
    """

    def __init__(self) -> None:
        logger.info("初始化 LangGraph 多智能体旅行规划工作流")
        self.amap_service = get_amap_service()
        self.image_service = get_image_service()
        self.llm_service = get_llm_service()
        self.workflow = self._build_workflow()
        self.engine_name = "langgraph-multi-agent" if self.workflow else "sequential-fallback"

    def _build_workflow(self) -> Any:
        if StateGraph is None:
            logger.warning("langgraph未安装，工作流将使用顺序降级执行")
            return None

        try:
            graph = StateGraph(TripGraphState)
            graph.add_node("parse_input", self.parse_input_node)
            graph.add_node("resolve_destination", self.resolve_destination_node)
            graph.add_node("search_attractions", self.search_attractions_node)
            graph.add_node("query_weather", self.query_weather_node)
            graph.add_node("recommend_hotels", self.recommend_hotels_node)
            graph.add_node("recommend_food", self.recommend_food_node)
            graph.add_node("complete_images", self.complete_images_node)
            graph.add_node("plan_itinerary", self.plan_itinerary_node)
            graph.add_node("build_map_data", self.build_map_data_node)
            graph.add_node("validate_output", self.validate_output_node)

            graph.add_edge(START, "parse_input")
            graph.add_edge("parse_input", "resolve_destination")
            graph.add_edge("resolve_destination", "search_attractions")
            graph.add_edge("resolve_destination", "query_weather")
            graph.add_edge("search_attractions", "recommend_hotels")
            graph.add_edge("search_attractions", "recommend_food")
            graph.add_edge("recommend_hotels", "complete_images")
            graph.add_edge(["query_weather", "recommend_food", "complete_images"], "plan_itinerary")
            graph.add_edge("plan_itinerary", "build_map_data")
            graph.add_edge("build_map_data", "validate_output")
            graph.add_edge("validate_output", END)
            return graph.compile()
        except Exception as exc:
            logger.exception("LangGraph工作流构建失败，将使用顺序降级 error={}", exc)
            return None

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
        result = self.workflow.invoke(initial_state) if self.workflow else self._run_sequential(initial_state)

        state = TripPlannerAgentState.model_validate(result)
        request_for_plan = state.normalized_request or request
        if not state.trip_plan:
            logger.warning("工作流未生成有效行程，使用规则引擎兜底")
            state.trip_plan = self._build_rule_based_plan(
                request_for_plan,
                state.attractions,
                state.hotels,
                state.weather_info,
                state.daily_meals,
                state.errors,
            )
            state.trip_plan.map_data = self._build_map_data(state.trip_plan, state.destination_location)

        logger.info(
            "Agent工作流完成 city={} days={} attractions={} hotels={} markers={} errors={}",
            state.trip_plan.city,
            len(state.trip_plan.days),
            sum(len(day.attractions) for day in state.trip_plan.days),
            len(state.trip_plan.hotels),
            len(state.trip_plan.map_data.markers) if state.trip_plan.map_data else 0,
            len(state.errors),
        )
        return state.trip_plan

    def _run_sequential(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = dict(state)
        for node in (
            self.parse_input_node,
            self.resolve_destination_node,
            self.search_attractions_node,
            self.query_weather_node,
            self.recommend_hotels_node,
            self.recommend_food_node,
            self.complete_images_node,
            self.plan_itinerary_node,
            self.build_map_data_node,
            self.validate_output_node,
        ):
            update = node(current)
            self._merge_state(current, update)
        return current

    @staticmethod
    def _merge_state(current: Dict[str, Any], update: Dict[str, Any]) -> None:
        errors = update.get("errors") or []
        for key, value in update.items():
            if key != "errors":
                current[key] = value
        if errors:
            current.setdefault("errors", [])
            current["errors"].extend(errors)

    def parse_input_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.request
        logger.info("节点: 输入解析与参数标准化 city={}", request.city)
        try:
            start = datetime.strptime(request.start_date, "%Y-%m-%d")
            end = datetime.strptime(request.end_date, "%Y-%m-%d")
            errors: List[str] = []
            if end < start:
                end = start + timedelta(days=max(request.travel_days, 1) - 1)
                errors.append("结束日期早于开始日期，已按旅行天数自动修正。")
            calculated_days = (end - start).days + 1
            normalized_days = max(1, min(30, calculated_days))
            normalized = request.model_copy(
                update={
                    "city": request.city.strip(),
                    "start_date": start.strftime("%Y-%m-%d"),
                    "end_date": (start + timedelta(days=normalized_days - 1)).strftime("%Y-%m-%d"),
                    "travel_days": normalized_days,
                    "preferences": [item.strip() for item in request.preferences if item.strip()],
                    "free_text_input": (request.free_text_input or "").strip(),
                }
            )
            return {"normalized_request": normalized, "errors": errors}
        except Exception as exc:
            logger.exception("输入标准化失败 error={}", exc)
            return {"normalized_request": request, "errors": [f"输入标准化失败：{exc}"]}

    def resolve_destination_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 动态目的地坐标解析 destination={}", request.city)
        name, location = self._resolve_destination(request)
        if location:
            logger.info(
                "目的地坐标解析成功 name={} lng={} lat={}",
                name,
                location.longitude,
                location.latitude,
            )
            return {"resolved_destination": name, "destination_location": location}
        message = f"未能解析“{request.city}”的经纬度，请检查目的地名称或配置 AMAP_API_KEY。"
        logger.warning(message)
        return {"resolved_destination": request.city, "destination_location": None, "errors": [message]}

    def search_attractions_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 景点搜索 city={} preferences={}", request.city, request.preferences)
        try:
            limit = max(8, request.travel_days * 3)
            pois: List[POIInfo] = []
            if agent_state.destination_location:
                pois.extend(self.amap_service.search_attractions_nearby(agent_state.destination_location, request.preferences, limit=limit))
            if len(pois) < limit:
                pois.extend(self.amap_service.search_attractions(request.city, request.preferences, limit=limit))
            pois = self._dedupe_pois(pois)
            attractions = [self._poi_to_attraction(poi, request.preferences) for poi in pois[:limit]]
            if not attractions:
                attractions = self._fallback_attractions(request.city, request.preferences, agent_state.destination_location)
            errors = [] if attractions else [f"未搜索到“{request.city}”的可用景点坐标，地图和行程将保持空状态。"]
            return {"attractions": attractions[:limit], "errors": errors}
        except Exception as exc:
            logger.exception("景点搜索节点失败 error={}", exc)
            fallback = self._fallback_attractions(request.city, request.preferences, agent_state.destination_location)
            return {"attractions": fallback, "errors": [f"景点搜索失败：{exc}"]}

    def query_weather_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 天气查询 city={}", request.city)
        try:
            weather = self.amap_service.get_weather(request.city)
            return {"weather_info": self._align_weather_dates(request, weather)}
        except Exception as exc:
            logger.exception("天气查询节点失败 error={}", exc)
            return {"weather_info": self._fallback_weather(request), "errors": [f"天气查询失败：{exc}"]}

    def recommend_hotels_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        center = self._itinerary_center(agent_state.attractions) or agent_state.destination_location
        logger.info("节点: 统一酒店推荐 city={} accommodation={}", request.city, request.accommodation)
        try:
            pois: List[POIInfo] = []
            if center:
                pois.extend(self.amap_service.search_hotels_nearby(center, request.accommodation, limit=8))
            if len(pois) < 3:
                pois.extend(self.amap_service.search_hotels(request.city, request.accommodation, limit=8))
            hotels = [self._poi_to_hotel(poi, request, center) for poi in self._dedupe_pois(pois)]
            hotels = self._filter_hotels_by_budget(hotels, request)
            if not hotels:
                hotels = self._fallback_hotels(request.city, request.accommodation, center)
            return {"hotels": hotels[:3]}
        except Exception as exc:
            logger.exception("酒店推荐节点失败 error={}", exc)
            return {
                "hotels": self._fallback_hotels(request.city, request.accommodation, center),
                "errors": [f"酒店推荐失败：{exc}"],
            }

    def recommend_food_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 美食推荐 city={} days={}", request.city, request.travel_days)
        daily_meals: List[List[Meal]] = []
        try:
            for day_index in range(request.travel_days):
                day_attractions = self._pick_day_attractions(agent_state.attractions, day_index, request.travel_days)
                day_center = self._itinerary_center(day_attractions) or agent_state.destination_location
                daily_meals.append(self._build_day_meals(request, day_index, day_attractions, day_center))
            return {"daily_meals": daily_meals}
        except Exception as exc:
            logger.exception("美食推荐节点失败 error={}", exc)
            for day_index in range(request.travel_days):
                daily_meals.append(self._fallback_meals(request.city, day_index, [], source="llm_fallback"))
            return {"daily_meals": daily_meals, "errors": [f"美食推荐失败：{exc}"]}

    def complete_images_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        request = agent_state.normalized_request or agent_state.request
        logger.info("节点: 图片补全 attractions={} hotels={}", len(agent_state.attractions), len(agent_state.hotels))
        try:
            attractions = self.image_service.enrich_attractions(agent_state.attractions, request.city)
            hotels = self.image_service.enrich_hotels(agent_state.hotels, request.city)
            return {"attractions": attractions, "hotels": hotels}
        except Exception as exc:
            logger.exception("图片补全节点失败 error={}", exc)
            return {"errors": [f"图片补全失败：{exc}"]}

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
            plan = self._build_rule_based_plan(
                request,
                agent_state.attractions,
                agent_state.hotels,
                agent_state.weather_info,
                agent_state.daily_meals,
                agent_state.errors,
            )
        plan = self._normalize_plan(plan, request, agent_state.hotels, agent_state.daily_meals, agent_state.errors)
        return {"trip_plan": plan}

    def build_map_data_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        logger.info("节点: 地图数据构建")
        if not agent_state.trip_plan:
            return {}
        map_data = self._build_map_data(agent_state.trip_plan, agent_state.destination_location)
        agent_state.trip_plan.map_data = map_data
        return {"map_data": map_data, "trip_plan": agent_state.trip_plan}

    def validate_output_node(self, state: TripGraphState) -> TripGraphState:
        agent_state = TripPlannerAgentState.model_validate(state)
        logger.info("节点: 结果校验与格式化")
        if not agent_state.trip_plan:
            return {}

        request = agent_state.normalized_request or agent_state.request
        plan = self._normalize_plan(
            TripPlan.model_validate(agent_state.trip_plan),
            request,
            agent_state.hotels,
            agent_state.daily_meals,
            agent_state.errors,
        )
        plan.weather_info = self._align_weather_dates(request, plan.weather_info or agent_state.weather_info)
        plan.budget = self._calculate_budget(plan)
        plan.map_data = self._build_map_data(plan, agent_state.destination_location)
        return {"trip_plan": plan, "map_data": plan.map_data}


_trip_planner: Optional[LangGraphTripPlanner] = None


def get_trip_planner_agent() -> LangGraphTripPlanner:
    global _trip_planner
    if _trip_planner is None:
        _trip_planner = LangGraphTripPlanner()
    return _trip_planner


# 兼容旧引用名称。
MultiAgentTripPlanner = LangGraphTripPlanner

