from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    auth_mode: str = "local"
    app_secret: str
    database_url: str
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "foundry"
    s3_restore_map_file: str | None = None
    temporal_address: str = "localhost:7233"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    dev_password: str
    local_rate_micro_usd: int = 1000
    webhook_local_hosts: str = "localhost,127.0.0.1,webhook-receiver"
    local_webhook_url: str = "http://localhost:9100/events"
    max_upload_bytes: int = 20 * 1024 * 1024
    local_model_manifest: str = ".local/models/manifest.json"
    blender_executable: str = "/usr/bin/blender"
    blender_version: str = "4.3.2"
    provider_http_allowlist: str = ""
    allow_external_provider_calls: bool = False

    @property
    def origins(self) -> list[str]:
        return self.allowed_origins.split(",")


@lru_cache
def settings() -> Settings:
    config = Settings()
    if config.app_env != "local" or config.auth_mode != "local":
        raise RuntimeError(
            "This milestone supports local development only. Production authentication is blocked."
        )
    if len(config.app_secret) < 32 or config.app_secret == "generated-by-bootstrap":
        raise RuntimeError("Run make bootstrap to generate local secrets.")
    return config
