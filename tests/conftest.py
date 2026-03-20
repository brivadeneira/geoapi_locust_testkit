import pytest
from conf.geo_data_generator_settings import GeoDataGeneratorSettings


@pytest.fixture(scope="session")
def test_geo_settings() -> GeoDataGeneratorSettings:
    """
    Fixture to provide GeoSettings for tests.
    """
    return GeoDataGeneratorSettings.default()
