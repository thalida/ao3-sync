import functools
import rich_click as click
from ao3_sync import settings
from ao3_sync.api import AO3Api
from ao3_sync.session import AO3Session
import ao3_sync.exceptions

session = AO3Session()

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def shared_options(func):
    @click.pass_context
    @click.option(
        "--debug",
        is_flag=True,
        flag_value=True,
        default=False,
        help="Enable Debug Mode",
    )
    @click.option(
        "-u",
        "--username",
        "username",
        help="AO3 Username",
        default=lambda: session.username,
    )
    @click.option(
        "-p",
        "--password",
        "password",
        help="AO3 Password",
        hide_input=True,
        default=lambda: session.password.get_secret_value() if session.password else None,
    )
    @functools.wraps(func)
    def wrapper(ctx, debug, username, password, *args, **kwargs):
        if debug:
            settings.DEBUG = True

        if settings.DEBUG:
            click.secho("DEBUG MODE: ON", bold=True, fg="red", color=True)

        if username is None or len(username) == 0:
            username = click.prompt("Enter your AO3 username", type=str)

        if password is None or len(password) == 0:
            password = click.prompt("Enter your AO3 password", type=str, hide_input=True)

        session.set_auth(username, password)
        return func(ctx, *args, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.command()
@shared_options
@click.option("--page", "page", type=int, default=1, help="Page number")
@click.option("--paginate/--no-paginate", "paginate", default=True, help="Should we paginate?")
@click.option("-f", "--force", "force", is_flag=True, default=False, help="Force update")
@click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Dry Run")
def bookmarks(ctx, page, paginate, **kwargs):
    """
    Sync AO3 Bookmarks
    """
    click.secho(f"Syncing AO3 Bookmarks for {session.username}...", bg="blue", fg="black", bold=True, color=True)

    try:
        api = AO3Api(session, **kwargs)
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
