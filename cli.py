import subprocess
import sys

import typer

from config.settings import settings, AVAILABLE_LOCUST_TAGS

app = typer.Typer()


@app.command(
    help=f"Display the current installed version of {settings.project_name}."
)
def version() -> None:
    from . import __version__

    typer.echo(f"{settings.project_name} - {__version__}")


@app.command(help="Display a friendly greeting.")
def hello() -> None:
    typer.echo(f"Hello from {settings.project_name}!")


@app.command(help="Run API load tests using Locust.")
def load_test(
        # env: str = typer.Option(default="dev", help="Target environment."),  # nice-to-have
        api_name: str = typer.Option(
            default="nominatim",  # "all" by default nice-to-have
            help="API configuration name.",
        ),
        endpoint_paths: list[str] = typer.Option(
            default=["all"],
            help="Endpoint names or paths.",
        ),
        on_land: bool = typer.Option(
            default=True,
            help="Generate coordinates located on land.",
        ),
        real_address: bool = typer.Option(
            default=False,
            help="Generate addresses from the real address dataset.",
        ),
        users: int = typer.Option(
            default=1,
            min=1,
            help="Number of concurrent users.",
        ),
        tags: list[str] | None = typer.Option(
            default=None,
            help="Only execute tasks matching these tags.",
        ),
        spawn_rate: float = typer.Option(
            default=0.1,
            min=0.1,
            help="Users spawned per second.",
        ),
        run_time: str = typer.Option(
            default="1m",
            help="Test duration.",
        ),
        wait_time: float = typer.Option(
            default=1.5,
            min=0,
            help="Wait between tasks in minutes.",
        ),
        headless: bool = typer.Option(
            default=False,
            help="Run without the web interface.",
        ),
) -> None:
    locust_custom_command = [
        sys.executable, "-m", "locust", "-f", str(settings.locust_file_path),
        "--api-name", api_name,
        "--endpoint-paths", *endpoint_paths,
        "--wait-time", str(wait_time),
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", run_time,
    ]

    if on_land:
        locust_custom_command.append("--on-land")

    if real_address:
        locust_custom_command.append("--real-address")

    if tags:
        locust_custom_command.extend(["--tags", *tags])

        invalid_tags = set(tags) - set(AVAILABLE_LOCUST_TAGS)

        if invalid_tags:
            raise typer.BadParameter(
                f"Invalid tags: {sorted(invalid_tags)}. "
                f"Available tags: {AVAILABLE_LOCUST_TAGS}"
            )

    if tags:
        typer.echo(f"Selected tasks: {', '.join(tags)}")

    if headless:
        locust_custom_command.append("--headless")

    typer.echo(f"Starting Locust client for API: {api_name}")

    subprocess.run(locust_custom_command, check=True)


if __name__ == "__main__":
    app()
