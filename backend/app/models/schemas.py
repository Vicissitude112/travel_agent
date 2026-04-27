"""旅行助手的结构化数据模型。"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TripRequest(BaseModel):
    """前端提交的旅行规划请求。"""

    city: str = Field(..., description="目的地城市", examples=["北京"])
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", examples=["2026-05-01"])
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", examples=["2026-05-03"])
    travel_days: int = Field(..., description="旅行天数", ge=1, le=30, examples=[3])
    transportation: str = Field(default="公共交通", description="交通方式")
    accommodation: str = Field(default="舒适型酒店", description="住宿偏好")
    preferences: List[str] = Field(default_factory=list, description="旅行偏好标签")
    free_text_input: Optional[str] = Field(default="", description="额外要求")

    @field_validator("city", "start_date", "end_date", "transportation", "accommodation", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class POISearchRequest(BaseModel):
    keywords: str = Field(..., description="搜索关键词")
    city: str = Field(..., description="城市")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    origin_address: str = Field(..., description="起点地址")
    destination_address: str = Field(..., description="终点地址")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: Literal["walking", "driving", "transit"] = Field(default="walking", description="路线类型")


class Location(BaseModel):
    """地理位置，经度在前、纬度在后，匹配高德地图 JS SDK。"""

    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class ImageInfo(BaseModel):
    """统一图片结构，便于多图片源降级。"""

    url: str = Field(..., description="图片URL")
    source: str = Field(default="default", description="图片来源")
    attribution: Optional[str] = Field(default=None, description="作者或版权信息")
    thumb_url: Optional[str] = Field(default=None, description="缩略图URL")


class Attraction(BaseModel):
    name: str = Field(..., description="景点名称")
    address: str = Field(default="", description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(default=90, ge=10, le=600, description="建议游览时长，分钟")
    description: str = Field(default="", description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="评分")
    photos: List[str] = Field(default_factory=list, description="POI原始图片URL列表")
    poi_id: Optional[str] = Field(default="", description="高德POI ID")
    image: Optional[ImageInfo] = Field(default=None, description="补全后的主图")
    image_url: Optional[str] = Field(default=None, description="兼容旧前端的图片URL")
    ticket_price: int = Field(default=0, ge=0, description="门票价格")
    recommendation_reason: str = Field(default="", description="推荐理由")

    @model_validator(mode="after")
    def sync_image_url(self) -> "Attraction":
        if self.image and not self.image_url:
            self.image_url = self.image.url
        return self


class Meal(BaseModel):
    type: Literal["breakfast", "lunch", "dinner", "snack"] = Field(..., description="餐饮类型")
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, ge=0, description="预计费用")


class Hotel(BaseModel):
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格区间")
    rating: Union[str, float, None] = Field(default="", description="评分")
    distance: str = Field(default="", description="与核心景点距离")
    type: str = Field(default="酒店", description="酒店类型")
    estimated_cost: int = Field(default=0, ge=0, description="每晚预估费用")
    photos: List[str] = Field(default_factory=list, description="POI原始图片URL列表")
    poi_id: Optional[str] = Field(default="", description="高德POI ID")
    image: Optional[ImageInfo] = Field(default=None, description="补全后的主图")
    image_url: Optional[str] = Field(default=None, description="兼容旧前端的图片URL")
    recommendation_reason: str = Field(default="", description="推荐理由")

    @model_validator(mode="after")
    def sync_image_url(self) -> "Hotel":
        if self.image and not self.image_url:
            self.image_url = self.image.url
        return self


class DayPlan(BaseModel):
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_index: int = Field(..., ge=0, description="第几天，从0开始")
    description: str = Field(default="", description="当日行程概述")
    transportation: str = Field(default="", description="交通方式")
    accommodation: str = Field(default="", description="住宿偏好")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    attractions: List[Attraction] = Field(default_factory=list, description="景点列表")
    meals: List[Meal] = Field(default_factory=list, description="餐饮列表")


class WeatherInfo(BaseModel):
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")

    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, value: Any) -> int:
        if isinstance(value, str):
            cleaned = value.replace("°C", "").replace("℃", "").replace("°", "").strip()
            try:
                return int(float(cleaned))
            except ValueError:
                return 0
        return int(value or 0)


class Budget(BaseModel):
    total_attractions: int = Field(default=0, ge=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, ge=0, description="酒店总费用")
    total_meals: int = Field(default=0, ge=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, ge=0, description="交通总费用")
    total: int = Field(default=0, ge=0, description="总费用")


class MapMarker(BaseModel):
    id: str = Field(..., description="前端Marker唯一ID")
    marker_type: Literal["attraction", "hotel"] = Field(..., description="标记类型")
    name: str = Field(..., description="名称")
    address: str = Field(default="", description="地址")
    location: Location = Field(..., description="位置")
    day_index: Optional[int] = Field(default=None, description="所属第几天")
    order: Optional[int] = Field(default=None, description="当日顺序")
    rating: Optional[Union[str, float]] = Field(default=None, description="评分")
    image_url: Optional[str] = Field(default=None, description="展示图")
    description: Optional[str] = Field(default=None, description="描述")
    extra: Dict[str, Any] = Field(default_factory=dict, description="前端弹窗补充字段")


class MapData(BaseModel):
    center: Location = Field(..., description="地图中心点")
    markers: List[MapMarker] = Field(default_factory=list, description="地图标记")
    bounds: List[Location] = Field(default_factory=list, description="视野范围点")


class TripPlan(BaseModel):
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(default_factory=list, description="每日行程")
    weather_info: List[WeatherInfo] = Field(default_factory=list, description="天气信息")
    overall_suggestions: str = Field(default="", description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")
    map_data: Optional[MapData] = Field(default=None, description="地图渲染数据")


class TripPlanResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")


class POIInfo(BaseModel):
    id: str = Field(default="", description="POI ID")
    name: str = Field(..., description="名称")
    type: str = Field(default="", description="类型")
    address: str = Field(default="", description="地址")
    location: Location = Field(..., description="坐标")
    tel: Optional[str] = Field(default=None, description="电话")
    rating: Optional[float] = Field(default=None, description="评分")
    photos: List[str] = Field(default_factory=list, description="POI图片")
    raw: Dict[str, Any] = Field(default_factory=dict, description="原始字段")


class POISearchResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[POIInfo] = Field(default_factory=list, description="POI列表")


class RouteInfo(BaseModel):
    distance: float = Field(default=0, description="距离，米")
    duration: int = Field(default=0, description="时间，秒")
    route_type: str = Field(default="walking", description="路线类型")
    description: str = Field(default="", description="路线描述")


class RouteResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[RouteInfo] = Field(default=None, description="路线信息")


class WeatherResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[WeatherInfo] = Field(default_factory=list, description="天气信息")


class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")


class ImageResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[ImageInfo] = Field(default=None, description="图片信息")
