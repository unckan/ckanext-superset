"""
Shared test fixtures for ckanext-superset.

Override CKAN's `clean_db` so that the `activity` plugin's migrations run after
the core schema is reset. Without this, tests that exercise activity creation
fail because the `activity.permission_labels` column does not exist.
"""
import pytest


@pytest.fixture()
def clean_db(reset_db, migrate_db_for):
    reset_db()
    migrate_db_for("activity")
