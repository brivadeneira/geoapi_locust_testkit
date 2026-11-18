import re

import pytest
from shapely.geometry import box, Point


@pytest.mark.usefixtures("fake_geo_generator")
class TestFakeGeoGenerator:
    def test_init_fake_geo_generator(self, fake_geo_generator):
        assert fake_geo_generator
        assert fake_geo_generator.rand_seed is not None
        assert fake_geo_generator.settings is not None
        assert fake_geo_generator.land_polygons_from_shapefile

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"on_land": True},
            {"bbox": "fake_bbox"},
            {"on_land": True, "bbox": "fake_bbox_on_land"},
        ],
        ids=[
            "default",
            "on_land",
            "bbox",
            "on_land_and_bbox",
        ],
    )
    def test_gen_coordinates_valid(self, request, fake_geo_generator, kwargs):
        if isinstance(kwargs.get("bbox"), str):
            kwargs["bbox"] = request.getfixturevalue(kwargs["bbox"])

        generated_address = fake_geo_generator.generate_coordinates(**kwargs)
        lat, lon = generated_address.get("latitude"), generated_address.get("longitude")

        assert lat is not None
        assert lon is not None
        assert isinstance(lat, float)
        assert isinstance(lon, float)

        assert (-90 <= lat <= 90)
        assert (-180 <= lon <= 180)

        point = Point(lon, lat)

        if kwargs.get("on_land"):
            assert any(poly.contains(point) for poly in fake_geo_generator.land_polygons_from_shapefile)

        if kwargs.get("bbox"):
            bbox = kwargs["bbox"]
            assert bbox.contains(point)

    def test_gen_coordinates_invalid_values(self, fake_geo_generator):
        generated_address = fake_geo_generator.generate_coordinates(invalid_value=True)
        lat, lon = generated_address.get("latitude"), generated_address.get("longitude")

        assert lat is not None
        assert lon is not None

        assert not (-90 <= lat <= 90) or not (-180 <= lon <= 180)

    def test_gen_coordinates_invalid_type(self, fake_geo_generator):
        generated_address = fake_geo_generator.generate_coordinates(invalid_type=True)
        lat, lon = generated_address.get("latitude"), generated_address.get("longitude")

        assert lat is not None
        assert lon is not None

        assert not isinstance(lat, float) or not isinstance(lon, float)

    def test_gen_coordinates_on_land_bbox_no_land(self, fake_geo_generator):
        ocean_bbox = box(
            minx=-160.0,
            miny=-60.0,
            maxx=-150.0,
            maxy=-50.0
        )

        with pytest.raises(RuntimeError, match=r"No land found inside given bbox"):
            fake_geo_generator.generate_coordinates(on_land=True, bbox=ocean_bbox)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"invalid_value": True, "invalid_type": True},
            {"invalid_value": True, "on_land": True},
            {"invalid_value": True, "bbox": "fake_bbox"},
            {"invalid_type": True, "on_land": True},
            {"invalid_type": True, "bbox": "fake_bbox"},
        ],
        ids=[
            "invalid_value_and_invalid_type",
            "invalid_value_and_on_land",
            "invalid_value_and_bbox",
            "invalid_type_and_on_land",
            "invalid_type_and_bbox",
        ],
    )
    def test_gen_coordinates_invalid_options(self, request, fake_geo_generator, kwargs):
        if isinstance(kwargs.get("bbox"), str):
            kwargs["bbox"] = request.getfixturevalue(kwargs["bbox"])

        with pytest.raises(ValueError):
            fake_geo_generator.generate_coordinates(**kwargs)

    def test_gen_address(self, fake_geo_generator):
        generated_address = fake_geo_generator.generate_address()
        address = generated_address.get("full_address")
        assert address
        assert isinstance(address, str)

        assert re.search(r"\d+", address), f"Address missing a number: {address}"

        components = [part.strip() for part in address.split(",") if part.strip()]
        assert len(components) >= 2, f"Address has less than 2 components: {components}"
