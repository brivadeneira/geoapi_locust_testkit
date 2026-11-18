import json
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from faker import Faker

from config.geo_data_generator_settings import GeoDataGeneratorSettings

logger = logging.getLogger(__name__)


@dataclass
class FakeGeoGenerator:
    """
    Service for generating fake geospatial data, including coordinates and addresses.
    """

    def __init__(
            self,
            seed: int | None = None,
            settings: GeoDataGeneratorSettings | None = None,
            locales: list[str] | None = None,
    ) -> None:
        self.rand_seed = seed
        self.settings = settings or GeoDataGeneratorSettings.default()
        self.locales = locales or self.settings.WORLD_LOCALES_FOR_FACTORY.copy()
        self.chosen_locale = random.choice(self.locales)

        self._init_faker()

        self.land_polygons_from_shapefile: list[Polygon]
        self._load_land_polygons()

        logger.info(
            f"FakeGeoGenerator initialized with settings:\n"
            f"  Seed: {self.rand_seed}\n"
            f"  Locales: {self.locales}\n"
            f"  Chosen Locale: {self.chosen_locale}\n"
            f"  GEO_DATA_GENERATOR_DIR: {self.settings.GEO_DATA_GENERATOR_DIR}\n"
            f"  DATASETS_DIR: {self.settings.DATASETS_DIR}\n"
            f"  LAND_SHAPES_DIR: {self.settings.LAND_SHAPES_DIR}\n"
            f"  DEFAULT_REAL_ADDRESSES_FILE: {self.settings.DEFAULT_REAL_ADDRESSES_FILE}\n"
            f"  LAND_SHAPEFILE: {self.settings.LAND_SHAPEFILE}\n"
            f"  MAX_TRIES_COORDINATES_IN_AREA: {self.settings.MAX_TRIES_COORDINATES_IN_AREA}\n"
        )

    def _init_faker(self) -> None:
        if self.rand_seed:
            Faker.seed(self.rand_seed)
            random.seed(self.rand_seed)

        self.fake = Faker(self.chosen_locale)

    def _load_land_polygons(self) -> None:
        land_path = self.settings.LAND_SHAPEFILE

        if not land_path.exists():
            raise FileNotFoundError(f"Land shapefile not found: {land_path}")

        gdf = gpd.read_file(land_path)
        union = gdf.unary_union
        self.land_polygons_from_shapefile = self._extract_polygons(union)

        if not self.land_polygons_from_shapefile:
            raise RuntimeError(f"No land polygons could be extracted from {land_path}")

    @staticmethod
    def _extract_polygons(given_geometry) -> list[Polygon]:
        """
        Recursively extract all Polygon geometries from a given geometry,
        which can be a Polygon, MultiPolygon, or GeometryCollection.
        """
        match given_geometry:
            case Polygon():
                return [given_geometry]

            case MultiPolygon():
                return list(given_geometry.geoms)

            case _:
                return [
                    geom for geom in getattr(given_geometry, "geoms", [])
                    if isinstance(geom, Polygon)
                ]

    def _validate_coordinates_requirements(
            self, on_land: bool, invalid_value: bool, invalid_type: bool, bbox: Polygon | None
    ) -> None:
        """
        Validate that the combination of coordinates options to be generated is logical
        and does not lead to contradictions.
        """
        if invalid_value and invalid_type:
            raise ValueError("invalid_value and invalid_type cannot be True at the same time")

        if (invalid_value or invalid_type) and (on_land or bbox):
            raise ValueError("invalid_value/invalid_type cannot be combined with on_land or bbox "
                             "(they are mutually exclusive)")

    def _pick_a_random_point_in_a_given_polygon(self, polygon: Polygon) -> Point:
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

    def _normalize_address_str(self, value: str | None) -> str | None:
        """
        Clean an address component string by:
        - converting None to None
        - stripping leading/trailing whitespace
        - replacing line breaks with a single space
        - collapsing multiple spaces into a single space
        - returning None if the resulting string is empty
        """
        if not value:
            return None

        cleaned = str(value).replace("\n", ", ").replace("\r", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def generate_coordinates(
            self,
            *,
            on_land: bool = False,
            invalid_value: bool = False,
            invalid_type: bool = False,
            bbox: Polygon | None = None,
    ) -> dict[str, float | str | bool]:
        """
        Generate a dictionary containing latitude and longitude coordinates.

        Args:
            on_land: Generate coordinates guaranteed to be on land.
            invalid_value: Generate coordinates outside valid geographical ranges.
            invalid_type: Generate coordinates with invalid types.
            bbox: Optional bounding polygon restricting coordinate generation.

        Returns:
            Dictionary containing latitude and longitude, and an OpenStreetMap URL for the generated coordinates.
        """
        self._validate_coordinates_requirements(
            on_land=on_land,
            invalid_value=invalid_value,
            invalid_type=invalid_type,
            bbox=bbox,
        )

        match True:
            case _ if invalid_value:
                latitude = self.fake.random_number(digits=3, fix_len=True) + 90.0
                longitude = self.fake.random_number(digits=3, fix_len=True) + 180.0

            case _ if invalid_type:
                not_float_but_python_native_values = [
                    self.fake.word(),
                    self.fake.boolean(),
                    self.fake.date(),
                    self.fake.time(),
                    self.fake.date_time(),
                ]

                latitude = random.choice(not_float_but_python_native_values)
                longitude = random.choice(not_float_but_python_native_values)

            case _ if bbox and on_land:
                polygons_in_bbox = [
                    poly.intersection(bbox)
                    for poly in self.land_polygons_from_shapefile
                ]

                land_polygons_found_inside_bbox = [
                    poly for poly in polygons_in_bbox if not poly.is_empty
                ]

                if not land_polygons_found_inside_bbox:
                    raise RuntimeError(
                        f"No land found inside given bbox: {bbox.bounds}"
                    )

                point = self._pick_a_random_point_in_a_given_polygon(
                    random.choice(land_polygons_found_inside_bbox)
                )

                latitude, longitude = float(point.y), float(point.x)

            case _ if on_land:
                if not self.land_polygons_from_shapefile:
                    raise RuntimeError(
                        "No land polygons loaded. Check LAND_SHAPEFILE."
                    )

                land_poly = random.choice(self.land_polygons_from_shapefile)
                point = self._pick_a_random_point_in_a_given_polygon(land_poly)

                latitude, longitude = float(point.y), float(point.x)

            case _ if bbox:
                min_lon, min_lat, max_lon, max_lat = bbox.bounds

                latitude = float(random.uniform(a=min_lat, b=max_lat))
                longitude = float(random.uniform(a=min_lon, b=max_lon))

            case _:
                fake_lat, fake_lon = self.fake.latlng()
                latitude, longitude = float(fake_lat), float(fake_lon)

        osm_url = f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}&zoom=5"

        return {
            "latitude": latitude,
            "longitude": longitude,
            "osm_url": osm_url
        }

    def generate_address(
            self, from_real_dataset: bool = True, address_source_file: Path | None = None
    ) -> dict[str, str]:
        """
        Generate a full address string based on the specified options.

        Returns (dict):
        A dictionary containing a full address string composed of available components,
        cleaned and formatted appropriately. And a
        """

        address_source_file_path = address_source_file or self.settings.DEFAULT_REAL_ADDRESSES_FILE

        match True:
            case _ if not from_real_dataset:
                address = self._normalize_address_str(self.fake.address())
                tail_component = address.split(', ')[-1]
                osm_url = f"https://www.openstreetmap.org/search?query={quote(tail_component)}"

                return {
                    "full_address": address,
                    "osm_url": osm_url
                }

            case _ if not address_source_file_path.exists():
                raise FileNotFoundError(
                    f"Addresses dataset not found: {address_source_file_path}"
                )

            case _:
                with open(address_source_file_path, "r", encoding="utf-8") as f:
                    address_source = json.load(f)

                if not isinstance(address_source, dict) or not address_source:
                    raise ValueError(
                        f"Invalid or empty addresses dataset: {address_source_file_path}"
                    )

                for _ in range(self.settings.MAX_TRIES_ADDRESS_GENERATION):
                    rand_country_from_source = random.choice(
                        list(address_source.keys())
                    )

                    address = random.choice(address_source[rand_country_from_source])

                    if not isinstance(address, dict):
                        continue

                    street = self._normalize_address_str(address.get("street"))
                    number = self._normalize_address_str(address.get("address_number"))

                    street_full = f"{street} {number}".strip() if street or number else ""

                    components = [
                        street_full,
                        self._normalize_address_str(address.get("neighborhood")),
                        self._normalize_address_str(address.get("place")),
                        self._normalize_address_str(address.get("locality")),
                        self._normalize_address_str(address.get("region")),
                        self._normalize_address_str(address.get("postcode")),
                        (
                            self._normalize_address_str(address.get("country")).upper()
                            if address.get("country")
                            else None
                        ),
                    ]

                    address = ", ".join(filter(None, components)).replace("'", "’").replace("\n", " ").strip()

                    if not address:
                        continue

                    osm_url = f"https://www.openstreetmap.org/search?query={quote(address)}"

                    return {
                        "full_address": address,
                        "osm_url": osm_url
                    }

                raise ValueError(
                    f"Could not find a valid address after {self.settings.MAX_TRIES_ADDRESS_GENERATION} attempts "
                    f"for country: {rand_country_from_source}"
                )
