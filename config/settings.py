
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


AVAILABLE_LOCUST_TAGS = [
    "coordinates",
    "coordinates_on_land",
    "coordinates_inside_bbox",
    "coordinates_inside_bbox_on_land",
    "address",
    "address_real",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEOAPI_",
        env_file=".env",
        extra="ignore",
    )

    project_name: str = "geoapi_locust_testkit"
    debug: bool = False

    locust_file_path: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parent.parent
            / "services"
            / "locustfile.py"
        )
    )

    apis_config_dir: Path = Field(
        default_factory=lambda: (
            Path(__file__).resolve().parent / "apis"
        )
    )

    def model_post_init(self, context) -> None:
        """Validate project paths after settings initialization."""

        if not self.locust_file_path.is_file():
            raise FileNotFoundError(
                f"Locust file not found: {self.locust_file_path}"
            )

        if not self.apis_config_dir.is_dir():
            raise NotADirectoryError(
                f"API configuration directory not found: "
                f"{self.apis_config_dir}"
            )

        config_files = [
            *self.apis_config_dir.glob("*.yaml"),
        ]

        if not config_files:
            raise FileNotFoundError(
                f"No API YAML configurations found in: "
                f"{self.apis_config_dir}"
            )


settings = Settings()
