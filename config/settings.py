from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class StoreConfig:
    code: str
    city: str
    url: str


@dataclass(frozen=True)
class Settings:
    brand_code: str
    brand_name: str
    base_url: str
    sitemap_url: str
    stores: tuple[StoreConfig, ...]
    timeout_seconds: int
    retries: int
    workers: int
    delay_seconds: float
    incremental: bool
    full_refresh_days: int
    user_agent: str
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    knowledge_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "knowledge")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or Path(os.getenv("CATALOG_CONFIG", PROJECT_ROOT / "config" / "brands" / "friovesa.yaml"))
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    brand = data["brand"]
    runtime = data.get("runtime", {})
    stores = tuple(StoreConfig(str(item["code"]), str(item["city"]), str(item["url"])) for item in data["stores"])
    return Settings(
        brand_code=str(brand["code"]), brand_name=str(brand["name"]), base_url=str(brand["base_url"]),
        sitemap_url=str(brand.get("sitemap_url", "")), stores=stores,
        timeout_seconds=int(os.getenv("CATALOG_TIMEOUT", runtime.get("timeout_seconds", 35))),
        retries=int(os.getenv("CATALOG_RETRIES", runtime.get("retries", 3))),
        workers=int(os.getenv("CATALOG_WORKERS", runtime.get("workers", 8))),
        delay_seconds=float(os.getenv("CATALOG_DELAY", runtime.get("delay_seconds", 0.15))),
        incremental=str(os.getenv("CATALOG_INCREMENTAL", runtime.get("incremental", True))).casefold() in {"1", "true", "yes", "si", "sí"},
        full_refresh_days=int(os.getenv("CATALOG_FULL_REFRESH_DAYS", runtime.get("full_refresh_days", 14))),
        user_agent=str(os.getenv("CATALOG_USER_AGENT", runtime.get("user_agent", "CatalogKnowledgeCrawler/1.0"))),
    )


SETTINGS = load_settings()
