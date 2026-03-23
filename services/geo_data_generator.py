import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from faker import Faker

from conf.geo_data_generator_settings import GeoDataGeneratorSettings

logger = logging.getLogger(__name__)


@dataclass
class FakeGeoGenerator:
    """
    Service for generating fake geospatial data, including coordinates and addresses.
    """

    def __init__(
        self,
        seed: int = 32,
        settings: GeoDataGeneratorSettings | None = None,
        locales: list[str] | None = None,
    ) -> None:
        self.seed = seed
        self.settings = settings or GeoDataGeneratorSettings.default()
        self.locales = locales or self.settings.WORLD_LOCALES_FOR_FACTORY.copy()

        if self.seed:
            Faker.seed(self.seed)
            random.seed(self.seed)

        chosen_locale = random.choice(self.locales)
        self.fake = Faker(chosen_locale)

        self.land_polygons: list[Polygon] = []
        self._load_land_polygons()

        logger.info(
            f"FakeGeoGenerator initialized with settings:\n"
            f"  Seed: {self.seed}\n"
            f"  Locales: {self.locales}\n"
            f"  Chosen Locale: {chosen_locale}\n"
            f"  GEO_DATA_GENERATOR_DIR: {self.settings.GEO_DATA_GENERATOR_DIR}\n"
            f"  DATASETS_DIR: {self.settings.DATASETS_DIR}\n"
            f"  LAND_SHAPES_DIR: {self.settings.LAND_SHAPES_DIR}\n"
            f"  DEFAULT_REAL_ADDRESSES_FILE: {self.settings.DEFAULT_REAL_ADDRESSES_FILE}\n"
            f"  LAND_SHAPEFILE: {self.settings.LAND_SHAPEFILE}\n"
            f"  MAX_TRIES_COORDINATES_IN_AREA: {self.settings.MAX_TRIES_COORDINATES_IN_AREA}\n"
        )

    def _init_locales(self) -> None:
        if not self.locales:
            self.locales = self.settings.WORLD_LOCALES_FOR_FACTORY

    def _init_faker(self) -> None:
        if self.seed:
            Faker.seed(self.seed)
            random.seed(self.seed)
        locale = random.choice(self.locales)
        self.fake = Faker(locale)

    def _load_land_polygons(self) -> None:
        land_path = self.settings.LAND_SHAPEFILE

        if not land_path.exists():
            raise FileNotFoundError(f"Land shapefile not found: {land_path}")

        gdf = gpd.read_file(land_path)
        union = gdf.unary_union
        self.land_polygons = self._extract_polygons(union)

    @staticmethod
    def _extract_polygons(given_geometry) -> list[Polygon]:
        """
        Recursively extract all Polygon geometries from a given geometry,
        which can be a Polygon, MultiPolygon, or GeometryCollection.
        """
        if isinstance(given_geometry, Polygon):
            return [given_geometry]
        if isinstance(given_geometry, MultiPolygon):
            return list(given_geometry.geoms)
        return [g for g in getattr(given_geometry, "geoms", []) if isinstance(g, Polygon)]

    def _validate_options(
            self, on_land: bool, invalid_value: bool, invalid_type: bool, bbox: Polygon | None
    ) -> None:
        """
        Validate that the combination of options is logical and does not lead to contradictions.
        """
        if (invalid_value or invalid_type) and (on_land or bbox):
            raise ValueError("invalid_value/invalid_type cannot be combined with on_land or bbox")

    def _random_point_in_polygon(self, polygon: Polygon) -> Point:
        """
        Generate a random point within the given polygon using rejection sampling.
        """
        min_lon, min_lat, max_lon, max_lat = polygon.bounds

        for _ in range(self.settings.MAX_TRIES_COORDINATES_IN_AREA):
            lat = random.uniform(a=min_lat, b=max_lat)
            lon = random.uniform(a=min_lon, b=max_lon)
            point = Point(lon, lat)

            if polygon.contains(point):
                return point

        raise RuntimeError(
            f"Failed to generate point inside polygon after "
            f"{self.settings.MAX_TRIES_COORDINATES_IN_AREA} attempts"
        )

    def _clean_address_str(self, value: str | None) -> str | None:
        """
        Clean an address component string by stripping whitespace and returning None if it's empty.
        """
        if value is None:
            return None

        value = str(value).strip()

        return value if value else None

    def gen_coordinates(
        self,
        *,
        on_land: bool = False,
        invalid_value: bool = False,
        invalid_type: bool = False,
        bbox: Polygon | None = None,
    ) -> tuple[float | str | bool, float | str | bool]:
        """
        Generate a pair of latitude and longitude coordinates based on the specified options.

        Returns:
        A tuple of (latitude, longitude) where each can be a float, string, or boolean depending on the options.
        """
        self._validate_options(
            on_land=on_land,
            invalid_value=invalid_value,
            invalid_type=invalid_type,
            bbox=bbox,
        )

        if invalid_value:
            latitude_out_of_range = self.fake.random_number(digits=3, fix_len=True) + 90.0
            longitude_out_of_range = self.fake.random_number(digits=3, fix_len=True) + 180.0

            return latitude_out_of_range, longitude_out_of_range

        if invalid_type:
            not_float_values = [
                self.fake.word(),
                self.fake.boolean(),
                self.fake.date(),
                self.fake.time(),
                self.fake.datetime(),
            ]

            random_not_float_for_latitude = random.choice(not_float_values)
            random_not_float_for_longitude = random.choice(not_float_values)

            return random_not_float_for_latitude, random_not_float_for_longitude

        if bbox and on_land:
            polygons_in_bbox = [poly.intersection(bbox) for poly in self.land_polygons]
            not_empty_polygons_in_bbox = [p for p in polygons_in_bbox if not p.is_empty]

            if not not_empty_polygons_in_bbox:
                raise RuntimeError(f"No land found inside given bbox: {bbox.bounds}")

            rand_point_inside_bbox = self._random_point_in_polygon(
                random.choice(not_empty_polygons_in_bbox)
            )

            return float(rand_point_inside_bbox.y), float(rand_point_inside_bbox.x)

        if on_land:
            if not self.land_polygons:
                raise RuntimeError("No land polygons loaded. Check LAND_SHAPEFILE.")

            land_poly = random.choice(self.land_polygons)
            point = self._random_point_in_polygon(land_poly)
            return float(point.y), float(point.x)

        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox.bounds

            return float(
                random.uniform(a=min_lat, b=max_lat)
            ), float(
                random.uniform(a=min_lon, b=max_lon)
            )

        fake_lat, fake_lon = self.fake.latlng()
        return float(fake_lat), float(fake_lon)

    def gen_address(
            self, real: bool = True, address_source_file: Path | None = None
    ) -> str:
        """
        Generate a full address string based on the specified options.

        Returns (str):
            A full address string composed of available components, cleaned and formatted appropriately.
        """
        address_source_file_path = address_source_file or self.settings.DEFAULT_REAL_ADDRESSES_FILE

        if not real:
            fake_address = self._clean_address_str(self.fake.address())
            return fake_address

        if not address_source_file_path.exists():
            raise FileNotFoundError(
                f"Addresses dataset not found: {address_source_file_path}"
            )

        with open(address_source_file_path, "r") as f:
            address_source = json.load(f)

        if not isinstance(address_source, dict) or not address_source:
            raise ValueError(
                f"Invalid or empty addresses dataset: {address_source_file_path}"
            )

        rand_country_from_source = random.choice(
            list(address_source.keys())
        )
        address = random.choice(
            address_source[rand_country_from_source]
        )

        street = self._clean_address_str(address.get("street"))
        number = self._clean_address_str(address.get("address_number"))
        street_full = f"{street} {number}".strip() if street or number else ""

        components = [
            street_full,
            self._clean_address_str(address.get("neighborhood")),
            self._clean_address_str(address.get("place")),
            self._clean_address_str(address.get("locality")),
            self._clean_address_str(address.get("region")),
            self._clean_address_str(address.get("postcode")),
            self._clean_address_str(address.get("country")).upper() if address.get("country") else None,
        ]
        return ", ".join(filter(None, components)).replace("'", "’").replace("\n", " ")

    def gen_geo_context(
        self,
        *,
        on_land: bool = True,
        invalid_value: bool = False,
        invalid_type: bool = False,
        bbox: Polygon | None = None,
        real_address: bool = True,
        addresses_file: Path | None = None,
    ) -> dict[str, float | str | bool]:
        """
        Generate a geospatial context dictionary containing latitude, longitude, and a full address.
        Arguments:
            - on_land (bool): If True, generate coordinates that are guaranteed to be on land.
            - invalid_value (bool): If True, generate coordinates with values that are outside valid ranges.
            - invalid_type (bool): If True, generate coordinates with invalid types (e.g., strings or booleans).
            - bbox (Polygon): If provided, generate coordinates within the specified bounding box.
            - real_address (bool): If True, generate an address from a real dataset;
            if False, generate a fake address using Faker.
            - addresses_file (Path): Optional path to a JSON file containing real addresses.
            If not provided, the default dataset will be used.

        Returns:
            A dictionary with keys "latitude", "longitude", and "full_address",
            where the values are generated based on the specified options.

        Note: latitude, longitude and full_address generation are independent,
        so the generated address may not correspond to the generated coordinates.

        Usage example:

        generator = FakeGeoGenerator(seed=42)
        geo_context = generator.gen_geo_context(
            on_land=True,
            invalid_value=False,
            invalid_type=False,
            bbox=None,
            real_address=True,
            addresses_file=None
        )

        """
        lat, lon = self.gen_coordinates(
            on_land=on_land,
            invalid_value=invalid_value,
            invalid_type=invalid_type,
            bbox=bbox,
        )
        return {
            "latitude": lat,
            "longitude": lon,
            "full_address": self.gen_address(real=real_address, address_source_file=addresses_file),
        }
