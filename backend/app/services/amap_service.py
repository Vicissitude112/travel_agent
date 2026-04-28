"""高德地图 Web API 服务封装。

重构后不再通过教学框架的工具包装调用高德，而是后端直接请求高德
REST API，并把外部返回标准化为 Pydantic 模型。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import httpx
from loguru import logger

from ..config import get_settings
from ..models.schemas import Location, POIInfo, RouteInfo, WeatherInfo


class AmapService:
    """高德地图服务。外部 API 失败时返回空数据，由 Agent 节点做降级。"""

    base_url = "https://restapi.amap.com"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.amap_api_key:
            logger.warning("高德API Key未配置，跳过外部调用 path={}", path)
            return {}

        safe_params = {key: value for key, value in params.items() if key != "key"}
        logger.info("调用高德API path={} params={}", path, safe_params)

        query_params = dict(params)
        query_params["key"] = self.settings.amap_api_key
        try:
            with httpx.Client(timeout=self.settings.amap_timeout_seconds) as client:
                response = client.get(f"{self.base_url}{path}", params=query_params)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.exception("高德API调用失败 path={} error={}", path, exc)
            return {}

        if data.get("status") not in (None, "1", 1):
            logger.warning("高德API返回异常 path={} info={}", path, data.get("info"))
            return {}
        return data

    @staticmethod
    def _parse_location(value: Any) -> Optional[Location]:
        if not value:
            return None
        if isinstance(value, dict):
            lng = value.get("longitude") or value.get("lng")
            lat = value.get("latitude") or value.get("lat")
            if lng is not None and lat is not None:
                return Location(longitude=float(lng), latitude=float(lat))
        if isinstance(value, str) and "," in value:
            lng, lat = value.split(",", 1)
            return Location(longitude=float(lng), latitude=float(lat))
        return None

    @staticmethod
    def _first_text(value: Any) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value if item)
        return str(value or "")

    @staticmethod
    def _parse_rating(poi: Dict[str, Any]) -> Optional[float]:
        rating = poi.get("biz_ext", {}).get("rating") if isinstance(poi.get("biz_ext"), dict) else None
        if rating in ("", None, []):
            return None
        try:
            return float(rating)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_photos(poi: Dict[str, Any]) -> List[str]:
        photos: List[str] = []
        for photo in poi.get("photos") or []:
            if isinstance(photo, dict) and photo.get("url"):
                photos.append(photo["url"])
        return photos

    def _parse_pois(self, pois: Iterable[Dict[str, Any]]) -> List[POIInfo]:
        results: List[POIInfo] = []
        for poi in pois:
            try:
                location = self._parse_location(poi.get("location"))
                if not location:
                    continue
                results.append(
                    POIInfo(
                        id=str(poi.get("id") or ""),
                        name=str(poi.get("name") or ""),
                        type=str(poi.get("type") or ""),
                        address=self._first_text(poi.get("address")),
                        location=location,
                        tel=self._first_text(poi.get("tel")) or None,
                        rating=self._parse_rating(poi),
                        photos=self._parse_photos(poi),
                        raw=poi,
                    )
                )
            except Exception as exc:
                logger.warning("解析高德POI失败 name={} error={}", poi.get("name"), exc)
        return results

    def search_poi(self, keywords: str, city: str, citylimit: bool = True, page_size: int = 12) -> List[POIInfo]:
        data = self._get(
            "/v3/place/text",
            {
                "keywords": keywords,
                "city": city,
                "citylimit": "true" if citylimit else "false",
                "offset": page_size,
                "page": 1,
                "children": 0,
                "extensions": "all",
            },
        )
        pois = self._parse_pois(data.get("pois") or [])
        logger.info("高德POI搜索完成 city={} keywords={} count={}", city, keywords, len(pois))
        return pois

    def search_poi_around(
        self,
        keywords: str,
        location: Location,
        radius: int = 5000,
        page_size: int = 12,
    ) -> List[POIInfo]:
        """围绕动态坐标搜索 POI，适合景区、区县、路线等非标准城市输入。"""
        data = self._get(
            "/v3/place/around",
            {
                "keywords": keywords,
                "location": f"{location.longitude},{location.latitude}",
                "radius": radius,
                "offset": page_size,
                "page": 1,
                "sortrule": "distance",
                "extensions": "all",
            },
        )
        pois = self._parse_pois(data.get("pois") or [])
        logger.info("高德周边POI搜索完成 keywords={} count={}", keywords, len(pois))
        return pois

    def search_attractions(self, city: str, preferences: List[str], limit: int = 12) -> List[POIInfo]:
        keywords = preferences or ["景点"]
        merged: Dict[str, POIInfo] = {}
        for keyword in keywords:
            query = keyword if "景点" in keyword or "公园" in keyword else f"{keyword} 景点"
            for poi in self.search_poi(query, city, page_size=limit):
                key = poi.id or f"{poi.name}:{poi.address}"
                merged.setdefault(key, poi)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        return list(merged.values())[:limit]

    def search_attractions_nearby(self, location: Location, preferences: List[str], limit: int = 12) -> List[POIInfo]:
        keywords = preferences or ["景点"]
        merged: Dict[str, POIInfo] = {}
        for keyword in keywords:
            query = keyword if any(word in keyword for word in ("景点", "公园", "博物馆", "古镇")) else f"{keyword} 景点"
            for poi in self.search_poi_around(query, location, radius=12000, page_size=limit):
                key = poi.id or f"{poi.name}:{poi.address}"
                merged.setdefault(key, poi)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        if len(merged) < limit:
            for poi in self.search_poi_around("景点", location, radius=12000, page_size=limit):
                key = poi.id or f"{poi.name}:{poi.address}"
                merged.setdefault(key, poi)
                if len(merged) >= limit:
                    break
        return list(merged.values())[:limit]

    def search_hotels(self, city: str, accommodation: str, limit: int = 8) -> List[POIInfo]:
        merged: Dict[str, POIInfo] = {}
        keywords = [f"{accommodation or ''} 酒店".strip(), "酒店", "宾馆"]
        for keyword in keywords:
            for poi in self.search_poi(keyword, city, page_size=limit):
                key = poi.id or f"{poi.name}:{poi.address}"
                merged.setdefault(key, poi)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        return list(merged.values())[:limit]

    def search_hotels_nearby(
        self,
        location: Location,
        accommodation: str,
        limit: int = 8,
    ) -> List[POIInfo]:
        merged: Dict[str, POIInfo] = {}
        keywords = [f"{accommodation or ''} 酒店".strip(), "酒店", "宾馆"]
        for keyword in keywords:
            for poi in self.search_poi_around(keyword, location, radius=7000, page_size=limit):
                key = poi.id or f"{poi.name}:{poi.address}"
                merged.setdefault(key, poi)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        return list(merged.values())[:limit]

    def search_foods_nearby(self, location: Location, keyword: str, limit: int = 6) -> List[POIInfo]:
        return self.search_poi_around(keyword, location, radius=3500, page_size=limit)

    def get_weather(self, city: str) -> List[WeatherInfo]:
        data = self._get(
            "/v3/weather/weatherInfo",
            {"city": city, "extensions": "all", "output": "JSON"},
        )
        weather: List[WeatherInfo] = []
        for forecast in data.get("forecasts") or []:
            for cast in forecast.get("casts") or []:
                try:
                    weather.append(
                        WeatherInfo(
                            date=cast.get("date") or "",
                            day_weather=cast.get("dayweather") or "",
                            night_weather=cast.get("nightweather") or "",
                            day_temp=cast.get("daytemp") or 0,
                            night_temp=cast.get("nighttemp") or 0,
                            wind_direction=cast.get("daywind") or "",
                            wind_power=cast.get("daypower") or "",
                        )
                    )
                except Exception as exc:
                    logger.warning("解析天气失败 city={} error={}", city, exc)
        logger.info("高德天气查询完成 city={} count={}", city, len(weather))
        return weather

    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        params: Dict[str, Any] = {"address": address}
        if city:
            params["city"] = city
        data = self._get("/v3/geocode/geo", params)
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return None
        return self._parse_location(geocodes[0].get("location"))

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        data = self._get("/v3/place/detail", {"id": poi_id, "extensions": "all"})
        pois = data.get("pois") or []
        return pois[0] if pois else {}

    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking",
    ) -> RouteInfo:
        """保留路线接口，无法稳定规划时返回可展示的空路线。"""
        origin = self.geocode(origin_address, origin_city)
        destination = self.geocode(destination_address, destination_city)
        if not origin or not destination:
            return RouteInfo(route_type=route_type, description="未能获取完整坐标，暂无法规划路线。")
        return RouteInfo(
            route_type=route_type,
            description=(
                f"已解析起终点坐标：{origin.longitude:.5f},{origin.latitude:.5f} "
                f"-> {destination.longitude:.5f},{destination.latitude:.5f}"
            ),
        )


_amap_service: Optional[AmapService] = None


def get_amap_service() -> AmapService:
    global _amap_service
    if _amap_service is None:
        _amap_service = AmapService()
    return _amap_service
