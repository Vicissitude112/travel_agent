"""兼容旧路由的 Unsplash 服务包装。"""

from typing import List, Optional

from .image_service import ImageLookupContext, UnsplashImageProvider


class UnsplashService:
    def __init__(self) -> None:
        self.provider = UnsplashImageProvider()

    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        image = self.provider.search(ImageLookupContext(query=query))
        if not image:
            return []
        return [
            {
                "url": image.url,
                "thumb": image.thumb_url,
                "source": image.source,
                "attribution": image.attribution,
            }
        ][:per_page]

    def get_photo_url(self, query: str) -> Optional[str]:
        image = self.provider.search(ImageLookupContext(query=query))
        return image.url if image else None


_unsplash_service: Optional[UnsplashService] = None


def get_unsplash_service() -> UnsplashService:
    global _unsplash_service
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    return _unsplash_service
