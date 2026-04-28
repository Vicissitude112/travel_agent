"""餐饮推荐相关辅助逻辑。"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from ..models.schemas import Attraction, Location, Meal, POIInfo, TripRequest

if TYPE_CHECKING:
    from ..services.amap_service import AmapService
    from ..services.llm_service import LLMService


class TripFoodMixin:
    """封装美食 Agent 的 POI 推荐和降级策略。"""

    # 由 LangGraphTripPlanner.__init__ 注入，Mixin 不单独初始化服务。
    amap_service: "AmapService"
    llm_service: "LLMService"

    def _build_day_meals(
        self,
        request: TripRequest,
        day_index: int,
        attractions: List[Attraction],
        center: Optional[Location],
    ) -> List[Meal]:
        meals: List[Meal] = []
        used: set[str] = set()
        anchor = attractions[0].name if attractions else request.city
        if center:
            for meal_type, keyword in (
                ("breakfast", "早餐"),
                ("lunch", "特色菜 餐厅"),
                ("dinner", "晚餐 餐厅"),
                ("snack", "小吃 夜市"),
            ):
                poi = self._pick_food_poi(center, keyword, used)
                if poi:
                    used.add(poi.id or poi.name)
                    meals.append(self._meal_from_poi(meal_type, poi, anchor, request.accommodation))

        existing_types = {meal.type for meal in meals}
        if {"breakfast", "lunch", "dinner"}.issubset(existing_types):
            return meals[:4]

        llm_meals = self.llm_service.build_day_meals(request, day_index, [item.name for item in attractions])
        if llm_meals:
            meals_by_type = {meal.type: meal for meal in meals}
            for meal in llm_meals:
                meals_by_type.setdefault(meal.type, meal)
            meals = list(meals_by_type.values())

        existing_types = {meal.type for meal in meals}
        fallback = self._fallback_meals(request.city, day_index, attractions, source="llm_fallback")
        for meal in fallback:
            if meal.type not in existing_types:
                meals.append(meal)
                existing_types.add(meal.type)
        return sorted(meals[:4], key=lambda item: ["breakfast", "lunch", "dinner", "snack"].index(item.type))

    def _pick_food_poi(self, center: Location, keyword: str, used: set[str]) -> Optional[POIInfo]:
        pois = self.amap_service.search_foods_nearby(center, keyword, limit=6)
        for poi in pois:
            key = poi.id or poi.name
            if key not in used:
                return poi
        return None

    def _meal_from_poi(self, meal_type: str, poi: POIInfo, anchor: str, accommodation: str) -> Meal:
        return Meal(
            type=meal_type,  # type: ignore[arg-type]
            name=poi.name,
            address=poi.address,
            location=poi.location,
            description=f"靠近{anchor}周边，适合按当天路线就近安排，减少绕路时间。",
            estimated_cost=self._estimate_meal_cost(meal_type, accommodation),
            source="amap_poi",
        )

    def _fallback_meals(
        self,
        city: str,
        day_index: int,
        attractions: List[Attraction],
        source: str = "llm_fallback",
    ) -> List[Meal]:
        foods = self._food_profile(city)
        anchor = attractions[0].name if attractions else f"{city}核心区"
        return [
            Meal(
                type="breakfast",
                name=f"{foods[0]}早餐",
                address=anchor,
                description=f"围绕{anchor}就近选择，优先安排出餐快、排队可控的本地早餐。",
                estimated_cost=35,
                source=source,
            ),
            Meal(
                type="lunch",
                name=foods[1],
                address=anchor,
                description="安排在上午景点结束后，选择步行或短途打车可达的餐厅。",
                estimated_cost=70,
                source=source,
            ),
            Meal(
                type="dinner",
                name=foods[2],
                address=f"{city}商圈或老街",
                description="晚餐结合当天返程路线，适合补充城市代表菜和休息时间。",
                estimated_cost=95 + day_index * 10,
                source=source,
            ),
            Meal(
                type="snack",
                name=foods[3],
                address=f"{city}夜市或特色街区",
                description="作为夜游或饭后散步补充项，可根据体力选择。",
                estimated_cost=45,
                source=source,
            ),
        ]

    @staticmethod
    def _food_profile(city: str) -> List[str]:
        profiles = {
            "西安": ["肉夹馍和胡辣汤", "羊肉泡馍", "biangbiang面", "回民街小吃"],
            "成都": ["钟水饺和担担面", "川菜小馆", "火锅", "宽窄巷子小吃"],
            "重庆": ["重庆小面", "江湖菜", "重庆火锅", "解放碑夜市小吃"],
            "北京": ["豆汁焦圈或炒肝", "老北京炸酱面", "北京烤鸭", "护国寺小吃"],
            "上海": ["生煎和小笼包", "本帮菜", "蟹粉面", "城隍庙小吃"],
            "广州": ["早茶点心", "烧腊饭", "粤菜小馆", "西关小吃"],
            "杭州": ["葱包桧和片儿川", "杭帮菜", "西湖醋鱼", "河坊街小吃"],
            "南京": ["鸭血粉丝汤", "盐水鸭", "金陵菜", "夫子庙小吃"],
        }
        for key, foods in profiles.items():
            if key in city:
                return foods
        return [f"{city}本地早餐", f"{city}特色午餐", f"{city}风味晚餐", f"{city}夜市小吃"]

    @staticmethod
    def _estimate_meal_cost(meal_type: str, accommodation: str) -> int:
        base = {"breakfast": 35, "lunch": 70, "dinner": 95, "snack": 45}.get(meal_type, 60)
        if "豪华" in accommodation:
            return int(base * 1.7)
        if "经济" in accommodation or "民宿" in accommodation:
            return int(base * 0.85)
        return base
