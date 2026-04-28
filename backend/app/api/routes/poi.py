"""POI 与图片相关 API 路由。"""

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel

from ...config import get_settings
from ...models.schemas import ImageResponse, POIInfo
from ...services.amap_service import get_amap_service
from ...services.image_service import ImageLookupContext, get_image_service

router = APIRouter(prefix="/poi", tags=["POI"])

BACKEND_DIR = Path(__file__).resolve().parents[3]
IMAGE_TEMP_DIR = BACKEND_DIR / "image_temp"
CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
    "image/svg+xml": ".svg",
}


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


def _safe_folder_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip(), flags=re.UNICODE).strip(".-")
    return (cleaned or "default")[:80]


def _media_type_from_path(path: Path) -> str:
    for content_type, ext in CONTENT_TYPE_EXT.items():
        if path.suffix.lower() == ext:
            return content_type
    return "image/jpeg"


@router.get("/image-proxy", summary="图片导出代理")
async def image_proxy(
    url: str = Query(..., description="需要代理的图片URL"),
    folder: str = Query("default", description="导出图片缓存子目录"),
) -> Response:
    """为导出提供同源图片，并按需缓存到 backend/image_temp。

    普通页面渲染不会调用该接口；只有 PNG/PDF 导出时前端才请求，避免浪费资源。
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="仅支持 http/https 图片URL")

    folder_name = _safe_folder_name(folder)
    cache_dir = IMAGE_TEMP_DIR / folder_name
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    existing = next(cache_dir.glob(f"{cache_key}.*"), None) if cache_dir.exists() else None
    if existing and existing.is_file():
        logger.info("图片代理命中缓存 folder={} file={}", folder_name, existing.name)
        return Response(
            content=existing.read_bytes(),
            media_type=_media_type_from_path(existing),
            headers={"Cache-Control": "public, max-age=86400"},
        )

    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.image_timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Referer": "https://ditu.amap.com/",
                },
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("图片代理失败 url={} error={}", url, exc)
        raise HTTPException(status_code=502, detail="图片代理获取失败") from exc

    content_type = response.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="目标URL不是图片资源")

    media_type = content_type.split(";", 1)[0].lower()
    extension = CONTENT_TYPE_EXT.get(media_type, ".jpg")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{cache_key}{extension}"
    cache_file.write_bytes(response.content)
    logger.info("图片代理写入缓存 folder={} file={} bytes={}", folder_name, cache_file.name, len(response.content))

    return Response(
        content=response.content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
