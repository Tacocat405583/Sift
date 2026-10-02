from datetime import date, timedelta
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://sift:sift@localhost:5433/sift"

    # Corpus window. 1 month for the MVP; set HARVEST_MONTHS=3 for the full v1 corpus.
    harvest_months: int = 1
    categories: frozenset[str] = frozenset({"cs.AI", "cs.LG", "cs.CL", "cs.MA", "cs.IR"})
    data_dir: Path = ROOT / "data" / "cs"

    # Ranking / graph
    result_limit: int = 125
    neighbors_k: int = 20

    semantic_scholar_api_key: str | None = None

    @property
    def harvest_from(self) -> date:
        return date.today() - timedelta(days=30 * self.harvest_months)


settings = Settings()
