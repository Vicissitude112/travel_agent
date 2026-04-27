"""LangGraph 工作流状态模型。"""

from typing import List, Optional

from pydantic import BaseModel, Field

from ..models.schemas import Attraction, Hotel, MapData, TripPlan, TripRequest, WeatherInfo


class TripPlannerAgentState(BaseModel):
    """每个 LangGraph 节点共享的状态。

    节点只读写自己负责的字段，便于排查每一步的数据来源和异常。
    """

    request: TripRequest = Field(..., description="原始请求")
    normalized_request: Optional[TripRequest] = Field(default=None, description="标准化后的请求")
    attractions: List[Attraction] = Field(default_factory=list, description="候选景点")
    hotels: List[Hotel] = Field(default_factory=list, description="候选酒店")
    weather_info: List[WeatherInfo] = Field(default_factory=list, description="天气")
    trip_plan: Optional[TripPlan] = Field(default=None, description="生成的行程")
    map_data: Optional[MapData] = Field(default=None, description="地图数据")
    errors: List[str] = Field(default_factory=list, description="节点错误摘要")
