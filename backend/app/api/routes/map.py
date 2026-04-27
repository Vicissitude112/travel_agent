"""地图服务 API 路由。"""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from ...models.schemas import POISearchResponse, RouteRequest, RouteResponse, WeatherResponse
from ...services.amap_service import get_amap_service

router = APIRouter(prefix="/map", tags=["地图服务"])


@router.get("/poi", response_model=POISearchResponse, summary="搜索POI")
async def search_poi(
    keywords: str = Query(..., description="搜索关键词", examples=["故宫"]),
    city: str = Query(..., description="城市", examples=["北京"]),
    citylimit: bool = Query(True, description="是否限制在城市范围内"),
) -> POISearchResponse:
    logger.info("请求入口: 地图POI搜索 keywords={} city={}", keywords, city)
    try:
        pois = get_amap_service().search_poi(keywords, city, citylimit)
        return POISearchResponse(success=True, message="POI搜索成功", data=pois)
    except Exception as exc:
        logger.exception("POI搜索失败 keywords={} city={} error={}", keywords, city, exc)
        raise HTTPException(status_code=500, detail=f"POI搜索失败: {exc}") from exc


@router.get("/weather", response_model=WeatherResponse, summary="查询天气")
async def get_weather(city: str = Query(..., description="城市名称", examples=["北京"])) -> WeatherResponse:
    logger.info("请求入口: 天气查询 city={}", city)
    try:
        weather_info = get_amap_service().get_weather(city)
        return WeatherResponse(success=True, message="天气查询成功", data=weather_info)
    except Exception as exc:
        logger.exception("天气查询失败 city={} error={}", city, exc)
        raise HTTPException(status_code=500, detail=f"天气查询失败: {exc}") from exc


@router.post("/route", response_model=RouteResponse, summary="规划路线")
async def plan_route(request: RouteRequest) -> RouteResponse:
    logger.info("请求入口: 路线规划 type={}", request.route_type)
    try:
        route_info = get_amap_service().plan_route(
            origin_address=request.origin_address,
            destination_address=request.destination_address,
            origin_city=request.origin_city,
            destination_city=request.destination_city,
            route_type=request.route_type,
        )
        return RouteResponse(success=True, message="路线规划成功", data=route_info)
    except Exception as exc:
        logger.exception("路线规划失败 error={}", exc)
        raise HTTPException(status_code=500, detail=f"路线规划失败: {exc}") from exc


@router.get("/health", summary="地图服务健康检查")
async def health_check() -> dict:
    settings = get_amap_service().settings
    return {
        "status": "healthy",
        "service": "map-service",
        "amap_api_key": "已配置" if settings.amap_api_key else "未配置",
    }
