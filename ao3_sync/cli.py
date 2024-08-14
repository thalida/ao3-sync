import functools

import rich_click as click
from pydantic import SecretStr
from yaspin import yaspin

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.client import Client
from ao3_sync.enums import DownloadFormat
from ao3_sync.utils import debug_log

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

api = Client()

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
            "options": ["--page", "--paginate"],
            "panel_styles": {
                "border_style": "white",
            },
        },
        {
            "name": "Advanced Options",
            "options": ["--debug", "--force"],
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
    @click.option("--debug", is_flag=True, flag_value=True, default=False, help="Enable debug mode")
    @click.option(
        "-f",
        "--force",
        "force",
        is_flag=True,
        flag_value=True,
        default=False,
        help="Enable force update",
    )
    @functools.wraps(func)
    def wrapper(ctx, **kwargs):
        debug = kwargs.pop("debug", False)
        force_update = kwargs.pop("force", False)

        username = kwargs.pop("username")
        password = kwargs.pop("password")

        if debug:
            settings.DEBUG = True

        if force_update:
            settings.FORCE_UPDATE = True

        click.secho("AO3 Sync", bold=True, color=True)
        click.secho("Press Ctrl+C to cancel \n", color=True)

        if settings.DEBUG:
            click.secho("DEBUG MODE         ENABLED", bold=True, fg="yellow", color=True)

        if settings.FORCE_UPDATE:
            click.secho("FORCE UPDATE MODE  ENABLED", bold=True, fg="red", color=True)

        if settings.DEBUG or settings.FORCE_UPDATE:
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
                debug_log(e)
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
    [bold underline white]Examples[/]\n
    \n
    [bold]Basic Usage:[/]\n
    ao3-sync bookmarks --username your-username --password your-password \n
    [i]Syncs all new bookmarks, by default it will paginate and stop at the last synced bookmark. See --no-paginate and --force to override this behavior.[/] \n
    \n
    [bold]Advanced Usage:[/]\n
    ao3-sync bookmarks --username your-username --password your-password --force \n
    [i]Force update all bookmarks[/] \n
    \n
    ao3-sync bookmarks --username your-username --password your-password --page 2 --no-paginate --force\n
    [i]Force sync all bookmarks on page 2 only[/] \n
    \n
    AO3_USERNAME=your-username AO3_PASSWORD=your-password ao3-sync bookmarks \n
    [i]Use environment variables[/] \n
    \n
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
            debug_log(e)
        else:
            click.secho("An error occurred while syncing bookmarks", fg="red", color=True, bold=True)
            debug_log(e)


if __name__ == "__main__":
    cli()
