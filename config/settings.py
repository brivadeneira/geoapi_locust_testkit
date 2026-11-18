from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = "geoapi_locust_testkit"
    debug: bool = False
