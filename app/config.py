from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Career Copilot"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    portfolio_content_path: str = (
        "D:/Escritorio/MyPage/manuelma4.github.io/assets/js/content.js"
    )
    miktex_bin: str = (
        "C:/Users/Usuario/AppData/Local/Programs/MiKTeX/miktex/bin/x64"
    )
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'career_copilot.db').as_posix()}"
    generated_dir: Path = PROJECT_ROOT / "data" / "generated"
    profile_seed_path: Path = PROJECT_ROOT / "app" / "data" / "profile_seed.json"
    writing_examples_path: Path = PROJECT_ROOT / "app" / "data" / "writing_examples.json"


settings = Settings()
