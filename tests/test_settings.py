import pytest


class TestGeoSettings:
    @pytest.fixture(autouse=True)
    def _setup(self, fake_geo_settings):
        self.settings = fake_geo_settings

    @pytest.mark.parametrize(
        "mandatory_attribute",
        [
            "GEO_DATA_GENERATOR_DIR",
            "DATASETS_DIR",
            "LAND_SHAPES_DIR",
            "DEFAULT_REAL_ADDRESSES_FILE",
            "LAND_SHAPEFILE",
        ],
    )
    def test_required_attributes_present(self, mandatory_attribute):
        value = getattr(self.settings, mandatory_attribute, None)
        assert value is not None, f"{mandatory_attribute} is missing in GeoSettings"
