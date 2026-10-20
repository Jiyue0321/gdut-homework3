"""读取 .env 中的大模型配置（OpenAI 兼容接口）。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def load_config() -> LLMConfig:
    return LLMConfig(
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
    )
