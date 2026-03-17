from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    local_model_url: str = "http://localhost:11434"
    database_url: str = "sqlite+aiosqlite:///agents_team.db"
    host: str = "0.0.0.0"
    port: int = 9000
    log_level: str = "info"
    max_tool_iterations: int = 10
    max_dependency_result_length: int = 4000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
