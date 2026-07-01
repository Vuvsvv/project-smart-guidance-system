from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_driver: str = Field(default="ODBC Driver 17 for SQL Server", alias="DB_DRIVER")
    db_server: str = Field(default="medichain-server.database.windows.net", alias="DB_SERVER")
    db_name: str = Field(default="MediChainDB", alias="DB_NAME")
    db_user: str = Field(default="medichain_admin", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")

    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    llm_model: str = Field(default="gemini-2.5-flash", alias="LLM_MODEL")
    ai_timeout_seconds: float = Field(default=8.0, alias="AI_TIMEOUT_SECONDS")
    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    deploy_mode: str = Field(default="local", alias="DEPLOY_MODE")
    disable_local_embedding: bool = Field(default=False, alias="DISABLE_LOCAL_EMBEDDING")

    # 語音 gateway 設定
    voice_enabled: bool = Field(default=False, alias="VOICE_ENABLED")
    voice_gateway_url: str = Field(default="http://localhost:8000", alias="VOICE_GATEWAY_URL")
    voice_gateway_key: str = Field(default="sk-secret-key-here", alias="VOICE_GATEWAY_KEY")
    voice_gateway_is_ngrok: bool = Field(default=False, alias="VOICE_GATEWAY_IS_NGROK")
    voice_default_lang: str = Field(default="taiwanese", alias="VOICE_DEFAULT_LANG")
    voice_timeout: float = Field(default=60.0, alias="VOICE_TIMEOUT")

def get_settings():
    return Settings()
