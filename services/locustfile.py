from itertools import cycle
from locust import tag, task



from services.custom_http_locust_client import CustomLocustClient


class GeoAPITestUser(CustomLocustClient):
    """
    Locust tasks for exercising all configured API endpoints with
    different geographic data generation strategies.

    Each task cycle through all selected endpoints and delegates
    parameter generation and HTTP execution to CustomLocustClient.

    Available tags:
        coordinates
        coordinates_on_land
        coordinates_inside_bbox
        coordinates_inside_bbox_on_land
        address
        address_real
    """

    abstract = False

    def on_start(self) -> None:
        """Initialize the parent client and endpoint iterator."""

        super().on_start()
        self._endpoint_cycle = cycle(self.list_of_endpoints_to_hit)

    def _run_endpoints(self, cli_geo_params: dict) -> None:
        """
        Run the next configured endpoint using the selected generation options.
        """

        self._generation_options = cli_geo_params

        try:
            endpoint = next(self._endpoint_cycle)
            self._call_endpoint(endpoint)
        finally:
            self._generation_options = None

    @tag("coordinates")
    @task
    def coordinates(self) -> None:
        """
        Exercise endpoints with unrestricted coordinates.
        """

        self._run_endpoints({
            "on_land": False,
            "bbox": False,
        })

    @tag("coordinates_on_land")
    @task
    def coordinates_on_land(self) -> None:
        """
        Exercise endpoints with coordinates located on land.
        """

        self._run_endpoints({
            "on_land": True,
            "bbox": False,
        })

    @tag("coordinates_inside_bbox")
    @task
    def coordinates_inside_bbox(self) -> None:
        """
        Exercise endpoints with coordinates inside their configured bounding boxes.
        """

        self._run_endpoints({
            "on_land": False,
            "bbox": True,
        })

    @tag("coordinates_inside_bbox_on_land")
    @task
    def coordinates_inside_bbox_on_land(self) -> None:
        """Exercise endpoints with coordinates inside their bounding boxes and on land."""

        self._run_endpoints({
            "on_land": True,
            "bbox": True,
        })

    @tag("address")
    @task
    def address(self) -> None:
        """Exercise endpoints with synthetic addresses."""

        self._run_endpoints({
            "from_real_dataset": False,
        })

    @tag("address_real")
    @task
    def address_real(self) -> None:
        """Exercise endpoints with addresses from the real address dataset."""

        self._run_endpoints({
            "from_real_dataset": True,
        })
