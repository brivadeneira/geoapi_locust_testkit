from jinja2 import Environment, PackageLoader

env = Environment(
    loader=PackageLoader("geoapi_locust_testkit"),
    autoescape=True,
)
