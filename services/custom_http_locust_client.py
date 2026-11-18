import logging

from functools import lru_cache

from itertools import cycle
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

from locust import HttpUser, events
from shapely import box
from config.settings import settings
from services.geo_data_generator import FakeGeoGenerator, init_fake_geo_generator


@events.init_command_line_parser.add_listener
def add_arguments(parser):
    """Register additional command-line arguments for the Locust client.

    Args:
        parser: Locust argument parser used to configure the load test.
    """

    parser.add_argument(
        "--api-name",
        required=True,
        help="API configuration name."
    )

    parser.add_argument(
        "--endpoint-paths",
        nargs="+",
        default=["all"],
        help="Endpoint names or paths."
    )

    parser.add_argument(
        "--on-land",
        action="store_true",
        help="Generate coordinates on land.",
    )

    parser.add_argument(
        "--real-address",
        action="store_true",
        help="Generate addresses from the real address dataset.",
    )

    parser.add_argument(
        "--wait-time",
        type=float,
        default=1,
        help="Wait between tasks in seconds."
    )


class CustomLocustClient(HttpUser):
    """
    Generic Locust HTTP client driven by YAML API configurations.

    The client:
     - discovers the requested API configuration,
    - selects its endpoints,
    - generates geographic test data when required,
    - and renders endpoint parameters using Jinja templates.

    Geographic parameters are generated through :class:`FakeGeoGenerator`.
    Supported generated values include fake addresses and geographic
    coordinates, optionally constrained to a configured bounding box.

    Attributes:
        host: Default HTTP host used by Locust.
        config_dir_with_api_schemas_path: Directory containing API YAML
            configuration files.
        geo_fake_generator: Generator responsible for producing geographic
            test data.
        host: Base URL resolved from the selected API configuration.
        api_name: Name of the selected API.
        list_of_endpoints_to_hit: Endpoints selected for the current test.
        api_config_from_yaml: Loaded API configuration.
        endpoint_cycle: Infinite iterator cycling through selected endpoints.
        wait_time_in_min: Minimum waiting time between consecutive tasks.
    """

    abstract = True
    host = "http://localhost"

    def wait_time(self) -> float:
        return self.wait_time_in_min

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_dir_with_api_schemas_path: Path = Path(settings.apis_config_dir)
        self.geo_fake_generator: FakeGeoGenerator = init_fake_geo_generator()

        self.api_name: str | None = None

        self.on_land: bool = False
        self.real_address: bool = False

        self.list_of_endpoints_to_hit: list[str] | None = None
        self.api_config_from_yaml: dict | None = None
        self.endpoint_cycle: cycle | None = None
        self.wait_time_in_min: float | None = None
        self.cli_geo_params: dict | None = None

    def on_start(self) -> None:
        """Initialize the client before executing its first task.

        Loads the requested API configuration, resolves its development
        base URL, selects the configured endpoints, and initializes the
        endpoint iterator.

        Raises:
            ValueError: If the wait time, API configuration, base URL, or
                endpoint selection is invalid.
            FileNotFoundError: If the requested API configuration cannot
                be found.
            NotADirectoryError: If the API configuration directory does
                not exist.
        """

        options = self.environment.parsed_options

        self.host = options.host
        self.api_name = options.api_name

        self.on_land = options.on_land
        self.real_address = options.real_address

        self.wait_time_in_min = options.wait_time

        if self.wait_time_in_min < 0:
            raise ValueError("--wait-time cannot be negative")

        self.api_config_from_yaml = self._load_api_config_from_yaml()
        custom_host = self._resolve_base_url()

        if not custom_host:
            logging.warning(
                f"No development base URL configured for API '{self.api_name}'"
            )

        else:
            self.host = custom_host

        self.list_of_endpoints_to_hit = self._get_endpoints_from_yaml(
            selected_paths=options.endpoint_paths
        )

        if not self.list_of_endpoints_to_hit:
            raise ValueError(
                f"No endpoints found for API '{self.api_name}' "
                f"matching {options.endpoint_paths}"
            )

        self.endpoint_cycle = cycle(self.list_of_endpoints_to_hit)

        logging.info(
            "Locust client initialized | "
            f"api={self.api_name} | "
            f"host={self.host} | "
            f"endpoints={len(self.list_of_endpoints_to_hit)}"
        )

        for endpoint in self.list_of_endpoints_to_hit:
            logging.info(
                "Endpoint registered | "
                f"name={endpoint['name']} | "
                f"path={endpoint['path']} | "
                f"method={endpoint.get('method', 'GET')}"
            )

        self.client.headers.update({
            "User-Agent": (
                "geo_locust/0.1.0 "
                "(geographic API testing; contact: YOUR_EMAIL)"
            ),
            "Accept": "application/json",
        })

        logging.info(
            "HTTP REQUEST HEADERS | "
            f"headers={dict(self.client.headers)}"
        )

    @lru_cache(maxsize=None)
    def _load_api_config_from_yaml(self) -> dict:
        """Discover and load the selected API YAML configuration.

        Configuration files are discovered in the configured API schemas
        directory. The filename must follow the ``<api_name>.yaml`` pattern.

        Returns:
            The complete API configuration loaded from YAML.

        Raises:
            NotADirectoryError: If the configuration directory does not
                exist or is not a directory.
            FileNotFoundError: If no YAML files are found or the requested
                API configuration does not exist.
            ValueError: If the loaded YAML structure is invalid or does
                not contain a valid ``api`` section.
        """

        if not self.config_dir_with_api_schemas_path.is_dir():
            raise NotADirectoryError(
                f"API config directory not found: {self.config_dir_with_api_schemas_path}"
            )

        config_files_found_in_dir = sorted(
            self.config_dir_with_api_schemas_path.glob("*.yaml")
        )

        if not config_files_found_in_dir:
            raise FileNotFoundError(
                f"No YAML configurations found in "
                f"{self.config_dir_with_api_schemas_path}"
            )

        config_file_for_given_api_name = next(
            (
                file for file in config_files_found_in_dir
                if file.stem == self.api_name
            ), None,
        )

        if config_file_for_given_api_name is None:
            available_apis = [
                file for file in config_files_found_in_dir
            ]

            raise FileNotFoundError(
                f"API '{self.api_name}' not found. "
                f"Available APIs: {available_apis}"
            )

        with config_file_for_given_api_name.open(mode="r", encoding="utf-8") as file:
            api_config_from_yaml = yaml.safe_load(file) or {}

        if not isinstance(api_config_from_yaml, dict):
            raise ValueError(
                f"Invalid configuration in {config_file_for_given_api_name}: expected a mapping"
            )

        api_config = api_config_from_yaml.get("api")

        if not isinstance(api_config, dict):
            raise ValueError(
                f"Invalid or missing 'api' section in {config_file_for_given_api_name}"
            )

        logging.info(
            f"Loaded API configuration | "
            f"api={self.api_name} | "
            f"file={config_file_for_given_api_name}"
        )

        return api_config_from_yaml

    def _resolve_base_url(self) -> str:
        """
        Resolve and validate the API base URL from the configuration.

        Returns:
            A valid HTTP or HTTPS base URL.

        Raises:
            ValueError: If the base URL is missing, invalid, or malformed.
        """

        base_url = self.api_config_from_yaml["api"].get("base_url")

        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError(
                f"Missing or invalid base_url configuration for '{self.api_name}'"
            )

        base_url = base_url.strip()
        parsed_url = urlparse(base_url)

        if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
                or not parsed_url.hostname
        ):
            raise ValueError(
                f"Invalid base_url '{base_url}' for API '{self.api_name}'. "
                "Expected a valid HTTP or HTTPS URL."
            )

        return base_url.rstrip("/")

    def _get_endpoints_from_yaml(
            self,
            selected_paths: list[str],
    ) -> list[dict]:
        """
        Select API endpoints according to their configured names or paths.

        Args:
            selected_paths: Endpoint names or URL paths to include.
                Selecting ``all`` includes every configured endpoint.

        Returns:
            A list of endpoint configuration mappings matching the
            requested names or paths.

        Raises:
            ValueError: If the endpoint configuration is not a list.
        """

        endpoints = self.api_config_from_yaml["api"].get("endpoints", [])

        if not isinstance(endpoints, list):
            raise ValueError("API endpoints must be a list")

        if "all" in selected_paths:
            return endpoints

        return [
            endpoint for endpoint in endpoints
            if endpoint.get("name") in selected_paths or endpoint.get("path") in selected_paths
        ]

    @lru_cache(maxsize=1)
    def _get_jinja_environment(self) -> NativeEnvironment:
        return NativeEnvironment(
            undefined=StrictUndefined,
            autoescape=False,
        )

    @lru_cache(maxsize=256)
    def _get_compiled_template(self, template_string: str):
        return self._get_jinja_environment().from_string(template_string)

    def _build_query_params_from_template(self,
                                          endpoint: dict,
                                          on_land: bool,
                                          real_address: bool,
                                          ) -> dict[str, Any]:
        """
        Generate geographic data and render endpoint parameter templates.

        Inspects the endpoint's parameter templates to determine which
        geographic values are required.

        Supported placeholders:
            - ``{{ address }}``: Generates a fake full address.
            - ``{{ latitude }}``: Generates a geographic latitude.
            - ``{{ longitude }}``: Generates a geographic longitude.

        When an endpoint defines a bounding box, generated coordinates
        are constrained to that geographic area.

        Jinja's NativeEnvironment preserves native Python types when
        rendering parameter values.

        Args:
            endpoint: Endpoint configuration containing parameter templates
                and optional geographic bounding box constraints.

        Returns:
            A dictionary containing the fully rendered endpoint parameters.

        Raises:
            jinja2.exceptions.UndefinedError: If a template references
                a variable that was not generated.
            KeyError: If a required generated geographic value is missing.
        """

        template = endpoint.get("params", {})

        template_values = " ".join(
            value for value in template.values()
            if isinstance(value, str)
        )

        generated_query_params: dict[str, Any] = {}

        if "{{ address }}" in template_values:
            generated_address = self.geo_fake_generator.generate_address(
                real_address=real_address,
            )

            generated_query_params.update(generated_address)

            logging.info(
                "Generated fake address | "
                f"address={generated_address['full_address']} | "
                f"osm_url={generated_address['osm_url']}"
            )

        if "{{ latitude }}" in template_values or "{{ longitude }}" in template_values:
            bbox_config_from_yaml = endpoint.get("bbox")

            bbox = (
                box(
                    xmin=bbox_config_from_yaml["xmin"],
                    ymin=bbox_config_from_yaml["ymin"],
                    xmax=bbox_config_from_yaml["xmax"],
                    ymax=bbox_config_from_yaml["ymax"],
                )
                if bbox_config_from_yaml else None
            )

            generated_coordinates = (
                self.geo_fake_generator.generate_coordinates(
                    bbox=bbox,
                    on_land=on_land,
                )
            )

            generated_query_params.update(generated_coordinates)

            logging.info(
                "Generated fake coordinates | "
                f"latitude={generated_coordinates['latitude']} | "
                f"longitude={generated_coordinates['longitude']} | "
                f"osm_url={generated_coordinates['osm_url']}"
            )

        rendered_params = {
            key: (
                self._get_compiled_template(value).render(**generated_query_params)
                if isinstance(value, str) else value
            )
            for key, value in template.items()
        }

        logging.info(
            "Rendered endpoint parameters | "
            f"api={self.api_name} | "
            f"endpoint={endpoint['name']} | "
            f"params={rendered_params}"
        )

        return rendered_params

    def _call_endpoint(self, endpoint: dict[str, Any]) -> None:
        """
        Send an HTTP request using a configured API endpoint.

        Renders the endpoint's parameter templates, generates the required
        geographic test data, and dispatches the request through Locust's
        HTTP client.

        Request parameters are sent as query-string parameters for GET and
        other non-body methods, or as a JSON payload for POST, PUT, and PATCH.

        The request is registered under the API and endpoint name to ensure
        meaningful grouping in Locust's performance statistics. Response
        failures are explicitly reported when the HTTP status code indicates
        a client or server error.

        Args:
            endpoint: API endpoint configuration containing its name, path,
                HTTP method, and parameter templates.
        """
        http_method = endpoint.get("method", "GET").upper()
        path = endpoint["path"]
        params = self._build_query_params_from_template(
            endpoint=endpoint,
            on_land=self.on_land,
            real_address=self.real_address,
        )

        request_kwargs = (
            {"json": params}
            if http_method in {"POST", "PUT", "PATCH"}
            else {"params": params}
        )

        logging.info(
            f"Calling endpoint | method={http_method} | path={path} | params={params}"
        )

        url = urljoin(f"{self.host.rstrip('/')}/", path.lstrip("/"))

        with self.client.request(
                method=http_method,
                url=url,
                name=f"{self.api_name}: {endpoint['name']}",
                catch_response=True,
                **request_kwargs,
        ) as response:
            logging.info(
                "HTTP REQUEST | "
                f"method={http_method} | "
                f"url={response.request.url}"
            )

            logging.info(
                "HTTP RESPONSE | "
                f"status_code={response.status_code} | "
                f"response_time={response.elapsed.total_seconds():.3f}s | "
                f"body={response.text}"
            )

            if response.status_code >= 400:
                response.failure(
                    f"HTTP {response.status_code}: {response.text}"
                )
