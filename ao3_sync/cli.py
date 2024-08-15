import functools

import rich_click as click
from pydantic import SecretStr
from yaspin import yaspin

import ao3_sync.exceptions
from ao3_sync.api import AO3Api
from ao3_sync.enums import DownloadFormat

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

api = AO3Api()

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
            "options": ["--force", "--debug", "--debug-cache", "--history"],
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
        default=lambda: api.auth.username if api.auth.username else "",
        required=True,
    )
    @click.option(
        "-p",
        "--password",
        "password",
        help="AO3 Password",
        hide_input=True,
        default=lambda: api.auth.password.get_secret_value() if api.auth.password else "",
        required=True,
    )
    @click.option(
        "--debug/--no-debug",
        "debug",
        default=api.DEBUG,
        help="Enable debug mode",
    )
    @click.option(
        "--debug-cache/--no-debug-cache",
        "use_debug_cache",
        default=api.USE_DEBUG_CACHE,
        help="Enable or disable the debug cache",
    )
    @click.option(
        "--history/--no-history",
        "use_history",
        default=api.USE_HISTORY,
        help="Enable or disable history",
    )
    @functools.wraps(func)
    def wrapper(ctx, **kwargs):
        debug = kwargs.pop("debug", api.DEBUG)
        use_debug_cache = kwargs.pop("use_debug_cache", api.USE_DEBUG_CACHE)
        use_history = kwargs.pop("use_history", api.USE_HISTORY)

        username = kwargs.pop("username")
        password = kwargs.pop("password")

        api.DEBUG = debug
        api.USE_DEBUG_CACHE = use_debug_cache
        api.USE_HISTORY = use_history

        click.secho("AO3 Sync", bold=True, color=True)
        click.secho("Press Ctrl+C to cancel \n", color=True)

        if api.DEBUG:
            click.secho("DEBUG MODE         ENABLED", bold=True, fg="yellow", color=True)

        if api.DEBUG and not api.USE_DEBUG_CACHE:
            click.secho("DEBUG CACHE        DISABLED", bold=True, fg="cyan", color=True)

        if not api.USE_HISTORY:
            click.secho("HISTORY            DISABLED", bold=True, fg="cyan", color=True)

        if api.DEBUG or not api.USE_HISTORY:
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
                is_ao3_exception = isinstance(e, ao3_sync.exceptions.AO3Exception)
                spinner.color = "red"
                spinner.text = e.args[0] if is_ao3_exception else "An error occurred while logging in"
                spinner.fail("✘")
                api.debug_log(e)
                return

        return func(ctx, **kwargs)

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
    help="Query parameters",
)
@click.option(
    "--format",
    "formats",
    type=click.Choice(["all"] + [f.value for f in DownloadFormat]),
    default=["all"],
    help="Formats to download",
    multiple=True,
)
def bookmarks(ctx, **kwargs):
    """
    Sync AO3 Bookmarks
    """
    click.secho("\nSyncing AO3 Bookmarks", bold=True, color=True)

    try:
        api.bookmarks.sync(**kwargs)
        click.secho("DONE!", bold=True, fg="green", color=True)
    except Exception as e:
        is_ao3_exception = isinstance(e, ao3_sync.exceptions.AO3Exception)
        if is_ao3_exception:
            click.secho(e.args[0], fg="red", color=True, bold=True)
            api.debug_log(e)
        else:
            click.secho("An error occurred while syncing bookmarks", fg="red", color=True, bold=True)
            api.debug_log(e)


if __name__ == "__main__":
    cli()
