from pydantic_settings import BaseSettings
from pathlib import Path


class GeoDataGeneratorSettings(BaseSettings):
    """
    Settings for the GeoDataGenerator service.
    """
    GEO_DATA_GENERATOR_DIR: Path
    DATASETS_DIR: Path
    LAND_SHAPES_DIR: Path

    DEFAULT_REAL_ADDRESSES_FILE: Path
    LAND_SHAPEFILE: Path

    MAX_TRIES_COORDINATES_IN_AREA: int = 10
    MAX_TRIES_ADDRESS_GENERATION: int = 5
    WORLD_LOCALES_FOR_FACTORY: list[str] = [
        "es_ES", "it_IT",
        "pt_BR", "es_AR",
        "pt_PT"
    ]

    @classmethod
    def default(cls) -> "GeoDataGeneratorSettings":
        """
        Create a default instance of GeoDataGeneratorSettings with paths relative to the project root.
        """
        project_root = Path(__file__).resolve().parent.parent

        base_dir = project_root / "services" / "geo_data_generator"
        datasets_dir = project_root / "services" / "datasets"
        land_shapes_dir = project_root / "services" / "datasets" / "on_land_shapes_data"

        return cls(
            GEO_DATA_GENERATOR_DIR=base_dir.resolve(),
            DATASETS_DIR=datasets_dir.resolve(),
            LAND_SHAPES_DIR=land_shapes_dir.resolve(),
            DEFAULT_REAL_ADDRESSES_FILE=(datasets_dir / "curated_addresses.json").resolve(),
            LAND_SHAPEFILE=(land_shapes_dir / "ne_110m_admin_0_countries.shp").resolve(),
        )
