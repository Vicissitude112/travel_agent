"""旅行规划 API 路由。"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from ...agents.trip_planner_agent import get_trip_planner_agent
from ...models.schemas import TripPlanResponse, TripRequest

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求，生成包含景点、酒店、天气、图片和地图数据的旅行计划。",
)
async def plan_trip(request: TripRequest) -> TripPlanResponse:
    """生成旅行计划。"""
    logger.info(
        "请求入口: 旅行规划 city={} start={} end={} days={}",
        request.city,
        request.start_date,
        request.end_date,
        request.travel_days,
    )
    try:
        planner = get_trip_planner_agent()
        trip_plan = planner.plan_trip(request)
        logger.info(
            "最终结果摘要 city={} days={} markers={}",
            trip_plan.city,
            len(trip_plan.days),
            len(trip_plan.map_data.markers) if trip_plan.map_data else 0,
        )
        return TripPlanResponse(success=True, message="旅行计划生成成功", data=trip_plan)
    except Exception as exc:
        logger.exception("生成旅行计划失败 error={}", exc)
        raise HTTPException(status_code=500, detail=f"生成旅行计划失败: {exc}") from exc


@router.get("/health", summary="旅行规划服务健康检查")
async def health_check() -> dict:
    try:
        planner = get_trip_planner_agent()
        return {
            "status": "healthy",
            "service": "trip-planner",
            "workflow_engine": planner.engine_name,
        }
    except Exception as exc:
        logger.exception("旅行规划服务不可用 error={}", exc)
        raise HTTPException(status_code=503, detail=f"服务不可用: {exc}") from exc
