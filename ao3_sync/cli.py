import functools

import rich_click as click
from pydantic import SecretStr
from yaspin import yaspin

import ao3_sync.api.exceptions
from ao3_sync.api import AO3ApiClient
from ao3_sync.api.enums import DownloadFormat

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

base_api = AO3ApiClient()

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.OPTION_GROUPS = {
    "ao3-sync bookmarks": [
        {
            "name": ":lock: Authentication",
            "options": ["--username", "--password"],
            "panel_styles": {
                "border_style": "yellow",
            },
        },
        {
            "name": "Sync Bookmarks Options",
            "options": ["--start-page", "--end-page", "--query-params", "--format"],
            "panel_styles": {
                "border_style": "white",
            },
        },
        {
            "name": "Advanced Options",
            "options": ["--downloads-dir", "--requests-per-second", "--history", "--history-file"],
        },
        {
            "name": "Debug Options",
            "options": [
                "--debug",
                "--debug-cache",
                "--debug-cache-dir",
            ],
        },
    ],
}


def shared_options(func):
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
        "--downloads-dir",
        "downloads_dir",
        type=click.Path(file_okay=False, writable=True),
        default=base_api.downloads_dir,
        show_default=True,
        help="Directory to save downloads",
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
        help="Path to history file",
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
        help="Directory to save debug cache",
    )
    @functools.wraps(func)
    def wrapper(ctx, **kwargs):
        api = AO3ApiClient(
            username=kwargs.pop("username"),
            password=kwargs.pop("password"),
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

        if api.debug:
            click.secho(
                "DEBUG MODE         ENABLED",
                bold=True,
                fg="yellow",
                color=True,
            )
            click.secho(
                f"DEBUG CACHE     {'ENABLED' if api.use_debug_cache else 'DISABLED'}",
                bold=True,
                fg="yellow",
                color=True,
            )

        if not api.use_history:
            click.secho(
                "HISTORY            DISABLED",
                bold=True,
                fg="cyan",
                color=True,
            )

        if api.debug or not api.use_history:
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


@cli.command(
    epilog="""
    [bold underline white]Resources[/]\n
    \n
    [link=https://github.com]User Guides[/] \n
    [link=https://github.com]Developer Documentation[/] \n
    """,
)
@shared_options
@click.option(
    "--start-page",
    "start_page",
    type=int,
    default=1,
    help="Start page number",
    show_default=True,
)
@click.option(
    "--end-page",
    "end_page",
    type=int,
    default=None,
    help="End page number",
    show_default=True,
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
    type=click.Choice(["all"] + [f.value for f in DownloadFormat]),
    default=["all"],
    show_default=True,
    help="Formats to download",
    multiple=True,
)
def bookmarks(ctx, api, **kwargs):
    """
    Sync AO3 Bookmarks
    """
    click.secho("\nSyncing AO3 Bookmarks", bold=True, color=True)

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


if __name__ == "__main__":
    cli()
