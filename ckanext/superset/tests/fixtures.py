import pytest


@pytest.fixture
def superset_migrate(migrate_db_for):
    """ Apply the superset migrations """
    migrate_db_for('superset')
