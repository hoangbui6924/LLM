"""Nạp cấu hình từ YAML + .env. Một nguồn sự thật duy nhất cho toàn dự án."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"

load_dotenv(ROOT / ".env")


def _read_yaml(p: Path) -> dict[str, Any]:
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings:
    def __init__(self) -> None:
        self.root = ROOT
        self.models = _read_yaml(CONFIGS / "models.yaml")
        self.app = _read_yaml(CONFIGS / "app.yaml")

        self.profile = os.getenv("VMA_PROFILE", "cloud_default")
        self.strategy = os.getenv("VMA_STRATEGY", "balanced")

        self.cache_enabled = os.getenv("VMA_LLM_CACHE", "true").lower() == "true"
        self.cache_dir = ROOT / os.getenv("VMA_LLM_CACHE_DIR", ".cache/llm")
        self.budget_usd = float(os.getenv("VMA_BUDGET_USD_PER_RUN", "5.0"))
        self.max_concurrency = int(os.getenv("VMA_MAX_CONCURRENCY", "4"))

        self.trace_dir = ROOT / "traces"

    # ---- model registry -------------------------------------------------

    def agent_model(self, agent: str, profile: str | None = None) -> dict[str, Any]:
        """Trả cấu hình model cho một tác tử trong một profile."""
        prof = profile or self.profile
        profiles = self.models.get("profiles", {})
        if prof not in profiles:
            raise KeyError(
                f"Không có profile '{prof}' trong configs/models.yaml. "
                f"Có: {list(profiles)}"
            )
        block = profiles[prof]
        if agent not in block:
            raise KeyError(f"Profile '{prof}' thiếu tác tử '{agent}'. Có: {list(block)}")
        return dict(block[agent])

    def provider(self, name: str) -> dict[str, Any]:
        providers = self.models.get("providers", {})
        if name not in providers:
            raise KeyError(f"Không có provider '{name}'. Có: {list(providers)}")
        return dict(providers[name])

    def price(self, model: str) -> dict[str, float]:
        pricing = self.models.get("pricing", {})
        return pricing.get(model, pricing.get("_default", {"in": 0.0, "out": 0.0}))

    # ---- app config -----------------------------------------------------

    def strategy_cfg(self, name: str | None = None) -> dict[str, Any]:
        s = name or self.strategy
        strategies = self.app.get("strategies", {})
        if s not in strategies:
            raise KeyError(f"Không có strategy '{s}'. Có: {list(strategies)}")
        return dict(strategies[s])

    @property
    def retrieval(self) -> dict[str, Any]:
        return self.app.get("retrieval", {})

    @property
    def prm(self) -> dict[str, Any]:
        return self.app.get("prm", {})

    @property
    def router(self) -> dict[str, Any]:
        return self.app.get("router", {})

    @property
    def limits(self) -> dict[str, Any]:
        return self.app.get("limits", {})

    @property
    def semantic_cache(self) -> dict[str, Any]:
        return self.app.get("semantic_cache", {})

    # ---- chẩn đoán ------------------------------------------------------

    def available_providers(self) -> dict[str, bool]:
        """Provider nào thực sự dùng được ngay bây giờ. Gọi lúc khởi động để
        báo lỗi sớm thay vì chết giữa lúc demo."""
        out: dict[str, bool] = {}
        for name, cfg in self.models.get("providers", {}).items():
            env = cfg.get("api_key_env")
            out[name] = True if env is None else bool(os.getenv(env))
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
