import functools
from pydantic import SecretStr
import rich_click as click
from ao3_sync import settings
from ao3_sync.api import AO3Api
from ao3_sync.session import AO3Session
import ao3_sync.exceptions
from ao3_sync.utils import debug_log


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

session = AO3Session()


def shared_options(func):
    @click.pass_context
    @click.option(
        "-u",
        "--username",
        "username",
        help="AO3 Username",
        default=lambda: session.username if session.username else "",
        required=True,
    )
    @click.option(
        "-p",
        "--password",
        "password",
        help="AO3 Password",
        hide_input=True,
        default=lambda: session.password.get_secret_value() if session.password else "",
        required=True,
    )
    @click.option(
        "--debug",
        is_flag=True,
        flag_value=True,
        default=False,
        help="Enable Debug Mode",
    )
    @click.option("-f", "--force", "force", is_flag=True, default=False, help="Force update")
    @click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Dry Run")
    @functools.wraps(func)
    def wrapper(ctx, **kwargs):
        debug = kwargs.get("debug", False)
        username = kwargs.get("username")
        password = kwargs.get("password")

        if debug:
            settings.DEBUG = True

        click.secho("AO3 Sync", bold=True, color=True)
        click.secho("Press Ctrl+C to cancel \n", color=True)

        if settings.DEBUG:
            click.secho("DEBUG MODE: ON\n", bold=True, fg="red", color=True)

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

        click.secho("\nLogging into AO3...", color=True)

        try:
            session.set_auth(username, password)
            session.login()
            click.secho("Logged in!", fg="green", color=True)
        except ao3_sync.exceptions.LoginError as e:
            click.secho(e.args[0], fg="red", color=True, bold=True)
            debug_log(e)
            return
        except Exception as e:
            click.secho("Unexpected Error", fg="red", color=True, bold=True)
            debug_log(e)
            return

        kwargs["username"] = session.username
        kwargs["password"] = session.password.get_secret_value() if session.password else ""

        return func(ctx, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@shared_options
@click.option("--page", "page", type=int, default=1, help="Page number")
@click.option("--paginate/--no-paginate", "paginate", default=True, help="Should we paginate?")
def bookmarks(ctx, **kwargs):
    """
    Sync AO3 Bookmarks
    """
    click.secho(f"Syncing AO3 Bookmarks for {session.username}...", bg="blue", fg="black", bold=True, color=True)
    page: int = kwargs.get("page", 1)
    paginate: bool = kwargs.get("paginate", True)

    try:
        api = AO3Api(
            session,
            dry_run=kwargs.get("dry_run", False),
            force=kwargs.get("force", False),
        )
        api.sync_bookmarks(query_params={"page": page}, paginate=paginate)
        click.secho("DONE!", bold=True, fg="green", color=True)
    except ao3_sync.exceptions.LoginError as e:
        click.echo(f"Error logging into AO3 for {session.username}")
        if settings.DEBUG:
            print(e)
            raise
    except Exception as e:
        click.echo("Unexpected Error")
        if settings.DEBUG:
            print(e)
            raise e


if __name__ == "__main__":
    cli()
