from pydantic import SecretStr
import rich_click as click
from ao3_sync import settings
from ao3_sync.api import AO3Api
from ao3_sync.session import AO3Session
import ao3_sync.exceptions

session = AO3Session()

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.pass_context
@click.option(
    "-u",
    "--username",
    "username",
    help="AO3 Username",
    required=True,
    default=lambda: session.username,
)
@click.option(
    "-p",
    "--password",
    "password",
    help="AO3 Password",
    required=True,
    hide_input=True,
    default=lambda: session.password.get_secret_value() if session.password else None,
    show_default=False,
)
def cli(ctx, username, password):
    ctx.ensure_object(dict)

    if username is None or len(username) == 0:
        username = click.prompt("Enter your AO3 username", type=str)

    if password is None or len(password) == 0:
        password = click.prompt("Enter your AO3 password", type=str, hide_input=True)

    session.username = username
    session.password = SecretStr(password)


@cli.command()
@click.pass_context
@click.option("-f", "--force", "force", is_flag=True, default=False)
@click.option("--paginate/--no-paginate", "paginate", default=True)
@click.option("--page", "page", type=int, default=1)
def bookmarks(ctx, force, paginate, page):
    click.secho(f"Syncing AO3 Bookmarks for {session.username}...", bg="blue", fg="black", bold=True, color=True)

    if settings.DEBUG:
        click.secho("DEBUG MODE: ON", bold=True, fg="red", color=True)

    try:
        api = AO3Api(session)
        req_params = {"page": page}
        api.sync_bookmarks(paginate=paginate, req_params=req_params, force_update=force)
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
