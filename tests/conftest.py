import random
import pytest
from faker import Faker
from shapely.geometry import box

from config.geo_data_generator_settings import GeoDataGeneratorSettings
from services.geo_data_generator import FakeGeoGenerator


@pytest.fixture(scope="session")
def fake_geo_settings() -> GeoDataGeneratorSettings:
    return GeoDataGeneratorSettings.default()


@pytest.fixture(scope="session")
def fake_geo_generator(fake_geo_settings: GeoDataGeneratorSettings) -> FakeGeoGenerator:
    return FakeGeoGenerator(seed=42, settings=fake_geo_settings)


@pytest.fixture(scope="session")
def fake_bbox():
    fake = Faker()
    south_lat, west_lon = map(float, fake.latlng())
    north_lat, east_lon = map(float, fake.latlng())

    min_lat, max_lat = sorted([south_lat, north_lat])
    min_lon, max_lon = sorted([west_lon, east_lon])

    return box(minx=min_lon, miny=min_lat, maxx=max_lon, maxy=max_lat)


@pytest.fixture(scope="session")
def fake_bbox_on_land(fake_geo_generator):
    point_on_land = random.choice(fake_geo_generator.land_polygons_from_shapefile).centroid
    buffer_in_degrees = 1.0
    return box(
        minx=point_on_land.x - buffer_in_degrees,
        miny=point_on_land.y - buffer_in_degrees,
        maxx=point_on_land.x + buffer_in_degrees,
        maxy=point_on_land.y + buffer_in_degrees,
    )
