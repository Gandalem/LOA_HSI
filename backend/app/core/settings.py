from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    lostark_api_key: str = Field(default="", alias="LOSTARK_API_KEY")
    lostark_api_base: str = Field(default="https://developer-lostark.game.onstove.com", alias="LOSTARK_API_BASE")
    data_dir: Path = Field(default=Path("/app/data"), alias="DATA_DIR")
    cache_ttl_seconds: int = Field(default=600, alias="CACHE_TTL_SECONDS")
    default_krw_per_100_gold: float = Field(default=12.0, alias="DEFAULT_KRW_PER_100_GOLD")
    auto_collect_material_prices: bool = Field(default=True, alias="AUTO_COLLECT_MATERIAL_PRICES")
    material_price_ttl_minutes: int = Field(default=360, alias="MATERIAL_PRICE_TTL_MINUTES")
    material_price_refresh_interval_minutes: int = Field(default=360, alias="MATERIAL_PRICE_REFRESH_INTERVAL_MINUTES")
    material_price_startup_force: bool = Field(default=True, alias="MATERIAL_PRICE_STARTUP_FORCE")

    class Config:
        env_file = ".env"
        populate_by_name = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "raw").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "cache").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "parquet").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "db").mkdir(parents=True, exist_ok=True)
    return settings
