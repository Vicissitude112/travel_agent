"""LangChain LLM 服务封装。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from ..config import get_settings
from ..models.schemas import Attraction, Hotel, TripPlan, TripRequest, WeatherInfo


class LLMService:
    """用 LangChain 调用兼容 OpenAI 协议的模型。

    该服务只在密钥和依赖可用时启用；失败时上层 LangGraph 节点会降级为规则规划。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._chat_model: Any = None

    @property
    def available(self) -> bool:
        return bool(self.settings.effective_llm_api_key)

    def _get_chat_model(self) -> Any:
        if self._chat_model is not None:
            return self._chat_model
        if not self.available:
            raise RuntimeError("LLM API Key未配置")

        try:
            from langchain_openai import ChatOpenAI
        except Exception as exc:
            raise RuntimeError("langchain-openai未安装") from exc

        self._chat_model = ChatOpenAI(
            api_key=self.settings.effective_llm_api_key,
            base_url=self.settings.effective_llm_base_url,
            model=self.settings.effective_llm_model,
            timeout=self.settings.llm_timeout_seconds,
            temperature=0.3,
        )
        logger.info("LangChain LLM初始化完成 model={}", self.settings.effective_llm_model)
        return self._chat_model

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        raw = fenced.group(1) if fenced else None
        if raw is None and "{" in text and "}" in text:
            raw = text[text.find("{") : text.rfind("}") + 1]
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("LLM JSON解析失败 error={}", exc)
            return None

    def build_trip_plan(
        self,
        request: TripRequest,
        attractions: List[Attraction],
        hotels: List[Hotel],
        weather_info: List[WeatherInfo],
    ) -> Optional[TripPlan]:
        if not self.available:
            logger.info("LLM未配置，跳过模型规划")
            return None

        prompt = self._build_prompt(request, attractions, hotels, weather_info)
        try:
            chat_model = self._get_chat_model()
            response = chat_model.invoke(prompt)
            content = getattr(response, "content", str(response))
            payload = self._extract_json(content)
            if not payload:
                return None
            plan = TripPlan.model_validate(payload)
            logger.info("LLM行程规划成功 city={} days={}", plan.city, len(plan.days))
            return plan
        except RuntimeError as exc:
            logger.warning("LLM不可用，改用规则降级 error={}", exc)
            return None
        except Exception as exc:
            logger.exception("LLM行程规划失败，改用规则降级 error={}", exc)
            return None

    @staticmethod
    def _build_prompt(
        request: TripRequest,
        attractions: List[Attraction],
        hotels: List[Hotel],
        weather_info: List[WeatherInfo],
    ) -> str:
        attraction_json = json.dumps([item.model_dump() for item in attractions], ensure_ascii=False)
        hotel_json = json.dumps([item.model_dump() for item in hotels], ensure_ascii=False)
        weather_json = json.dumps([item.model_dump() for item in weather_info], ensure_ascii=False)
        return f"""
你是资深旅行规划师。请基于真实POI、酒店和天气数据，生成结构化 JSON，不要输出 Markdown。

用户需求：
{request.model_dump_json(indent=2)}

可选景点：
{attraction_json}

可选酒店：
{hotel_json}

天气：
{weather_json}

输出必须符合以下字段：
city, start_date, end_date, days, weather_info, overall_suggestions, budget。
days 每项必须包含 date, day_index, description, transportation, accommodation, hotel, attractions, meals。
每天安排 2-3 个景点，尽量使用给定景点和酒店，不要编造坐标。预算需要给出 total_attractions,
total_hotels, total_meals, total_transportation, total。
"""


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def reset_llm() -> None:
    global _llm_service
    _llm_service = None
