import functools

import rich_click as click
from pydantic import SecretStr
from rich.console import Console
from rich.table import Table
from yaspin import yaspin

import ao3_sync.api.exceptions
from ao3_sync.api import AO3ApiClient
from ao3_sync.api.enums import (
    DEFAULT_BOOKMARKS_SORT_OPTION_VALUE,
    DEFAULT_DOWNLOAD_FORMATS_VALUES,
    BookmarksSortOption,
    DownloadFormat,
)
from ao3_sync.utils import seralize_download_format, seralize_sort_by

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

console = Console()

base_api = AO3ApiClient()


def create_option_group(options):
    return [
        {
            "name": ":lock: Authentication",
            "options": [
                "--username",
                "--password",
            ],
            "panel_styles": {
                "border_style": "yellow",
            },
        },
        options,
        {
            "name": "Advanced Options",
            "options": [
                "--output-dir",
                "--downloads-dir",
                "--requests-per-second",
                "--history",
                "--history-file",
            ],
        },
        {
            "name": "Debug Options",
            "options": [
                "--debug",
                "--debug-cache",
                "--debug-cache-dir",
            ],
        },
    ]


# https://archiveofourown.org/works/18462467

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.OPTION_GROUPS = {
    "ao3-sync bookmarks": create_option_group(
        {
            "name": "Sync Bookmarks Options",
            "options": [
                "--start-page",
                "--end-page",
                "--sort-by",
                "--query-params",
                "--format",
            ],
            "panel_styles": {
                "border_style": "white",
            },
        }
    ),
    "ao3-sync series": create_option_group(
        {
            "name": "Sync Series Options",
            "options": [
                "--series",
                "--format",
            ],
            "panel_styles": {
                "border_style": "white",
            },
        }
    ),
    "ao3-sync work": create_option_group(
        {
            "name": "Sync Work Options",
            "options": [
                "--work",
                "--format",
            ],
            "panel_styles": {
                "border_style": "white",
            },
        }
    ),
}


def api_command(func):
    @cli.command(
        epilog="""
        [bold underline white]Resources[/]\n
        \n
        [link=https://github.com]User Guides[/] \n
        [link=https://github.com]Developer Documentation[/] \n
        """,
    )
    @click.pass_context
    @click.option(
        "-u",
        "--username",
        "username",
        help="AO3 Username",
        default=lambda: base_api.auth.username if base_api.auth.username else "",
        required=True,
    )
    @click.option(
        "-p",
        "--password",
        "password",
        help="AO3 Password",
        hide_input=True,
        default=lambda: base_api.auth.password.get_secret_value() if base_api.auth.password else "",
        required=True,
    )
    @click.option(
        "--output-dir",
        "output_dir",
        type=click.Path(file_okay=False, writable=True),
        default=base_api.output_dir,
        show_default=True,
        help="Directory to save output",
    )
    @click.option(
        "--downloads-dir",
        "downloads_dir",
        type=click.Path(file_okay=False, writable=True),
        default=base_api.downloads_dir,
        show_default=True,
        help="Directory to save downloads. Directory wil be nested under output-dir",
    )
    @click.option(
        "--requests-per-second",
        "num_requests_per_second",
        type=float,
        default=base_api.num_requests_per_second,
        show_default=True,
        help="Number of requests per second",
    )
    @click.option(
        "--history/--no-history",
        "use_history",
        default=base_api.use_history,
        show_default=True,
        help="Enable or disable history",
    )
    @click.option(
        "--history-file",
        "history_filepath",
        type=click.Path(file_okay=True, writable=True),
        default=base_api.history_filepath,
        show_default=True,
        help="Path to history file. File will be nested under output-dir",
    )
    @click.option(
        "--debug/--no-debug",
        "debug",
        default=base_api.debug,
        show_default=True,
        help="Enable debug mode",
    )
    @click.option(
        "--debug-cache/--no-debug-cache",
        "use_debug_cache",
        default=base_api.use_debug_cache,
        show_default=True,
        help="Enable or disable the debug cache",
    )
    @click.option(
        "--debug-cache-dir",
        "debug_cache_dir",
        type=click.Path(file_okay=False, writable=True),
        default=base_api.debug_cache_dir,
        show_default=True,
        help="Directory to save debug cache. Directory will be nested under output-dir",
    )
    @functools.wraps(func)
    def wrapper(ctx, **kwargs):
        api = AO3ApiClient(
            username=kwargs.pop("username"),
            password=kwargs.pop("password"),
            output_dir=kwargs.pop("output_dir"),
            downloads_dir=kwargs.pop("downloads_dir"),
            num_requests_per_second=kwargs.pop("num_requests_per_second"),
            use_history=kwargs.pop("use_history"),
            history_filepath=kwargs.pop("history_filepath"),
            debug=kwargs.pop("debug"),
            use_debug_cache=kwargs.pop("use_debug_cache"),
            debug_cache_dir=kwargs.pop("debug_cache_dir"),
        )

        username = api.auth.username
        password = api.auth.password.get_secret_value() if api.auth.password else None

        click.secho("AO3 Sync", bold=True, color=True)
        click.secho("Press Ctrl+C to cancel \n", color=True)

        table = Table(
            title="Settings",
            title_justify="left",
            title_style="bold",
            show_lines=False,
            show_edge=True,
            show_header=False,
            expand=True,
            pad_edge=True,
        )
        table.add_column("Setting")
        table.add_column("Value")
        table.add_row("Downloads Directory", str(api.get_downloads_dir().resolve()), end_section=True)

        if api.num_requests_per_second != base_api.num_requests_per_second:
            table.add_row("Requests Per Second", f"{api.num_requests_per_second}", end_section=True)

        if api.use_history:
            table.add_row("History", "[green]Enabled")
            table.add_row("History File", str(api.get_history_filepath().resolve()), end_section=True)

        if api.debug:
            table.add_row("Debug", "[green]Enabled")
            table.add_row("Debug Cache", "[green]Enabled" if api.use_debug_cache else "[red]Disabled")
            table.add_row("Debug Cache Directory", str(api.get_debug_cache_dir().resolve()), end_section=True)

        console.print(table)
        click.echo()

        has_username = username is not None and len(username) > 0
        has_password = password is not None and len(password) > 0

        if not has_username or not has_password:
            click.secho("Please provide your AO3 username and password", color=True)

        if username is None or len(username) == 0:
            username = click.prompt(click.style("AO3 username", fg="blue"), type=str)
        else:
            click.secho(f"AO3 username: {username}", color=True)

        if password is None or len(password) == 0:
            password = click.prompt(click.style("AO3 password", fg="blue"), type=str, hide_input=True)
        else:
            click.secho(f"AO3 password: {SecretStr(password)}", color=True)

        with yaspin(text="Logging into AO3\r", color="yellow") as spinner:
            try:
                api.auth.login(username=username, password=password)
                spinner.color = "green"
                spinner.text = "Successfully logged in!"
                spinner.ok("✔")
            except Exception as e:
                is_ao3_exception = isinstance(e, ao3_sync.api.exceptions.AO3Exception)
                spinner.color = "red"
                spinner.text = e.args[0] if is_ao3_exception else "An error occurred while logging in"
                spinner.fail("✘")
                api._debug_log(e)
                return

        return func(ctx, api, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    """
    Archive your AO3 Account
    """
    ctx.ensure_object(dict)
    return


@api_command
@click.option(
    "--start-page",
    "start_page",
    type=int,
    default=1,
    show_default=True,
    help="Start page number",
)
@click.option(
    "--end-page",
    "end_page",
    type=int,
    default=None,
    show_default=True,
    help="End page number",
)
@click.option(
    "--sort-by",
    "sort_by",
    type=click.Choice([f.value for f in BookmarksSortOption]),
    default=DEFAULT_BOOKMARKS_SORT_OPTION_VALUE,
    show_default=True,
    help="Sort bookmarks by",
)
@click.option(
    "--query-params",
    "query_params",
    type=str,
    default=None,
    show_default=True,
    help="Query parameters",
)
@click.option(
    "--format",
    "formats",
    type=click.Choice([f.value for f in DownloadFormat]),
    default=DEFAULT_DOWNLOAD_FORMATS_VALUES,
    show_default=True,
    help="Formats to download",
    multiple=True,
)
def bookmarks(ctx, api, **kwargs):
    """
    Sync AO3 Bookmarks
    """
    click.secho("\nSyncing AO3 Bookmarks", bold=True, color=True)

    kwargs["formats"] = seralize_download_format(kwargs.get("formats"))
    kwargs["sort_by"] = seralize_sort_by(kwargs.get("sort_by"))

    try:
        api.bookmarks.sync(**kwargs)
        click.secho("DONE!", bold=True, fg="green", color=True)
    except Exception as e:
        is_ao3_exception = isinstance(e, ao3_sync.api.exceptions.AO3Exception)
        if is_ao3_exception:
            click.secho(e.args[0], fg="red", color=True, bold=True)
            api._debug_log(e)
        else:
            click.secho("An error occurred while syncing bookmarks", fg="red", color=True, bold=True)
            api._debug_log(e)


@api_command
@click.option(
    "--work",
    "work_id",
    type=str,
    required=True,
)
@click.option(
    "--format",
    "formats",
    type=click.Choice([f.value for f in DownloadFormat]),
    default=DEFAULT_DOWNLOAD_FORMATS_VALUES,
    show_default=True,
    help="Formats to download",
    multiple=True,
)
def work(ctx, api, **kwargs):
    """
    Sync AO3 Work
    """
    click.secho("\nSyncing AO3 Work", bold=True, color=True)

    kwargs["formats"] = seralize_download_format(kwargs.get("formats"))

    try:
        api.works.sync(**kwargs)
        click.secho("DONE!", bold=True, fg="green", color=True)
    except Exception as e:
        is_ao3_exception = isinstance(e, ao3_sync.api.exceptions.AO3Exception)
        if is_ao3_exception:
            click.secho(e.args[0], fg="red", color=True, bold=True)
            api._debug_log(e)
        else:
            click.secho("An error occurred while syncing work", fg="red", color=True, bold=True)
            api._debug_log(e)


@api_command
@click.option(
    "--series",
    "series_id",
    type=str,
    required=True,
)
@click.option(
    "--format",
    "formats",
    type=click.Choice([f.value for f in DownloadFormat]),
    default=DEFAULT_DOWNLOAD_FORMATS_VALUES,
    show_default=True,
    help="Formats to download",
    multiple=True,
)
def series(ctx, api, **kwargs):
    """
    Sync AO3 Work
    """
    click.secho("\nSyncing AO3 Series", bold=True, color=True)

    kwargs["formats"] = seralize_download_format(kwargs.get("formats"))

    try:
        api.series.sync(**kwargs)
        click.secho("DONE!", bold=True, fg="green", color=True)
    except Exception as e:
        is_ao3_exception = isinstance(e, ao3_sync.api.exceptions.AO3Exception)
        if is_ao3_exception:
            click.secho(e.args[0], fg="red", color=True, bold=True)
            api._debug_log(e)
        else:
            click.secho("An error occurred while syncing work", fg="red", color=True, bold=True)
            api._debug_log(e)


if __name__ == "__main__":
    cli()
