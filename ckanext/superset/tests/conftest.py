"""
Shared test fixtures for ckanext-superset.

Override CKAN's `clean_db` so that the `activity` plugin's migrations run after
the core schema is reset. Without this, tests that exercise activity creation
fail because the `activity.permission_labels` column does not exist.
"""
import pytest
from ckan.plugins import plugin_loaded, toolkit


@pytest.fixture()
def clean_db(reset_db, migrate_db_for):
    reset_db()
    # CKAN 2.11 split the activity plugin into its own alembic tree, so its
    # tables need to be re-created after reset_db. On 2.10 the activity tables
    # are part of core's schema and migrate_db_for("activity") errors out
    # ("No 'script_location' key found in configuration").
    if plugin_loaded("activity") and toolkit.check_ckan_version(min_version="2.11"):
        migrate_db_for("activity")
