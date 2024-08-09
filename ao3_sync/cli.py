import os

import rich_click as click
from dotenv import load_dotenv

import ao3_sync.choices
import ao3_sync.exceptions
from ao3_sync.ao3 import AO3

load_dotenv(override=True)

DEBUG = os.getenv("AO3_DEBUG", False)


@click.command()
@click.argument(
    "sync_type",
    type=click.Choice(ao3_sync.choices.SYNC_TYPES_VALUES, case_sensitive=False),
    default=ao3_sync.choices.DEFAULT_SYNC_TYPE,
)
@click.option("-u", "--username", "username", help="AO3 Username", envvar="AO3_USERNAME", required=True)
@click.option("-p", "--password", "password", help="AO3 Password", envvar="AO3_PASSWORD", required=True)
@click.option("--dry-run", "dryrun", is_flag=True, default=False)
def main(sync_type, username, password, dryrun):
    click.secho(f"Syncing AO3 {sync_type} for {username}...", bg="blue", fg="black", bold=True, color=True)

    if DEBUG:
        click.secho("DEBUG MODE: ON", bold=True, fg="red", color=True)

    if dryrun:
        click.secho("DRY RUN: ON", bold=True, fg="yellow", color=True)

    try:
        instance = AO3(username, password)

        if dryrun:
            click.secho(f"[SKIPPED] AO3 fetch {sync_type}", color=True)
        elif sync_type == ao3_sync.choices.SYNC_TYPES.BOOKMARKS:
            instance.get_bookmarks()

        click.secho("DONE!", bold=True, fg="green", color=True)
    except ao3_sync.exceptions.LoginError:
        click.echo(f"Error logging into AO3 with username: {username}")
        if DEBUG:
            raise
    except Exception:
        click.echo("Unexpected Error")
        if DEBUG:
            raise
