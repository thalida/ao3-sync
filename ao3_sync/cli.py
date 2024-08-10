import os

import rich_click as click
from dotenv import load_dotenv

import ao3_sync.exceptions
from ao3_sync.ao3 import AO3

load_dotenv(override=True)

DEBUG = os.getenv("AO3_DEBUG", False)
if isinstance(DEBUG, str):
    DEBUG = DEBUG.lower() in ("true", "1")


@click.command()
@click.argument(
    "sync_type",
    type=click.Choice(AO3.get_sync_types_values(), case_sensitive=False),
    default=AO3.get_default_sync_type(),
)
@click.option("-u", "--username", "username", help="AO3 Username", envvar="AO3_USERNAME", required=True)
@click.option("-p", "--password", "password", help="AO3 Password", envvar="AO3_PASSWORD", required=True)
@click.option("--dry-run", "dryrun", is_flag=True, default=False)
@click.option("-f", "--force", "force", is_flag=True, default=False)
@click.option("--paginate/--no-paginate", "paginate", default=True)
@click.option("--page", "page", type=int, default=1)
def main(sync_type, username, password, force, dryrun, paginate, page):
    click.secho(f"Syncing AO3 {sync_type} for {username}...", bg="blue", fg="black", bold=True, color=True)

    if DEBUG:
        click.secho("DEBUG MODE: ON", bold=True, fg="red", color=True)

    if dryrun:
        click.secho("DRY RUN: ON", bold=True, fg="yellow", color=True)

    try:
        instance = AO3(username, password)

        if dryrun:
            click.secho(f"[SKIPPED] AO3 fetch {sync_type}", color=True)
        elif sync_type == AO3.SYNC_TYPES.BOOKMARKS:
            req_params = {"page": page}
            instance.sync_bookmarks(paginate=paginate, req_params=req_params, force_update=force)

        click.secho("DONE!", bold=True, fg="green", color=True)
    except ao3_sync.exceptions.LoginError as e:
        click.echo(f"Error logging into AO3 with username: {username}")
        if DEBUG:
            print(e)
            raise
    except Exception as e:
        click.echo("Unexpected Error")
        if DEBUG:
            print(e)
            raise e
