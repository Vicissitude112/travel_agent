"""POI 与图片相关 API 路由。"""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from ...models.schemas import ImageResponse, POIInfo
from ...services.amap_service import get_amap_service
from ...services.image_service import ImageLookupContext, get_image_service

router = APIRouter(prefix="/poi", tags=["POI"])


class POIDetailResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None


@router.get("/detail/{poi_id}", response_model=POIDetailResponse, summary="获取POI详情")
async def get_poi_detail(poi_id: str) -> POIDetailResponse:
    try:
        detail = get_amap_service().get_poi_detail(poi_id)
        return POIDetailResponse(success=True, message="获取POI详情成功", data=detail)
    except Exception as exc:
        logger.exception("获取POI详情失败 poi_id={} error={}", poi_id, exc)
        raise HTTPException(status_code=500, detail=f"获取POI详情失败: {exc}") from exc


@router.get("/search", summary="搜索POI")
async def search_poi(
    keywords: str = Query(..., description="关键词"),
    city: str = Query("北京", description="城市"),
) -> dict:
    try:
        pois = get_amap_service().search_poi(keywords, city)
        return {"success": True, "message": "搜索成功", "data": pois}
    except Exception as exc:
        logger.exception("搜索POI失败 keywords={} city={} error={}", keywords, city, exc)
        raise HTTPException(status_code=500, detail=f"搜索POI失败: {exc}") from exc


@router.get("/photo", response_model=ImageResponse, summary="获取景点或酒店图片")
async def get_photo(
    name: str = Query(..., description="名称"),
    city: str = Query("", description="城市"),
    is_hotel: bool = Query(False, description="是否酒店"),
) -> ImageResponse:
    try:
        image = get_image_service().get_image(ImageLookupContext(query=name, city=city, is_hotel=is_hotel))
        return ImageResponse(success=True, message="获取图片成功", data=image)
    except Exception as exc:
        logger.exception("获取图片失败 name={} error={}", name, exc)
        raise HTTPException(status_code=500, detail=f"获取图片失败: {exc}") from exc
