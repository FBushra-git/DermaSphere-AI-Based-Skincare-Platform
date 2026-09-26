from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mysql_url: str = "mysql+pymysql://dermasphere:change-me@127.0.0.1:3306/dermasphere?charset=utf8mb4"
    jwt_secret: str = "local-development-secret-change-before-deployment"
    jwt_expire_minutes: int = 60
    frontend_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
