"""应用配置管理。"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
LOG_DIR = PROJECT_DIR / "logs"

# 按就近优先级加载环境变量，避免把密钥写进代码。
load_dotenv(PROJECT_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)
load_dotenv(Path.cwd() / ".env", override=False)


class Settings(BaseSettings):
    """统一的运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "LangGraph智能旅行助手"
    app_version: str = "2.0.0"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    port: int = Field(default=8000, validation_alias="APP_PORT")
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    amap_api_key: str = Field(default="", validation_alias="AMAP_API_KEY")
    amap_web_js_key: str = Field(default="", validation_alias="AMAP_WEB_JS_KEY")

    unsplash_access_key: str = Field(default="", validation_alias="UNSPLASH_ACCESS_KEY")
    unsplash_secret_key: str = Field(default="", validation_alias="UNSPLASH_SECRET_KEY")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", validation_alias="LLM_BASE_URL")
    llm_model_id: str = Field(default="", validation_alias="LLM_MODEL_ID")

    log_level: str = "INFO"
    log_rotation: str = "10 MB"
    log_retention: str = "14 days"

    amap_timeout_seconds: float = 10.0
    image_timeout_seconds: float = 8.0
    llm_timeout_seconds: float = 45.0

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str:
        return self.llm_base_url or self.openai_base_url

    @property
    def effective_llm_model(self) -> str:
        return self.llm_model_id or self.openai_model

    def get_cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def safe_summary(self) -> dict:
        """只返回安全配置摘要，避免日志泄露密钥。"""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "amap_api_key": "已配置" if self.amap_api_key else "未配置",
            "amap_web_js_key": "已配置" if self.amap_web_js_key else "未配置",
            "unsplash_access_key": "已配置" if self.unsplash_access_key else "未配置",
            "llm_api_key": "已配置" if self.effective_llm_api_key else "未配置",
            "llm_base_url": self.effective_llm_base_url,
            "llm_model": self.effective_llm_model,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_config() -> List[str]:
    """返回非阻塞配置警告，外部服务缺 key 时系统走降级逻辑。"""
    settings = get_settings()
    warnings: List[str] = []

    if not settings.amap_api_key:
        warnings.append("AMAP_API_KEY未配置，POI、天气和地理编码将使用降级数据。")
    if not settings.effective_llm_api_key:
        warnings.append("LLM_API_KEY/OPENAI_API_KEY未配置，行程规划将使用规则引擎降级。")
    if not settings.unsplash_access_key:
        warnings.append("UNSPLASH_ACCESS_KEY未配置，图片将优先使用高德POI图片或占位图。")

    return warnings
