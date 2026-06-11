from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    MCP_API_KEY: str

    MCP_TRANSPORT: str = "http"

    HOST: str = "0.0.0.0"

    PORT: int = 8080

    # Oracle settings
    DEBUG: bool = False

    ORACLE_ENABLED: bool = True

    DB_CONNECTION_STRING: str | None = None

    COMMENT_DB_CONNECTION_STRING: str | None = None

    QUERY_LIMIT_SIZE: int = 50

    TABLE_WHITE_LIST: str | None = None

    COLUMN_WHITE_LIST: str | None = None

    ORACLE_POOL_SIZE: int = 5

    ORACLE_MAX_OVERFLOW: int = 10

    ORACLE_POOL_RECYCLE: int = 3600

    ORACLE_QUERY_TIMEOUT_MS: int = 30000

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
