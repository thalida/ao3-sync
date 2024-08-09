import click
from dotenv import load_dotenv
from ao3_sync.ao3 import AO3
from ao3_sync.choices import DEFAULT_SYNC_TYPE, SYNC_TYPES_VALUES
import ao3_sync.exceptions

load_dotenv()


@click.command()
@click.argument("sync_type", type=click.Choice(SYNC_TYPES_VALUES, case_sensitive=False), default=DEFAULT_SYNC_TYPE)
@click.option("-u", "--username", "username", help="AO3 Username", envvar="AO3_USERNAME", required=True)
@click.option("-p", "--password", "password", help="AO3 Password", envvar="AO3_PASSWORD", required=True)
def main(sync_type, username, password):
    click.echo(f"Running AO3 sync of {sync_type}...")
    try:
        instance = AO3(username, password, sync_type=sync_type)
        instance.run()
        click.echo("Done!")
    except ao3_sync.exceptions.LoginError:
        click.echo(f"Error logging into AO3 with username: {username}")
    except Exception:
        click.echo("Unexpected Error")
