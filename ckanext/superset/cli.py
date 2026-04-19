import logging
import click
from ckan.plugins import toolkit as tk
from ckanext.superset.data import sync as sync_module


log = logging.getLogger(__name__)


@click.group(short_help="Apache Superset extension commands")
def superset():
    """ Commands for ckanext-superset. """


@superset.command(
    name="run-due-syncs",
    short_help="Run pending periodic syncs for Superset-linked datasets"
)
def run_due_syncs():
    """ Enqueue a sync job for every dataset whose `superset_next_sync` has arrived. """
    package_ids = sync_module.find_due_package_ids()
    click.echo(f"Found {len(package_ids)} package(s) due for sync")
    for pid in package_ids:
        click.echo(f" -> enqueuing sync for {pid}")
        tk.enqueue_job(
            sync_module.sync_dataset,
            args=[pid],
            title=f"superset_sync:{pid}",
        )
    click.echo("Done")


def get_commands():
    return [superset]
