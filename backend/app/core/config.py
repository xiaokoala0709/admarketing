import os


class Settings:
    app_name = "adamarketing backend"
    api_prefix = "/api"
    default_anthropic_base_url = "https://api.anthropic.com"

    @property
    def frontend_origin(self) -> str:
        return os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def anthropic_api_key(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "").strip()

    @property
    def anthropic_base_url(self) -> str:
        return os.getenv(
            "ANTHROPIC_BASE_URL",
            self.default_anthropic_base_url,
        ).strip() or self.default_anthropic_base_url

    @property
    def anthropic_model(self) -> str:
        return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7").strip() or "claude-opus-4-7"

    @property
    def image_provider(self) -> str:
        return os.getenv("IMAGE_PROVIDER", "").strip().lower()

    @property
    def image_api_key(self) -> str:
        return os.getenv("IMAGE_API_KEY", "").strip()

    @property
    def openai_image_model(self) -> str:
        return os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip() or "gpt-image-1"

    @property
    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_image_api_key(self) -> bool:
        return bool(self.image_api_key)

    @property
    def tophub_access_key(self) -> str:
        return os.getenv("TOPHUB_ACCESS_KEY", "").strip()

    @property
    def has_tophub_key(self) -> bool:
        return bool(self.tophub_access_key)

    @property
    def newsnow_base_url(self) -> str:
        # 自建 newsnow (github.com/ourongxing/newsnow) 实例的地址，没有官方免费
        # 公共站可用，必须自己部署后把域名填进这个环境变量，不填就跳过这个数据源。
        return os.getenv("NEWSNOW_BASE_URL", "").strip().rstrip("/")

    @property
    def has_newsnow_base_url(self) -> bool:
        return bool(self.newsnow_base_url)


settings = Settings()

