"""图片服务与多 Provider 降级。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote

import httpx
from loguru import logger

from ..config import get_settings
from ..models.schemas import Attraction, Hotel, ImageInfo


@dataclass
class ImageLookupContext:
    query: str
    city: str = ""
    poi_photos: List[str] = field(default_factory=list)
    is_hotel: bool = False


class ImageProvider(ABC):
    source: str

    @abstractmethod
    def search(self, context: ImageLookupContext) -> Optional[ImageInfo]:
        """搜索图片，找不到时返回 None，交给下一个 Provider。"""


class AmapPoiImageProvider(ImageProvider):
    source = "amap_poi"

    def search(self, context: ImageLookupContext) -> Optional[ImageInfo]:
        if not context.poi_photos:
            return None
        return ImageInfo(
            url=context.poi_photos[0],
            thumb_url=context.poi_photos[0],
            source=self.source,
            attribution="高德POI图片",
        )


class UnsplashImageProvider(ImageProvider):
    source = "unsplash"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = "https://api.unsplash.com/search/photos"

    def search(self, context: ImageLookupContext) -> Optional[ImageInfo]:
        if not self.settings.unsplash_access_key:
            return None

        query_parts = [context.query, context.city]
        if context.is_hotel:
            query_parts.append("hotel")
        else:
            query_parts.extend(["China", "landmark"])
        query = " ".join(part for part in query_parts if part)

        try:
            with httpx.Client(timeout=self.settings.image_timeout_seconds) as client:
                response = client.get(
                    self.base_url,
                    params={
                        "query": query,
                        "per_page": 1,
                        "orientation": "landscape",
                        "client_id": self.settings.unsplash_access_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("Unsplash图片搜索失败 query={} error={}", query, exc)
            return None

        results = payload.get("results") or []
        if not results:
            return None

        photo = results[0]
        user = photo.get("user") or {}
        urls = photo.get("urls") or {}
        if not urls.get("regular"):
            return None
        return ImageInfo(
            url=urls["regular"],
            thumb_url=urls.get("thumb"),
            source=self.source,
            attribution=f"Photo by {user.get('name', 'Unsplash')} on Unsplash",
        )


class PlaceholderImageProvider(ImageProvider):
    source = "default"

    def search(self, context: ImageLookupContext) -> Optional[ImageInfo]:
        label = quote(context.query[:24] or "Travel")
        return ImageInfo(
            url=f"https://placehold.co/960x600/e6f4ff/1677ff?text={label}",
            thumb_url=f"https://placehold.co/320x200/e6f4ff/1677ff?text={label}",
            source=self.source,
            attribution="默认占位图",
        )


class ImageService:
    """统一图片补全服务，按高德POI图 -> Unsplash -> 占位图降级。"""

    def __init__(self) -> None:
        self.providers: List[ImageProvider] = [
            AmapPoiImageProvider(),
            UnsplashImageProvider(),
            PlaceholderImageProvider(),
        ]

    def get_image(self, context: ImageLookupContext) -> ImageInfo:
        for provider in self.providers:
            image = provider.search(context)
            if image:
                logger.info("图片命中 source={} query={}", image.source, context.query)
                return image
        return PlaceholderImageProvider().search(context)  # type: ignore[return-value]

    def enrich_attractions(self, attractions: List[Attraction], city: str) -> List[Attraction]:
        for attraction in attractions:
            image = self.get_image(
                ImageLookupContext(
                    query=attraction.name,
                    city=city,
                    poi_photos=attraction.photos,
                    is_hotel=False,
                )
            )
            attraction.image = image
            attraction.image_url = image.url
        return attractions

    def enrich_hotels(self, hotels: List[Hotel], city: str) -> List[Hotel]:
        for hotel in hotels:
            image = self.get_image(
                ImageLookupContext(
                    query=f"{hotel.name} {city} hotel",
                    city=city,
                    poi_photos=hotel.photos,
                    is_hotel=True,
                )
            )
            hotel.image = image
            hotel.image_url = image.url
        return hotels


_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service
